# Retrieval Relevance Audit: Precision@5 over Saved Retrieval-Union Order — 18 November 2026

**Source files & reports:**
- Capture: `initial_2026-10-31.json` (`d2a04afa16959c785a3301a766461c24f2f19044e147906b8406b3745d68bcef`)
- Dataset: `dataset_v1.json` (`9b467106f97b6df8e62337f24379773ce93dd9f564334784985c1a45f373ff69`)
- Labels: `retrieval_labels_v1.json` (`e1fa73292be0445a071d6b6d84e3eca8d4b8cf22ff33d76a58ba1159c91b1e3e`)
- Score report: `retrieval_scores_2026-11-18_17-06-11-033268.json`
- RAGAS score report: `ragas_scores_2026-11-17_21-32-36-082911.json`

---

## 1. Metric Definition & Frozen Rules

| Rule Field | Decision |
|---|---|
| **Metric Name** | Precision@5 over saved retrieval-union order |
| **Included Cases** | 38 answerable cases (`answerable: true`) |
| **Excluded Cases** | 10 missing-information cases (`answerable: false`) |
| **Unit of Evaluation** | One retrieved chunk |
| **Relevant** | Directly supports at least one required part of the expected answer |
| **Not Relevant** | Does not support a required component, even if about the same tender |
| **Overview Policy** | Excluded from retrieval ranking (injected into generation context, not a ranked chunk) |
| **Denominator** | 5 for every included case (190 total decisions) |

---

## 2. Five-Case Trial Calibration

Before labeling all 38 cases, a 5-case calibration trial was conducted:

| Case | Expected Answer | Pos 1–5 Judgments | P@5 | Trial Notes |
|---|---|---|---|---|
| **T1-NEW-009** | MSE relaxation for experience & turnover is No | `[F, T, F, F, F]` | **0.20** | Pos 2 directly states `MSE Relaxation... No`. Others cover general past experience, TReDS, security deposit. |
| **T1-NEW-011** | Completed service thresholds: 40%, 50%, 80% | `[T, F, F, F, F]` | **0.20** | Pos 1 explicitly details 40%, 50%, and 80% thresholds under Clause 4. Pos 2 mentions requirement generally without thresholds. |
| **T1-NEW-016** | 6 vehicles: 1 Scorpio, 3 Boleros (group 2), 2 Boleros (group 3) | `[F, T, F, F, F]` | **0.20** | Pos 2 contains Scorpio heading with quantity `( 1 )`. Bolero group tables (pages 7–8) appear late (e.g. chunk 19+). |
| **T2-NEW-007** | Neither MSE nor Startup relaxation granted (No) | `[F, F, T, F, F]` | **0.20** | Pos 3 directly contains `Startup Relaxation... No` and `MSE Relaxation... No`. Pos 1–2 cover MSE price matching and option clause. |
| **T2-NEW-008** | Document required: Certificate (Requested in ATC) | `[T, F, F, F, F]` | **0.20** | Pos 1 directly contains `Document required from seller: Certificate (Requested in ATC)`. Pos 2–5 are general contract/wage clauses. |

---

## 3. Overall Precision@5 Results

Across all 38 answerable cases (190 evaluated chunks):

- **Mean Precision@5:** `0.1684` (**16.84%**)
- **Score Distribution:**
  - `P@5 = 0.00`: **13 cases** (34.2%)
  - `P@5 = 0.20`: **18 cases** (47.4%)
  - `P@5 = 0.40`: **7 cases** (18.4%)
  - `P@5 ≥ 0.60`: **0 cases** (0.0%)

---

## 4. Cross-Analysis with RAGAS Correctness

Cross-tabulating retrieval Precision@5 with RAGAS categorical correctness reveals distinct operational patterns:

RAGAS correctness labels are model-generated rather than human-confirmed. Read this
table alongside the [RAGAS audit](RAGAS_score_2026-11-17.md), which records known
judge limitations for selected cases.

| Correctness | Cases | Mean P@5 | P@5 = 0.00 | P@5 = 0.20 | P@5 = 0.40 |
|---|---|---|---|---|---|
| **Correct** | 26 | **0.1385** | 12 | 10 | 4 |
| **Partial** | 10 | **0.2400** | 1 | 6 | 3 |
| **Wrong** | 2 | **0.2000** | 0 | 2 | 0 |

### Observed patterns in this captured run

1. **Correct Answer + Low Precision@5 (12 cases with P@5 = 0.00):**
   - Cases: `T1-NEW-001`, `T1-NEW-002`, `T1-NEW-003`, `T1-NEW-005`, `T1-NEW-008`, `T1-NEW-019`, `T2-NEW-001`, `T2-NEW-002`, `T2-NEW-003`, `T2-NEW-004`, `T2-NEW-005`, `T2-NEW-016`.
   - *Meaning:* The first five chunks contained no directly supporting evidence under this relevance rule. The application nevertheless supplies all 12–28 saved chunks and the structured overview to generation. The answer may have been supported by later evidence or the overview; this metric does not reveal which context the model used.

2. **Partial Answer + Low/Moderate Precision@5:**
   - *Low P@5 (`T1-NEW-015`, P@5 = 0.00):* The question required 2500 km and 36 months for the 2-vehicle Bolero group. Relevant evidence appears late in the saved union, while early chunks describe other vehicle tables. This is consistent with, but does not prove, a retrieval contribution to the partial response.
   - *Moderate P@5 (e.g. `T1-NEW-014`, `T2-NEW-008`, `T2-NEW-010`):* Evidence was present in the first five chunks (P@5 = 0.20–0.40), while the response or judge still had an issue. These cases require answer-generation or evaluator review in addition to retrieval measurement.

3. **Wrong Answer + Low/Moderate Precision@5:**
   - *`T1-NEW-016` (P@5 = 0.20):* Required multi-table synthesis across three separate consignee tables. Only one required part appeared in the first five positions; the remaining tables appeared later. The answer was wrong, and both retrieval placement and multi-part generation remain possible contributors.
   - *`T2-NEW-007` (P@5 = 0.20):* The explicit `No` field was retrieved at position 3, but the response said startup relaxation was granted. This is evidence that retrieval alone is not enough; the generation path also needs attention.

---

## 5. Conclusions for Sprint 3

1. **Early evidence placement is weak in this captured run:** 34.2% of answerable questions have zero relevant evidence in the first five chunks. The saved union often places generic clauses ahead of field-specific tables and bid details.
2. **The application uses a wider context than this metric measures:** all 12–28 saved chunks and the structured overview are sent to generation. Therefore, Precision@5 measures early placement only; it does not measure whether useful evidence exists later in the prompt.
3. **Separate the next diagnosis by component:** low Precision@5 with a wrong answer is a retrieval-investigation candidate; high or moderate Precision@5 with a wrong or partial answer requires generation or prompt review too. No component change is approved by this report alone.
