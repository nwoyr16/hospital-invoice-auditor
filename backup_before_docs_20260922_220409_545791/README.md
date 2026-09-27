# Insurance Invoice Audit

**Nwoyr Alshahrani**

I developed a rules-based pipeline to audit synthetic hospital invoices against their service contracts. I used Hospital 1 for development and evaluation, and focused my final predictions on Hospital 4.

My approach prioritises traceable calculations and explicit uncertainty. I submit a prediction only when my implementation can calculate the complete invoice total under its documented rules and assumptions. A complete calculation does not guarantee that every service interpretation is correct.

## Scope and results

| Hospital | Role | Result |
| --- | --- | --- |
| Hospital 1 | Development and evaluation | 908 invoices evaluated; 10 records excluded because their invoice IDs are ambiguous |
| Hospital 4 | Final prediction scope | 227 predictions from 840 invoice records |

The Hospital 4 submission contains **7 flagged and 220 unflagged invoices**. Five calculated totals differ from the billed totals; other findings include date violations. I withheld 613 records because their complete pricing remains unresolved. Complete-total coverage is **27.02%**, not an accuracy estimate.

I set aside earlier exploration of Hospitals 3 and 5 to concentrate on Hospital 4. Hospitals 2, 3 and 5 are outside the final prediction scope.

## Reproduce my results

Keep the project files, contracts, invoices and labels together. The final pinned package was verified with Python 3.12.14. Some of my interactive development runs used Python 3.10; use Python 3.11 or later for the pinned dependencies below.

On Windows, with a compatible Python version available through the `py` launcher:

```powershell
.\run_audit.cmd
```

The launcher creates a local `.venv`, installs the pinned dependencies and runs the pipeline. Initial dependency installation requires internet access. No API key is required.

Alternatively, with a compatible Python interpreter:

```powershell
python -m pip install -r requirements.txt
python run.py
```

`run.py` executes the stages sequentially and stops if a stage fails. Close generated CSV files and `reports/report.pdf` before running, as open files may prevent replacement on Windows. A successful run ends with `PASS` and `DONE: submission.csv and reports/report.pdf`.

The scripts resolve paths relative to the project files. Generated outputs are replaced on rerun; source inputs are not modified.

## How the audit works

1. **Preserve invoice identity.** I read nested JSONL records and assign a local `record_id` so repeated invoice IDs do not create ambiguous line-item joins.
2. **Match services.** I expand explicit abbreviations and compare descriptions with contract service names. I do not use billed prices or reference labels to select a service.
3. **Apply contractual checks.** I check arithmetic, dates, units and applicable rates. Hospital 4 also includes daily quantity limits, quantity premiums, bundle pricing, cumulative discounts, exclusion windows and duplicate-service review.
4. **Calculate complete totals.** Amounts use integer cents and Decimal arithmetic, with half-up rounding after each applicable adjustment. Unresolved mappings or pricing rules prevent an invoice from entering the final selection.
5. **Export and verify.** I export the required submission columns and validate identifiers, integer amounts, flags and confidence bounds. Any calculated total differing from the billed amount is explicitly recorded as `recomputed_total_mismatch`.

## Evaluation on Hospital 1

| Metric | Result |
| --- | ---: |
| True positives | 35 |
| False positives | 0 |
| False negatives | 18 |
| True negatives | 855 |
| Precision | 100.00% |
| Recall | 66.04% |
| F1 | 79.55% |
| Accuracy | 98.02% |

These are **development results**, not held-out validation or measured Hospital 4 accuracy. A negative means that the implemented checks found no error; it does not mean that every contractual rule was checked. The high accuracy reflects the predominantly correct invoice population.

Per-category results, including unsupported categories, are in `outputs/hospital_1/all_category_metrics.csv`. Category names are compared literally. In particular, `weekend_rate_mismatch` has no identically named reference category, so that result needs interpretation rather than being treated as evidence that both weekend findings are wrong.

My report groups limitations into service identification, pricing coverage, daily aggregation and relationships across records, with an example of each. The false-negative detail file contains all lines from wholly missed invoices, not only confirmed erroneous lines.

## Verification of selected Hospital 4 invoices

`verify_selected.py` separately parses the contract and raw JSONL and recalculates all **227 selected invoices and 2,347 lines**, without importing the pipeline's pricing functions. The current run has **zero disagreements** in invoice totals or invoice flags.

This provides an additional calculation check, but it uses the same saved service mappings and candidate vocabulary. It is not an external independent audit and does not prove the semantic correctness of the mappings or shared contract interpretations.

## Uncertainty and confidence

Four descriptions have reviewed, unique-candidate mappings that omit part of the contractual name. I mark them as `mapped_reviewed_inference`. Thirty selected invoices contain these mappings directly. I also track exposure across records for the same patient, which affects 106 selected invoices.

The confidence values in `submission_config.json` are **subjective and uncalibrated**:

- **0.60:** complete calculation without identified patient-level mapping-inference exposure.
- **0.40:** an inferred mapping occurs in the same patient's records.

These are not fitted probabilities and are not derived from Hospital 1 precision. Patient-level exposure is a precautionary grouping, not an exact dependency proof; other mapping and utilisation risks remain. Empirical calibration of complete-row correctness is an unfinished part of my solution.

I leave exact exclusion-window boundaries and duplicate-charge allocation unresolved. Unmatched services are not automatically declared invalid, and absence of a finding is not clearance. The decision log records these choices.

## Files to review

| File or folder | Purpose |
| --- | --- |
| `submission.csv` | Final predictions in the supplied six-column format |
| `reports/report.pdf` | Two pages: evaluation and a one-page decision log |
| `reports/submission_evidence.csv` | Line IDs and confidence basis for each submitted invoice |
| `reports/abstentions.csv` | Omitted records and unresolved pricing reasons |
| `reports/separate_repricing_lines.csv` | Evidence from the separate calculation check |
| `outputs/hospital_1/` | Development evaluation and error analysis |
| `outputs/hospital_4/` | Mapping, rule checks and pricing evidence |
| `prompts/` | Selected actual requests, supplied code snapshots and an assistance record |
| `tests/test_checks.py` | Regression tests for thresholds, aggregation, uncertainty, money and output validation |
| `requirements.txt` | Pinned dependencies |

## AI assistance

I used an AI assistant extensively to develop this solution. It substantially contributed to code generation and revision, abbreviation mappings, debugging, tests, analysis and report drafting. I supplied the task context and execution outputs, made scope decisions, and ran the scripts interactively.

The delivered program is rules-based and does not call an LLM at runtime. The records in `prompts/` are selected actual requests and iteration snapshots, with retrospective context clearly identified. They are not a complete transcript. Git commits created during packaging do not represent the original timing of every development step.

## Time and further work

My reported hands-on effort is **6 hours 30 minutes**. Any subsequent work should be added to that total; time was not automatically tracked.

With another week, I would review the inferred mappings and unresolved units, implement comparable pricing checks on Hospital 1 to evaluate complete-row correctness, assess confidence calibration on data not used for development, clarify ambiguous exclusion boundaries, and expand hospital coverage.

My final submission is deliberately partial. I document what remains unresolved rather than filling incomplete invoice totals with guessed amounts.
