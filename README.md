# Hospital Invoice Auditor

**Nwoyr Alshahrani**

I audit synthetic hospital invoices against their contracts using deterministic Python rules. I use Hospital 1 for development evaluation and submit predictions for Hospitals 3 and 4. There are no runtime LLM calls, API keys, billed-price-based service mappings or labels in the audit engine.

## Current submission

| Hospital | Invoice records | Submitted | Flagged in submission | Omitted |
|---|---:|---:|---:|---:|
| H3 | 939 | 597 | 19 | 342 |
| H4 | 840 | 546 | 22 | 294 |
| Total | 1,779 | 1,143 | 41 | 636 |

My initial submission had 227 H4 invoices and 7 flags. Those rows retain their flags and monetary amounts in this revision. Increased coverage is not proof of increased accuracy: H3 and H4 have no supplied labels. H2 and H5 are not yet supported.

I submit only complete calculated totals under the documented interpretations. Findings on another 58 H3 and 45 H4 records remain in review because I cannot justify the full payable amount. I do not replace an unresolved expected amount with the billed total.

## Reproduce the submission

Use Python 3.10 or later. The audit and tests use only the standard library. They passed locally on Python 3.10 and in the preparation environment on Python 3.12.14.

```powershell
python -m unittest -v test_engine
python run.py --evaluate-h1
```

The default submission combines H3 and H4. `--evaluate-h1` adds labelled H1 development evaluation; H1 is never submitted. The command writes identical `submission.csv` files at the project root and under `results/`.

For a single hospital, use `python run.py --hospital 3` or `python run.py --hospital 4`. A single-hospital run replaces the submission with that selected scope; rerun the default command before submitting the combined file.

To audit fresh data under the same contracts, without loading H1 labels:

```powershell
python run.py --hospitals 3 4 --data-dir "C:\path\to\input" --output-dir "C:\path\to\results"
```

The input directory needs the selected hospitals' contract documents, nested invoice JSONL files and `submission_template.csv`. Outputs and service mappings are recomputed from these inputs, not loaded from committed per-invoice predictions. Missing required documents cause an explicit failure.

## Build the report

PDF generation is optional for running the audit. Close the PDF before overwriting it on Windows.

```powershell
python -m pip install -r requirements.txt
python build_report.py
```

The updated two-page evaluation and decision log is `reports/report.pdf`. The builder reads current `results/` evidence, checks the root submission against it and writes source hashes to `reports/report_sources.json`. It refuses to build this report from a single-hospital run or without H1 evaluation.

## Current files

- `audit.py`: H1/H3/H4 contract parsing, service mapping, findings and pricing.
- `vocabulary.py`: explicit abbreviation normalisation.
- `run.py`: orchestrates the selected hospitals and writes the combined submission.
- `evaluate.py`: opt-in H1 evaluation; never imported by the audit engine.
- `review_queue.py`: line-level reasons for unresolved flagged records.
- `test_engine.py`: 18 regression and contract-boundary tests.
- `build_report.py`: current two-page report and decision log.
- `results/hospital_N/`: current invoice, line and mapping evidence; review queues for H3/H4.
- `prompts/`: selected original technical material and explicitly labelled retrospective AI-assistance records.

Older `audit_bundles.py`, `audit_discounts.py`, `audit_total.py`, `build_submission.py`, `evaluate_h1.py`, `verify_selected.py`, `tests/test_checks.py` and `outputs/` belong to the first implementation. They are not called by the current runner and must not be combined with the current results. The old separate repricing verification applied to 227 initial rows, not all 1,143 current rows. Legacy reports, if retained for history, must not be presented as current verification.

Local `update.py` and `backup_before_update_*` folders are installation/history helpers, not dependencies of this repository. Do not upload those helpers or backups. A fresh clone should run with the commands above and without access to a Codex workspace.

## Development evaluation

On 908 H1 records with unambiguous identifiers, TP=52, FP=0, FN=1, TN=855; precision=1.000, recall=0.9811 and F1=0.9905. Ten reused-ID records are excluded. Complete amounts match the reference for 590 of 591 evaluated complete invoices.

These are development results after using H1 during iteration, not held-out calibration or H3/H4 accuracy. Per-category precision is lower for some categories. `results/hospital_1/category_metrics.csv` compares category names literally; generic amount/rate findings may differ from more specific reference categories. The report includes all category results and four systematic failure types.

## Contract decisions and uncertainty

I never select the first of multiple service candidates. Unique partial matches are exposed as inferences; unresolved services, units, dates and dependent adjustments remain reviewable. Confidence 0.40/0.60 is subjective and uncalibrated, with inference exposure propagated across patient context and global discount mappings.

For H3, I read the Base Agreement, Appendix B and Amendment No. 1 together. The seven revised rates take effect by service date on 1 January 2025; the two added services are non-billable before that date. Discounts do not reset at the amendment. No settlement-status evidence is supplied to apply the already-settled exception.

I apply bundle rates, premiums and discounts in contractual order with half-up cent rounding at each step. I defer exclusion endpoints, ambiguous compound units and duplicate allocation. The H1 cap/reference amount disagreement and the limits of the tests are explained in `reports/report.pdf` and `reports/decision_log.md`.

## AI assistance and time

I used Codex substantially for implementation, refactoring, testing, analysis and documentation. I supplied task materials and execution outputs, ran scripts and made scope decisions. The first submission recorded 6 hours 30 minutes of hands-on work. This invited revision adds work whose hands-on time I have not yet recorded separately. I do not present the revision as part of the original time entry.

With another week, I would validate inferred mappings, resolve contractual ambiguities, investigate the private generalisation failure, evaluate full-row confidence on a held-out set and extend hospital coverage.
