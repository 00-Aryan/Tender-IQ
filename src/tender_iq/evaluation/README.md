# Evaluation: start here

The working flow is **questions → captured answers/evidence → RAGAS scores**.

```text
evaluation/
├── dataset_v1.json          # The 48 reviewed questions and expected answers
├── dataset.py               # Shared dataset reader and validation
├── capture_evidence.py      # Ask the real RAG and save its evidence
├── evaluate.py              # Score answers with RAGAS or evaluate offline Precision@5
├── retrieval_labels_v1.json # Human relevance judgments for top-5 retrieved chunks
├── captures/                # Raw answers, context, timings and failures
│   └── initial_2026-10-31.json
├── scores/                  # RAGAS and retrieval relevance scoring reports
└── review/                  # Audit records and metric analysis reports
```

`__init__.py` is Python's package marker. The two runnable commands are capture
and evaluate; `dataset.py` is their shared helper.

## Which file do I edit?

**Questions and expected answers belong in the versioned dataset.** It contains
only reviewed cases. Do not copy model answers or old human labels into it.

| Case field | Purpose |
|---|---|
| `id` | Match the same question across runs |
| `tender_id` | Select its document from `documents` |
| `question` | What we ask the RAG |
| `expected_answer` | The checked reference, used by the correctness rubric |
| `answerable` | Distinguish answerable questions from checked missing-information cases |
| `evidence` | Physical PDF pages and section names for checking the reference |

The top-level `documents` map stores each PDF path and hash once. Dataset version
identifies the reviewed question set; schema version identifies its JSON structure.

Removed fields: `user_input`, `response`, supplied `retrieved_contexts`, duplicate
`tender`, `match_hint`, `source`, `verified`, unused category and repeated PDF names.
The dataset's membership means reviewed; draft and legacy cases remain in the archive.

Once a dataset has captures, preserve its bytes. For new questions or reference
corrections, create `dataset_v2.json` and collect a matching capture. The scorer
rejects old captures against a different dataset hash.

## What do we already have?

`captures/initial_2026-10-31.json` consolidates the 48 selected successful answers
from three earlier runs. Their answers, chunks, overview, prompts and timings are
unchanged. It retains the 39 earlier failed attempts and source-file hashes.
It is a development collection of eventual successes, not 48 successful first attempts.

There is no approved RAGAS baseline yet. Historical custom-judge labels are not
RAGAS scores and do not appear in `scores/`.

## What do I run now?

From the repository root:

```bash
# Validate the current dataset and capture, without model calls.
uv run python -m tender_iq.evaluation.evaluate

# Score four saved answers: paid judge calls, no new RAG generation.
uv run python -m tender_iq.evaluation.evaluate --score
```

After inspecting the sample, `--all --score` scores all successful captured answers.
Two metrics run separately: your correctness/abstention rubric through RAGAS
`DiscreteMetric`, and built-in `Faithfulness`. Failures have separate denominators.
Faithfulness may be undefined for a claim-free abstention; it is not silently zero.
Each question normally makes one rubric call and two faithfulness calls.

To score a later collection, explicitly select it:

```bash
uv run python -m tender_iq.evaluation.evaluate \
  --dataset src/tender_iq/evaluation/dataset_v1.json \
  --capture src/tender_iq/evaluation/captures/evidence_YOUR_RUN.json \
  --score
```

Collect a new answer only when needed, using an existing completed upload:

```bash
uv run python -m tender_iq.evaluation.capture_evidence \
  --question-id T1-NEW-011 --document-id JOB-B292154D
```

Upload IDs are local to your database. Capture calls the same RAG chain directly;
the API server need not be running. For two documents, use repeated
`--document-map TENDER_ID=UPLOAD_ID` options. Run `--help` for selection and pacing.

## Where did the older files go?

They are preserved in `archive/evaluation_2026-10-31/` at the repository root:
the CSV human reviews, original JSON datasets, individual result files, old scripts,
separate manifest and older evaluation learning notes. The archive retains their
original relative directory structure so old manifest references can be resolved.

The current commands do not depend on the archive. There is no compatibility
wrapper or separate active CSV review pipeline. Captures and scores are generated
locally and ignored by Git; the dataset, code and fixture-based tests can be tracked.

Architecture: [evaluation flow](../../../docs/architecture/05_evaluation.md).
