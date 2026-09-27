# My revision decision log

## Contract interpretation and scope

I added H3 by reading its Base Agreement, Appendix B and Amendment No. 1. I apply the seven amended rates by service date from 1 January 2025 and treat the two newly introduced services as non-billable before that date. Discounts continue across the amendment. I have no settlement-status evidence to apply the already-settled-invoice exception. I retained H4 rules and amounts; I did not reuse its rules for other contracts.

## Failure type 1: ambiguous service identity

I retain multiple textual candidates for review and expose unique partial matches as inferences. I never choose the first candidate merely to increase coverage. H1 INV-H1-000657 is the remaining wholly missed erroneous invoice: an unresolved description prevents a reliable unit comparison. Broader mapping can improve coverage but needs independent semantic review.

## Failure type 2: a finding without a complete amount

I retain findings on 58 H3 and 45 H4 records outside the submission because their totals remain unresolved. For example, H4 INV-H4-000003 has a unit mismatch with no justified quantity conversion. I do not copy billed amounts into the expected field. Detailed queues identify the affected lines and required resolution.

## Failure type 3: boundaries and allocation

I defer exact exclusion-window endpoints and duplicate-charge allocation. H4 INV-H4-000235 has an exclusion-boundary blocker; H1 exclusion detection still misses three labelled cases. I use invoice date and identifiers only to order candidate duplicate occurrences, not to certify the payable allocation. Reused invoice IDs are not collapsed into a guessed submission record.

## Failure type 4: correct rule, differing reference amount

For H1 INV-H1-000015, the line bills 9 tests and the contract caps payment at 4. My invoice total is 1,210,600 cents; the reference is 1,195,825 cents, one test lower. I preserve the general cap rule and report the disagreement instead of fitting an invoice-specific exception.

## Confidence and validation

My confidence values of 0.40/0.60 are subjective and uncalibrated. I mark same-patient mapping inference and global discount mapping exposure. I passed 18 tests, including adjustment thresholds, amendment dates, cross-invoice bundles, raw-input shuffling, and combined H3/H4 output without H1 labels. These tests do not validate every mapping, resolve the private generalisation failure, or establish an updated leaderboard score. The previous separate repricing check covered the original 227 rows only.

## AI assistance, time and another week

I used Codex substantially for code, debugging, tests, analysis and documentation; I supplied inputs, ran scripts and chose scope. My first submission recorded 6 hours 30 minutes of hands-on work. This invited revision adds time that I have not yet recorded separately. With another week, I would validate inferred mappings, clarify units and exclusion boundaries, obtain the failed generalisation traceback, calibrate full-row correctness on a held-out set and extend coverage to another contract.
