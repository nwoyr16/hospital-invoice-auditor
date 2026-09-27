# Pricing review of flagged records

I reviewed 45 flagged records whose payable totals are incomplete. Counts below overlap: one invoice may have several blockers.

| Blocker | Records | Required resolution |
|---|---:|---|
| unresolved_service_mapping | 20 | Resolve the service from clinical/billing description evidence, not its billed price. An unlisted description has no established payable rate. |
| unit_conversion_unresolved | 11 | Confirm the quantity on the contractual unit basis; do not assume a change of unit label leaves quantity unchanged. |
| ambiguous_invoice_identifier | 10 | Identify the intended record for each reused invoice ID; the submission key cannot distinguish both records. |
| ambiguous_contract_unit | 8 | Clarify whether "per hour, per item" means item-hours, alternative rates, or separate quantities, and what the supplied quantity measures. |
| possible_unresolved_same_day_service | 8 | Resolve possible same-patient/service/day occurrences before certifying a complete payable total. |
| exclusion_trigger_unresolved | 7 | Resolve possible trigger-service delivery and dates in the exclusion window. |
| premium_quantity_unresolved | 7 | Resolve all contributing quantities, mappings and dates for the patient/service/day. |
| invalid_service_date | 6 | Obtain the valid service date. Do not substitute the invoice or admission date. |
| bundle_partner_unresolved | 5 | Resolve possible partner-service delivery for this patient and day. |
| daily_quantity_unresolved | 5 | Resolve all contributing quantities, mappings and dates for the patient/service/day. |
| duplicate_service_allocation_unresolved | 5 | Confirm duplicate ownership and allocation; a deterministic sorting convention does not establish which charge is payable. |
| exclusion_boundary_unresolved | 5 | Clarify whether exactly N calendar days is inside the exclusion window. |
| out_of_term_date | 5 | Confirm applicable contractual authority or corrected date for the out-of-term service. |
| discount_utilisation_unresolved | 2 | Resolve the service identity, quantity or date affecting cumulative utilisation; current lower and upper bounds select different discounts. |

The queue retains all findings without adding fabricated amounts to the submission. The evidence CSV includes line descriptions, mapping candidates, dates and the required resolution. A known-line subtotal must not be submitted as a full expected total.

## Questions requiring task-owner clarification

1. May an invoice with a proven error but an unresolved payable amount be submitted with a blank expected_total_cents? If so, how should confidence represent that incomplete row?
2. For services stated as "per hour, per item", does this mean a single item-hour unit, and is quantity already the number of item-hours?
3. Does "within N days" include exactly N days? How should repeated invoice identifiers be represented in the single-ID submission schema?

These questions have not been sent to the task owner. Current output assumes no permission to submit missing amounts.
