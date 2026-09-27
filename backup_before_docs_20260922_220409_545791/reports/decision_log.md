# Decision log

## Scope and sequencing

Develop on labelled H1, then implement H4 rules. Earlier H3/H5 exploration was set aside. The final package executes only H1/H4. A complete computed total is required for submission; incomplete totals are not replaced with subtotals.

## Identity and amounts

Use nested JSONL record IDs to preserve parentage. Reused invoice IDs and unresolved duplicate allocations prevent selected totals. Money remains integer cents, with Decimal and half-up rounding. Any selected amount difference is explicitly labelled recomputed_total_mismatch in addition to existing findings.

## Mapping and reviewed inference

Abbreviations and compatible contract terms identify services without using billed prices or labels. Four H4 descriptions omit a qualifier but retain specialty and service terms; each has one compatible contractual candidate and is tagged mapped_reviewed_inference. 30 selected invoices contain these mappings. Uniqueness within the contract is an assumption, not proof that an unknown service could not have a similar description.

## Daily groups and exclusions

Daily quantities aggregate by patient, service and date across records. A known candidate list that excludes the current service does not block its daily count; an unclassified description with no candidates still does. Exclusion-trigger services are distinguished from the services being excluded. Exact window boundaries are withheld for review. This reading is deliberately unresolved rather than a claim that contract boundaries are exclusive.

## Utilisation and duplicate charges

Discounts use prior utilisation, strict threshold exceedance and service-date/line-ID ordering. Lower/upper bounds must agree before pricing; this conservatism depends on the candidate vocabulary. Repeated services on a patient-day generate review evidence without automatically retaining or removing any charge.

## Confidence and calibration

The confidence field concerns row correctness, including the amount. Values are subjective and uncalibrated: 0.60 for complete calculations without identified patient-level inference exposure, 0.40 when an inferred mapping appears anywhere in the same patient's records. 106 selected rows receive the latter value. Same-patient exposure is conservative, not an exact dependency proof. Global utilisation or unidentified mapping risk can remain. These values are not derived from H1 precision; calibration is unfinished and a material limitation.

## AI assistance and prompt history

An AI assistant substantially wrote and revised code, tests, mappings and report prose; the candidate supplied context and ran scripts interactively. No LLM/API is called at runtime. prompts/ contains selected authentic user requests, dated source snapshots and a retrospective change record; it is not an exhaustive original transcript. Git commits created during final packaging are not presented as contemporaneous development history.

## Time and next steps

Candidate-reported hands-on time at final packaging: 6 hours 30 minutes. Subsequent review time is not automatically tracked. With another week: validate inferred mappings and unresolved units, implement comparable H1 pricing to evaluate full-row confidence, test independent invoice-level calibration, resolve boundary clauses with the task owner, and extend hospital coverage. No claim of full H4 coverage is made.
