# Hospital Invoice Auditor

**Author:** Nwoyr Alshahrani  

I audit synthetic hospital invoices against their contracts using deterministic Python rules. I use Hospital 1 for development evaluation and submit predictions for Hospitals 3 and 4. There are no runtime LLM calls, API keys, billed-price-based service mappings or labels in the audit engine.

---

## Current Submission Summary

| Hospital | Records Submitted | Flagged in Submission | Omitted |
| :--- | :---: | :---: | :---: |
| **H3** | 939 | 597 | 19 |
| **H4** | 840 | 546 | 222 |
| **Total** | **1,779** | **1,143** | **241** |

> **Note:** My initial submission had 227 H4 invoices and 7 flags. Those rows retain their flags and monetary amounts in this revision. Increased coverage is not proof of increased accuracy: H3 and H4 have no supplied labels. H2 and H5 are not yet supported.

I submit only complete calculated totals under the documented interpretations. Findings on another 58 H3 and 45 H4 records remain in review because I cannot justify the full payable amount. I do not replace an unresolved expected amount with the billed total.

---

## Reproduce the Submission

Use **Python 3.10 or later**. The audit and tests use only the standard library. They passed locally on Python 3.10 and in the preparation environment on Python 3.12.14.

```bash
# Run test suite
python -m unittest -v test_engine

# Evaluate H1 and generate combined submission
python run.py --evaluate-h1

The default submission combines H3 and H4. --evaluate-h1 adds labelled H1 development evaluation; H1 is never submitted. The command writes identical submission.csv files at the project root and under results/.

For a single hospital, use python run.py --hospital 3 or python run.py --hospital 4. A single-hospital run replaces the submission with that selected scope; rerun the default command before submitting the combined file.

Audit Fresh Data Under Same Contracts:
python run.py --hospitals 3 4 --data-dir "C:\path\to\input" --output-dir "C:\path\to\results"

The input directory needs the selected hospitals' contract documents, nested invoice JSONL files, and submission_template.csv. Outputs and service mappings are recomputed from these inputs, not loaded from committed per-invoice predictions. Missing required documents cause an explicit failure.

Build the Report
PDF generation is optional for running the audit. Close the PDF before overwriting it on Windows.

python -m pip install -r requirements.txt
python build_report.py

The updated two-page evaluation and decision log is reports/report.pdf. The builder reads current results/ evidence, checks the root submission against it, and writes source hashes to reports/report_sources.json. It refuses to build this report from a single-hospital run or without H1 evaluation.

Repository Structure
audit.py: H1/H3/H4 contract parsing, service mapping, findings, and pricing.

vocabulary.py: Explicit abbreviation normalisation.

run.py: Orchestrates the selected hospitals and writes the combined submission.

evaluate.py: Opt-in H1 evaluation; never imported by the audit engine.

review_queue.py: Line-level reasons for unresolved flagged records.

test_engine.py: 18 regression and contract-boundary tests.

build_report.py: Current two-page report and decision log.

results/hospital_N/: Current invoice, line, and mapping evidence; review queues for H3/H4.

prompts/: Selected original technical material and explicitly labelled retrospective AI-assistance records.

Clean Setup Note: Local update.py and backup_before_update_* folders are installation/history helpers and are excluded from this repository. A fresh clone runs with the standard commands above.

Development Evaluation (H1)
On 908 H1 records with unambiguous identifiers:

Metrics: TP=52, FP=0, FN=1, TN=855

Precision: 1.000 | Recall: 0.9811 | F1 Score: 0.9905

Ten reused-ID records are excluded. Complete amounts match the reference for 590 of 591 evaluated complete invoices.

These are development results after using H1 during iteration, not held-out calibration or H3/H4 accuracy. Per-category precision is lower for some categories. results/hospital_1/category_metrics.csv compares category names literally; generic amount/rate findings may differ from more specific reference categories. The report includes all category results and four systematic failure types.

Contract Decisions & Uncertainty
No Blind First-Matches: I never select the first of multiple service candidates. Unique partial matches are exposed as inferences; unresolved services, units, dates, and dependent adjustments remain reviewable. Confidence (0.40/0.60) is subjective and uncalibrated, with inference exposure propagated across patient context and global discount mappings.

H3 Rules: I read the Base Agreement, Appendix B, and Amendment No. 1 together. The seven revised rates take effect by service date on 1 January 2025; the two added services are non-billable before that date. Discounts do not reset at the amendment. No settlement-status evidence is supplied to apply the already-settled exception.

Calculations: I apply bundle rates, premiums, and discounts in contractual order with half-up cent rounding at each step. I defer exclusion endpoints, ambiguous compound units, and duplicate allocation. The H1 cap/reference amount disagreement and limits of tests are explained in reports/report.pdf and reports/decision_log.md.

AI Assistance & Future Scope
I used Codex substantially for implementation, refactoring, testing, analysis, and documentation while supplying task materials, execution outputs, and making scope decisions. The first submission recorded 6 hours 30 minutes of hands-on work.

Future Enhancements:

Validate inferred mappings & resolve contractual ambiguities.

Investigate private generalisation failure.

Evaluate full-row confidence on a held-out set.

Extend hospital coverage (H2 & H5 support).