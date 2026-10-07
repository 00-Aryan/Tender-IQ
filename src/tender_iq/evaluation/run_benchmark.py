"""Measure a frozen TenderIQ API using human-verified question files only.

No app imports, app edits, LLM judge, retries, or dependency installation.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from zoneinfo import ZoneInfo

import fitz
import requests
from dotenv import dotenv_values


def normalized(text):
    text = str(text).lower().replace('**', '').replace('`', '')
    text = re.sub(r'(?<=\d),(?=\d)', '', text)
    months = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
    for month, name in enumerate(months, 1):
        text = re.sub(rf'\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{name}(?:\s*,)?\s+(\d{{4}})\b', lambda m: f'{int(m[2]):04d}-{month:02d}-{int(m[1]):02d}', text)
        text = re.sub(rf'\b{name}\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s*,)?\s+(\d{{4}})\b', lambda m: f'{int(m[2]):04d}-{month:02d}-{int(m[1]):02d}', text)
    text = re.sub(r'\b(\d{2})-(\d{2})-(\d{4})\b', lambda m: f'{m[3]}-{m[2]}-{m[1]}', text)
    def clock(m):
        hour, minute = int(m[1]) % 12, int(m[2] or 0)
        if m[3] == 'pm':
            hour += 12
        return f'{hour:02d}:{minute:02d}'
    text = re.sub(r'\b(\d{1,2})(?::(\d{2}))?(?::00)?\s*(am|pm)\b', clock, text)
    text = re.sub(r'\b(\d{1,2}):(\d{2})(?::00)?\b', lambda m: f'{int(m[1]):02d}:{m[2]}', text)
    for value, word in enumerate(['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve']):
        text = re.sub(rf'\b{word}\b', str(value), text)
    return ' '.join(text.split())


def numeric_values(text):
    found = set()
    for number in re.findall(r'(?<!\w)\d+(?:\.\d+)?(?!\w)', text):
        try:
            found.add(str(Decimal(number).normalize()))
        except InvalidOperation:
            pass
    return found


def score(question, answer, error):
    """Conservative, reviewable first pass. Never a semantic or LLM grade."""
    if error:
        return 'wrong', False, False, ['Request failed; failure counted in denominator.']
    body = re.split(r'(?im)^\s*\**(?:sources?|references?)\**\s*:', answer, maxsplit=1)[0]
    actual, expected = normalized(body), normalized(question['expected_answer'])
    flags = []
    if not question['answerable']:
        abstains = bool(re.search(r'not found|not specified|not provided|not mentioned|not stated|not available|does not (?:contain|specify|provide|state|mention)|no information|cannot (?:determine|identify|find)|can.t (?:determine|identify|find)|isn.t (?:specified|provided|mentioned|stated|available)', actual))
        risky = bool(numeric_values(re.sub(r'gem/\d+/b/\d+|page\s+\d+', '', actual))) or bool(re.search(r'\b(?:probably|presumably|likely|might be|estimate that)\b', actual))
        if abstains and risky:
            return 'partial', False, True, ['Abstention wording plus numeric or speculative detail; review for an invented answer.']
        if abstains:
            flags = ['Automatic abstention wording check; review wording if it contains other claims.'] if len(actual.split()) > 65 else []
            return 'correct', False, True, flags
        return 'wrong', False, False, ['No recognised abstention phrase; a valid paraphrase may need manual review.']
    hint = normalized(question['match_hint'])
    hint_match = hint in actual
    required, present = numeric_values(expected), numeric_values(actual)
    missing = required - present
    dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', expected)
    clocks = re.findall(r'\b\d{2}:\d{2}\b', expected)
    missing_exact = [x for x in dates + clocks if x not in actual]
    contradiction = expected.startswith('no ') and bool(re.search(r'\byes\b', actual))
    if hint_match and not missing and not missing_exact and not contradiction:
        label = 'correct'
        if question['category'] in ('eligibility', 'multi_section') or not required:
            flags.append('Hint/value checks do not verify all semantic conditions or additional claims.')
        if re.search(r'\b(?:however|although|but|not specified|not found)\b', actual):
            flags.append('Qualified or negative wording alongside a matching value; review.')
    elif hint_match or (required and required.intersection(present)):
        label = 'partial'
        flags.append('Some checks pass, but at least one required value, exact date/time, hint or polarity check fails.')
    else:
        label = 'wrong'
        flags.append('Hint not found; formatting or paraphrase could cause a false negative.')
    if missing:
        flags.append('Missing expected numeric tokens: ' + ', '.join(sorted(missing)))
    if missing_exact:
        flags.append('Missing expected date/time: ' + ', '.join(missing_exact))
    if contradiction:
        flags.append('Yes/no wording may contradict the expected negative answer.')
    return label, hint_match, False, flags


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-commit', required=True)
    parser.add_argument('--date', required=True, help='Client date as YYYYMMDD')
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--pause', type=float, default=2.0)
    parser.add_argument('--timeout', type=float, default=180.0)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    def git(*arguments):
        return subprocess.check_output(['git', *arguments], cwd=root, text=True).strip()
    freeze = git('rev-parse', args.freeze_commit)
    commit = git('rev-parse', 'HEAD')
    protected_names = git('ls-tree', '-r', '--name-only', freeze).splitlines()
    protected = {name: hashlib.sha256(subprocess.check_output(['git', 'show', freeze + ':' + name], cwd=root)).hexdigest() for name in protected_names}
    python_files = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / 'src').rglob('*.py')}
    env_digest = hashlib.sha256((root / '.env').read_bytes()).digest()
    def versions():
        return dict(sorted((d.metadata.get('Name', 'unknown'), d.version) for d in importlib.metadata.distributions()))
    package_versions = versions()
    def guard():
        changed = [p for p, digest in protected.items() if not (root / p).is_file() or hashlib.sha256((root / p).read_bytes()).hexdigest() != digest]
        current_python = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / 'src').rglob('*.py')}
        if changed or current_python != python_files or versions() != package_versions or hashlib.sha256((root / '.env').read_bytes()).digest() != env_digest or git('rev-parse', 'HEAD') != commit:
            raise RuntimeError('Frozen inputs, app files, environment, dependencies or HEAD changed. Run is INVALID; rerun required. Files: ' + ', '.join(changed))
    guard()
    eval_dir = root / 'src/tender_iq/evaluation'
    questions, documents, question_hashes, excluded = [], [], {}, []
    for filename in ('test_data.json', 'test_data2.json'):
        path = eval_dir / filename
        question_hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        data = json.loads(path.read_text())
        document = data['document']
        pdf = Path(document['pdf_path'])
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != document['sha256']:
            raise RuntimeError('PDF hash differs from the reviewed question metadata: ' + pdf.name)
        with fitz.open(pdf) as doc:
            pages = len(doc)
        documents.append(dict(document, pages=pages, dataset=filename))
        for item in data['eval_dataset']:
            if item.get('verified') is True:
                questions.append(dict(item, dataset=filename))
            else:
                excluded.append({'id': item.get('id'), 'source': item.get('source'), 'reason': 'verified is not true'})
    if not questions:
        raise RuntimeError('No verified questions. No API will be started.')
    if len({q['id'] for q in questions}) != len(questions):
        raise RuntimeError('Question IDs are not unique.')
    values = dotenv_values(root / '.env')
    env = dict(os.environ)
    env.update({k: v for k, v in values.items() if v is not None})
    secrets = [v for k, v in env.items() if v and re.search('KEY|TOKEN|SECRET|PASSWORD', k, re.I)]
    def clean(text):
        for value in secrets:
            text = text.replace(value, '[REDACTED]')
        return re.sub(r'AIza[0-9A-Za-z_-]{35}|sk-(?:proj-|or-v1-)?[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{30,}', '[REDACTED]', text)
    out = eval_dir / 'results'
    out.mkdir(exist_ok=True)
    csv_path = out / f'run_{args.date}_{commit[:7]}.csv'
    if csv_path.exists() or (out / 'manifest.json').exists():
        raise RuntimeError('Refuse to overwrite an existing benchmark. Archive its results explicitly first.')
    scratch = Path(tempfile.mkdtemp(prefix='tenderiq-frozen-benchmark-'))
    env['PYTHONPATH'] = str(root / 'src')
    env['PYTHONUNBUFFERED'] = '1'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    now = lambda: datetime.now(ZoneInfo('Asia/Kolkata')).isoformat()
    logs, events, rows, warmups, uploads = [], [], [], [], []
    ready = threading.Event()
    lock = threading.Lock()
    def write_json(name, value):
        (out / name).write_text(clean(json.dumps(value, ensure_ascii=False, indent=2)) + '\n')
    manifest = {
        'date': f'{args.date[:4]}-{args.date[4:6]}-{args.date[6:]}', 'timezone': 'Asia/Kolkata', 'started_at': now(),
        'commit_hash': commit, 'dataset_freeze_commit': freeze, 'branch': git('branch', '--show-current'),
        'question_file_sha256': question_hashes, 'verified_questions': len(questions), 'excluded': excluded,
        'runs': args.runs, 'pause_seconds': args.pause, 'request_timeout_seconds': args.timeout, 'runner_http_retries': 0,
        'python_version': platform.python_version(), 'python_executable': sys.executable, 'package_versions': package_versions,
        'host': {'os': platform.platform(), 'kernel': platform.release(), 'machine': platform.machine(), 'logical_cpus': os.cpu_count(),
                 'cpu_model': next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), 'unavailable'),
                 'memory_total_kib': int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:'))),
                 'wsl_distribution': os.getenv('WSL_DISTRO_NAME'), 'wsl_version': platform.release()},
        'llm': {'provider': 'Google Gemini / google_genai', 'model': 'gemini-3.1-flash-lite', 'temperature': 0, 'source': 'config/llm_config.py:get_llm'},
        'embedding': {'provider': 'local HuggingFace / sentence-transformers', 'model': 'all-MiniLM-L6-v2', 'source': 'vector_store/chroma_store.py:get_embed_model'},
        'documents': documents, 'protected_file_sha256': protected, 'python_file_sha256': python_files, 'isolated_runtime_directory': str(scratch),
        'app_command': [sys.executable, '-m', 'uvicorn', 'tender_iq.main:app', '--app-dir', str(root / 'src'), '--port', str(port)],
        'results_git_ignored': subprocess.run(['git', 'check-ignore', '-q', str(out)], cwd=root).returncode == 0,
        'retrieval_measurement': 'Skipped. API returns only first 3 snippets, not the full expanded-query retrieval. No app instrumentation or extra LLM retrieval probes.',
        'internal_sdk_retries': 'App and SDK defaults unchanged. Observable retry/rate-limit logs are recorded; retries not exposed in logs cannot be enumerated.',
        'status': 'running', 'scoring': 'auto, rule-based first pass; no LLM judge',
    }
    write_json('manifest.json', manifest)
    session = requests.Session()
    session.mount('http://', requests.adapters.HTTPAdapter(max_retries=0))
    def request(method, url, phase, **kwargs):
        started = time.perf_counter()
        entry = {'phase': phase, 'started_at': now(), 'status': None, 'error': ''}
        try:
            response = session.request(method, url, timeout=args.timeout, **kwargs)
            entry['status'] = response.status_code
            try:
                entry['body'] = response.json()
            except ValueError:
                entry['body'] = {'text': clean(response.text[:1000])}
            if not response.ok:
                entry['error'] = f'HTTP {response.status_code}: ' + clean(str(entry['body']))
        except requests.Timeout:
            entry['error'] = f'Timeout after {args.timeout:g}s; not retried.'
        except requests.RequestException as exc:
            entry['error'] = clean(type(exc).__name__ + ': ' + str(exc))
        entry['wall_seconds'] = time.perf_counter() - started
        entry['finished_at'] = now()
        events.append(entry)
        return entry
    def chat(tender, question, phase):
        return request('POST', base + '/api/v1/chat/', phase, json={'tender_id': tender, 'query': question})
    process = None
    cold = {}
    invalid = False
    fatal = ''
    fieldnames = ['id','tender','dataset','category','answerable','run','started_at','finished_at','http_status','wall_seconds','question','expected_answer','match_hint','hint_match','abstention_match','label','label_source','review_required','review_flags','error','observed_provider_events','answer','citations','evidence']
    try:
        start = time.perf_counter()
        process = subprocess.Popen(manifest['app_command'], cwd=scratch, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        def reader():
            with (out / 'api.log').open('w') as log_file:
                for line in process.stdout:
                    line = clean(line)
                    with lock:
                        logs.append(line)
                    log_file.write(now() + ' ' + line)
                    log_file.flush()
                    if 'Application startup complete' in line:
                        ready.set()
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        if not ready.wait(120):
            raise RuntimeError('API did not complete startup within 120s; not restarted.')
        cold['process_to_ready_seconds'] = time.perf_counter() - start
        first = request('GET', base + '/docs', 'cold_first_http_request')
        cold['first_http_request_seconds'] = first['wall_seconds']
        cold['process_start_to_first_http_response_seconds'] = time.perf_counter() - start
        if first['error']:
            raise RuntimeError(first['error'])
        ids = {}
        for document in documents:
            guard()
            started = time.perf_counter()
            with Path(document['pdf_path']).open('rb') as pdf:
                upload = request('POST', base + '/api/v1/tenders/upload', 'upload:' + document['tender'], files={'file': (Path(document['pdf_path']).name, pdf, 'application/pdf')})
            job = upload.get('body', {}).get('tender_id')
            item = {'pdf': document['pdf_path'], 'pages': document['pages'], 'tender': document['tender'], 'upload_request_seconds': upload['wall_seconds'], 'upload_http_status': upload['status'], 'job_id': job, 'error': upload['error']}
            final_status = None
            if job and not upload['error']:
                deadline = time.monotonic() + 600
                while time.monotonic() < deadline:
                    status = request('GET', base + f'/api/v1/tenders/{job}/specs', 'ingestion_poll:' + document['tender'])
                    final_status = status.get('body', {})
                    if status['error'] or final_status.get('status') in ('completed', 'failed'):
                        item['error'] = status['error'] or ('Ingestion failed' if final_status.get('status') == 'failed' else '')
                        break
                    time.sleep(.5)
                else:
                    item['error'] = 'Ingestion completion timeout after 600s; upload not retried.'
                item['final_status'] = final_status
            item['upload_to_completion_observed_seconds'] = time.perf_counter() - started
            item['ingestion_after_upload_observed_seconds'] = max(0, item['upload_to_completion_observed_seconds'] - upload['wall_seconds'])
            uploads.append(item)
            ids[document['tender']] = job or document['tender']
            print('INGEST', document['tender'], 'pages', item['pages'], 'seconds', round(item['upload_to_completion_observed_seconds'], 3), 'error', bool(item['error']), flush=True)
            write_json('manifest.json', dict(manifest, cold_start=cold, ingestion=uploads))
        for i in range(2):
            document = documents[i % len(documents)]
            result = chat(ids[document['tender']], 'What is the bid number?' if i == 0 else 'Which organisation issued this bid?', 'warmup:' + str(i+1))
            warmups.append(result)
            if i == 0:
                cold['first_chat_after_ingestion_seconds'] = result['wall_seconds']
            print('WARMUP', i+1, 'status', result['status'], 'seconds', round(result['wall_seconds'], 3), flush=True)
            time.sleep(args.pause)
        with csv_path.open('w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for run in range(1, args.runs+1):
                for question in questions:
                    guard()
                    with lock:
                        log_start = len(logs)
                    result = chat(ids[question['tender']], question['question'], f'question:{question["id"]}:run:{run}')
                    with lock:
                        relevant = ''.join(logs[log_start:])
                    provider_lines = [line.strip() for line in relevant.splitlines() if re.search(r'(?i)retrying|resource_exhausted|too many requests|quota exceeded|rate.?limit|429', line)]
                    error = result['error']
                    if provider_lines and not error:
                        error = 'Application/SDK retry or provider error observed during request; counted as failure even if HTTP succeeded.'
                    body = result.get('body', {})
                    answer = str(body.get('answer', '')) if isinstance(body, dict) else ''
                    if not error and not answer.strip():
                        error = 'Empty answer in successful response.'
                    label, hint, abstention, flags = score(question, answer, error)
                    row = {'id': question['id'], 'tender': question['tender'], 'dataset': question['dataset'], 'category': question['category'], 'answerable': question['answerable'], 'run': run, 'started_at': result['started_at'], 'finished_at': result['finished_at'], 'http_status': result['status'], 'wall_seconds': round(result['wall_seconds'], 6), 'question': question['question'], 'expected_answer': question['expected_answer'], 'match_hint': question.get('match_hint',''), 'hint_match': hint, 'abstention_match': abstention, 'label': label, 'label_source': 'auto', 'review_required': bool(flags), 'review_flags': flags, 'error': error, 'observed_provider_events': provider_lines, 'answer': clean(answer), 'citations': body.get('citations', []) if isinstance(body, dict) else [], 'evidence': question['evidence']}
                    rows.append(row)
                    written = {k: clean(json.dumps(v, ensure_ascii=False)) if isinstance(v, (list,dict)) else clean(str(v)) for k,v in row.items()}
                    writer.writerow(written)
                    file.flush()
                    print(f'RUN {run} {question["id"]} status={result["status"]} seconds={result["wall_seconds"]:.3f} label={label} error={bool(error)} [{len(rows)}/{len(questions)*args.runs}]', flush=True)
                    time.sleep(args.pause)
        guard()
    except Exception as exc:
        fatal = clean(str(exc))
        invalid = 'INVALID' in fatal
        print('STOP', fatal, flush=True)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
        session.close()
    def group(items):
        answerable = [r for r in items if r['answerable']]
        negatives = [r for r in items if not r['answerable']]
        return {'answerable': {'correct': sum(r['label']=='correct' for r in answerable), 'partial': sum(r['label']=='partial' for r in answerable), 'wrong': sum(r['label']=='wrong' for r in answerable), 'total': len(answerable)}, 'abstention': {'correct': sum(r['label']=='correct' for r in negatives), 'partial': sum(r['label']=='partial' for r in negatives), 'wrong': sum(r['label']=='wrong' for r in negatives), 'total': len(negatives)}}
    times = sorted(r['wall_seconds'] for r in rows)
    success_times = sorted(r['wall_seconds'] for r in rows if not r['error'])
    def latency(values):
        n = len(values)
        if not n:
            return {'n': 0, 'p95_reliable': False}
        result = {'n': n, 'median_seconds': statistics.median(values), 'min_seconds': values[0], 'max_seconds': values[-1], 'p95_reliable': n>=50}
        if n>=50:
            result['p95_seconds'] = values[max(0, __import__('math').ceil(.95*n)-1)]
        return result
    summary = {'status': 'invalid' if invalid else ('incomplete' if fatal else 'complete'), 'fatal_error': fatal, 'label_source': 'auto', 'distinct_verified_questions': len(questions), 'distinct_answerable_questions': sum(q['answerable'] for q in questions), 'distinct_not_found_questions': sum(not q['answerable'] for q in questions), 'planned_requests': len(questions)*args.runs, 'recorded_requests': len(rows), 'overall': group(rows), 'per_tender': {d['tender']: group([r for r in rows if r['tender']==d['tender']]) for d in documents}, 'per_category': {c: group([r for r in rows if r['category']==c]) for c in sorted({q['category'] for q in questions})}, 'per_pass': {str(i): group([r for r in rows if r['run']==i]) for i in range(1,args.runs+1)}, 'warm_request_latency_including_failed_attempts': latency(times), 'successful_warm_request_latency': latency(success_times), 'cold_start': cold, 'ingestion': uploads, 'question_request_error_count': sum(bool(r['error']) for r in rows), 'other_http_error_count': sum(bool(e['error']) for e in events if not e['phase'].startswith('question:')), 'ingestion_failure_count': sum(bool(u['error']) for u in uploads), 'timeout_count': sum('Timeout' in r['error'] for r in rows), 'http_429_count': sum(r['http_status']==429 for r in rows), 'requests_with_observed_provider_rate_limits': sum(any(re.search(r'(?i)resource_exhausted|too many requests|quota exceeded|rate.?limit|429', line) for line in r['observed_provider_events']) for r in rows), 'requests_with_observed_sdk_retry_logs': sum(any('retry' in x.lower() for x in r['observed_provider_events']) for r in rows), 'review_flagged_rows': sum(r['review_required'] for r in rows), 'retrieval_accuracy': None, 'p95_method': 'nearest-rank ceil(0.95*n)', 'warmups_excluded': 2, 'caveats': ['Dev set: parser fixes were made after viewing these PDFs (user-required disclosure). Earlier recorded parser regression checks used other PDFs; no claim of unseen-test independence.', 'Questions were written by the project author and reviewed by the project author; not an independent evaluation.', f'Small dev set: {len(questions)} distinct questions; three repeats are not independent questions.', 'Latency depends on provider and time of day, and measures the full external API request.', 'Automatic hint and numeric checks are provisional; all partial and doubtful cases require human review.', 'No LLM judge or weighted composite score.', 'API snippets are limited to first three sources; full retrieval accuracy is not measured.', 'SDK defaults are unchanged; hidden internal retries cannot be enumerated. Observable retries and provider errors count as failures.', 'Observed ingestion times include upload, processing and polling delay (0.5 second polling interval).', 'Fresh app and isolated empty storage; model download caches on this host are retained.']}
    manifest.update(status=summary['status'], finished_at=now(), cold_start=cold, ingestion=uploads, fatal_error=fatal, warmups=warmups, protected_files_unchanged=not invalid)
    write_json('manifest.json', manifest)
    write_json('summary.json', summary)
    write_json('request_events.json', events)
    write_json('warmups.json', warmups)
    def fraction(part):
        return f'{part["correct"]}/{part["total"]} correct; {part["partial"]} partial; {part["wrong"]} wrong'
    lines = ['# TenderIQ frozen API benchmark', '', f'Status: {summary["status"]}. Commit: {commit}. Frozen datasets: {freeze}.', '', 'All labels are **auto** first-pass labels, not human-confirmed accuracy. No LLM judge was used.', '', f'{len(questions)} distinct verified questions; {len(rows)} recorded scored requests across {args.runs} passes. {len(excluded)} unverified entries excluded.', '', '## Scores', '', 'Answerable requests: ' + fraction(summary['overall']['answerable']) + '.', 'Not-in-document abstention requests: ' + fraction(summary['overall']['abstention']) + '.', '', '| Tender | Answerable | Abstention |', '|---|---|---|']
    for tender, result in summary['per_tender'].items():
        lines.append(f'| {tender} | {fraction(result["answerable"])} | {fraction(result["abstention"])} |')
    lines += ['', '| Category | Answerable | Abstention |', '|---|---|---|']
    for category, result in summary['per_category'].items():
        lines.append(f'| {category} | {fraction(result["answerable"])} | {fraction(result["abstention"])} |')
    lines += ['', '| Pass (distinct questions per pass) | Answerable | Abstention |', '|---|---|---|']
    for number, result in summary['per_pass'].items():
        lines.append(f'| {number} | {fraction(result["answerable"])} | {fraction(result["abstention"])} |')
    lines += ['', '## Full-request latency', '', 'Two throwaway warmups and cold startup are excluded. Failed and timed-out scored requests are included in the main latency distribution. Repeats are reported as request-level observations.', '', json.dumps(summary['warm_request_latency_including_failed_attempts'], indent=2), '', 'Successful scored requests only:', '', json.dumps(summary['successful_warm_request_latency'], indent=2), '']
    if len(rows)<50:
        lines.append('n is below 50, so p95 is not reliable and is not reported.')
    lines += ['', '## Ingestion and cold start', '', '| PDF | Pages | Upload request seconds | Upload to observed completion seconds | Error |', '|---|---:|---:|---:|---|']
    for item in uploads:
        lines.append(f'| {Path(item["pdf"]).name} | {item["pages"]} | {item["upload_request_seconds"]:.6f} | {item["upload_to_completion_observed_seconds"]:.6f} | {item["error"] or "none"} |')
    lines += ['', json.dumps(cold, indent=2), '', f'Question-request errors: {summary["question_request_error_count"]}. Other HTTP errors: {summary["other_http_error_count"]}. Ingestion failures: {summary["ingestion_failure_count"]}.', f'Flagged scored rows: {summary["review_flagged_rows"]}. See CSV review_flags and failures.md. Every partial is flagged.', '', '## Limits', '']
    lines += ['- ' + caveat for caveat in summary['caveats']]
    if fatal:
        lines += ['', 'Fatal stop: ' + fatal, 'Incomplete or invalid results must not be used as final headline claims.']
    (out / 'summary.md').write_text(clean('\n'.join(lines)) + '\n')
    failures = ['# Wrong and partial answers', '', 'Every label below is auto. Context is limited to the citation snippets returned by the API; full retrieved context is unavailable. Cause statements are guesses, not verified diagnoses.', '']
    for row in rows:
        if row['label'] == 'correct':
            continue
        guess = 'Request or provider failure prevented a usable answer.' if row['error'] else ('A hint or formatting check may have missed a valid paraphrase, or retrieval/generation may have omitted a required fact. Full retrieval is unavailable, so these causes are not distinguished.')
        failures += [f'## {row["id"]}, pass {row["run"]}: {row["label"]} (auto)', '', 'Question: ' + row['question'], 'Expected: ' + row['expected_answer'], '', 'Answer:', '', row['answer'] or '(No answer returned)', '', 'API citation snippets:', '', '```json', json.dumps(row['citations'], ensure_ascii=False, indent=2), '```', '', 'Error: ' + (row['error'] or 'none'), 'Review flags: ' + '; '.join(row['review_flags']), '**Guess:** ' + guess, '']
    for event in events:
        if event['error'] and not event['phase'].startswith('question:'):
            failures += ['## Non-scored request error', '', event['phase'] + ': ' + event['error'], '']
    (out / 'failures.md').write_text(clean('\n'.join(failures)) + '\n')
    print('DONE', clean(json.dumps({'status': summary['status'], 'overall': summary['overall'], 'latency': summary['warm_request_latency_including_failed_attempts'], 'errors': summary['question_request_error_count'], 'flagged': summary['review_flagged_rows']})), flush=True)
    if fatal:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
