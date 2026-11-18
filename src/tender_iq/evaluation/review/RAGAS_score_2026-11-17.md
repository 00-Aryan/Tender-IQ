# RAGAS score audit — 17 November 2026

Source score report:
`ragas_scores_2026-11-17_21-32-36-082911.json`

Purpose: record a small human audit of unusual RAGAS outcomes.
This does not overwrite RAGAS results or change the dataset.

| Audit result | Meaning |
|---|---|
| Answer wrong and evidence missing | Retrieval or generation may need improvement |
| Answer wrong but evidence present | Generation/prompt may need improvement |
| Answer correct but evidence absent | Possible unsupported lucky answer; investigate |
| Answer correct and evidence present, but low faithfulness | Evaluator limitation or extraction-quality issue |
| Reference and PDF conflict | Dataset/reference needs a future version correction |

## T1-NEW-009

- RAGAS result: correctness `correct`; faithfulness `0.0`.
- Checked evidence: retrieved chunk 2 contains the MSE field with value `No`.
- Human audit: the answer matches the expected answer and direct evidence.
- Final audit decision: answer is correct and supported.
- Metric interpretation: faithfulness is a likely evaluator false negative.
- Follow-up: no RAG change; retain this as an evaluator limitation.

## T1-NEW-011

- RAGAS result: correctness `correct`; faithfulness `1.0`.
- Checked evidence: retrieved chunk 1 (page 3) contains the "Past Experience of Similar Services" clause stating the 40%, 50%, and 80% thresholds.
- Human audit: the answer matches the expected answer and direct evidence completely and accurately.
- Final audit decision: answer is correct and supported (positive control).
- Metric interpretation: correctness and faithfulness (1.0) both align with human audit and evidence ground truth.
- Follow-up: no RAG change; retain as an anchor positive control demonstrating clean retrieval, answer grounding, and evaluator alignment.

## T1-NEW-014

- RAGAS result: correctness `partial`; faithfulness `0.0`.
- Checked evidence: saved retrieved context contains both the single-vehicle group (2250 km) and the three-vehicle Bolero group (1995 km).
- Human audit: the question specifically asks for the monthly kilometres for the three-vehicle Bolero group. The answer correctly gives 1995 km. The judge treated 2250 km and 1995 km as a conflict in the response, conflating two different vehicle groups.
- Final audit decision: answer is correct and supported.
- Metric interpretation: RAGAS correctness `partial` is a likely judge error (the judge conflated two different vehicle groups); faithfulness `0.0` is a likely evaluator false negative.
- Follow-up: no application change from this case alone; retain as an evaluator limitation.

## T1-NEW-016

- RAGAS result: correctness `wrong`; faithfulness `0.0`.
- Checked evidence: relevant evidence across all three consignee tables was returned late in retrieval (e.g. chunk 19) and the saved context does not clearly provide all three required consignee tables near the top.
- Human audit: expected answer is 6 vehicles (1 Scorpio or equivalent, 3 Boleros in the second group, 2 Boleros in the third group). The saved answer says 3 vehicles (2 Scorpio, 1 Bolero), which is materially incorrect.
- Final audit decision: answer is wrong.
- Metric interpretation: evidence coverage was incomplete or poorly placed for a three-table question; retrieval ranking and generation both require investigation.
- Follow-up: investigate retrieval ranking (to ensure multi-table evidence appears near the top) and generation handling of multi-part tables.

## T2-NEW-007

- RAGAS result: correctness `wrong`; faithfulness `0.33`.
- Checked evidence: retrieved chunk 3 contains the explicit field values: MSE relaxation `No` and Startup relaxation `No`. The starred note about uploading exemption documents is conditional.
- Human audit: the document explicitly marks relaxation as `No`. The starred note does not convert either `No` field into an approved relaxation. The saved answer claims startup relaxation is granted, which is materially incorrect.
- Final audit decision: answer is wrong.
- Metric interpretation: RAGAS correctness `wrong` is reasonable; low faithfulness (`0.33`) is consistent with a false claim.
- Follow-up: investigate why the model preferred a generic conditional exemption note over the explicit `No` field value.

## T2-NEW-008

- RAGAS result: correctness `partial`; faithfulness `1.0`.
- Checked evidence: direct tender field "Document required from seller" lists `Certificate (Requested in ATC)`. Retrieved context also contains diffuse certificate clauses and ATC requirements across several pages.
- Human audit: the expected answer `Certificate (Requested in ATC)` is valid for the specific field queried. The saved answer gives a broad list of related documents and conditions rather than directly answering the specific field entry.
- Final audit decision: answer is partial (contains related information but misses the direct field entry).
- Metric interpretation: RAGAS correctness `partial` is appropriate. Faithfulness `1.0` reflects that statements made are grounded in retrieved context, but demonstrates that faithfulness does not measure answer focus, completeness, or direct responsiveness.
- Follow-up: prompt refinement to improve answer focus and directness for specific field queries.
