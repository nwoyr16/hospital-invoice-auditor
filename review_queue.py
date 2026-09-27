"""Build a review queue without promoting unresolved payable amounts."""
from collections import Counter, defaultdict
import json
from audit import write_csv


REASONS = {
    'ambiguous_invoice_identifier': ('identifier', 'Contract section 11',
        'Identify the intended record for each reused invoice ID; the submission key cannot distinguish both records.'),
    'unit_conversion_unresolved': ('unit', 'H4 sections 1.3, 3 and 4.4',
        'Confirm the quantity on the contractual unit basis; do not assume a change of unit label leaves quantity unchanged.'),
    'ambiguous_contract_unit': ('compound_unit', 'H4 sections 1.3, 3 and 4.4',
        'Clarify whether "per hour, per item" means item-hours, alternative rates, or separate quantities, and what the supplied quantity measures.'),
    'unresolved_service_mapping': ('mapping', 'Contract service schedule',
        'Resolve the service from clinical/billing description evidence, not its billed price. An unlisted description has no established payable rate.'),
    'invalid_service_date': ('date', 'Contract section 11',
        'Obtain the valid service date. Do not substitute the invoice or admission date.'),
    'out_of_term_date': ('date', 'Contract term and section 11',
        'Confirm applicable contractual authority or corrected date for the out-of-term service.'),
    'exclusion_boundary_unresolved': ('boundary', 'H4 section 9; H1 section 10',
        'Clarify whether exactly N calendar days is inside the exclusion window.'),
    'duplicate_service_allocation_unresolved': ('allocation', 'Contract section 11',
        'Confirm duplicate ownership and allocation; a deterministic sorting convention does not establish which charge is payable.'),
    'cap_allocation_unresolved': ('allocation', 'Contract daily quantity caps',
        'Allocate the payable capped quantity across contributing lines and records.'),
    'discount_utilisation_unresolved': ('dependency', 'H4 section 8; H1 section 7',
        'Resolve the service identity, quantity or date affecting cumulative utilisation; current lower and upper bounds select different discounts.'),
    'bundle_partner_unresolved': ('dependency', 'H4 section 7; H1 section 9',
        'Resolve possible partner-service delivery for this patient and day.'),
    'exclusion_trigger_unresolved': ('dependency', 'H4 section 9; H1 section 10',
        'Resolve possible trigger-service delivery and dates in the exclusion window.'),
    'possible_unresolved_same_day_service': ('dependency', 'Contract section 11',
        'Resolve possible same-patient/service/day occurrences before certifying a complete payable total.'),
    'premium_quantity_unresolved': ('dependency', 'Contract section 5',
        'Resolve all contributing quantities, mappings and dates for the patient/service/day.'),
    'daily_quantity_unresolved': ('dependency', 'Contract daily quantity caps',
        'Resolve all contributing quantities, mappings and dates for the patient/service/day.'),
}


def build_review_queue(invoices, lines, output, hospital=4):
    grouped = defaultdict(list)
    for line in lines:
        grouped[line['record_id']].append(line)
    pending = [r for r in invoices if r['flagged'] and not r['pricing_complete']]
    rows, details = [], []
    counts = Counter()
    for inv in pending:
        blockers = set(filter(None,inv['review_reasons'].split('|')))
        if not blockers:
            raise ValueError('Incomplete flagged invoice has no recorded explanation')
        counts.update(blockers)
        related = grouped[inv['record_id']]
        unresolved = [l for l in related if l['expected_line_total_cents'] is None]
        rows.append(dict(record_id=inv['record_id'],invoice_id=inv['invoice_id'],
            detected_errors=inv['detected_errors'],billed_total_cents=inv['billed_total_cents'],
            review_reasons=inv['review_reasons'],unresolved_line_count=len(unresolved),
            unresolved_line_ids='|'.join(l['line_id'] for l in unresolved),
            known_lines_subtotal_NOT_expected_total_cents=sum(l['expected_line_total_cents'] for l in related if l['expected_line_total_cents'] is not None),
            resolution_status='not_submission_ready'))
        for reason in sorted(blockers):
            kind,clause,action = REASONS.get(reason,('other','Review contract and evidence','Inspect the unresolved condition; do not invent a total.'))
            if hospital == 3:
                clause = {
                    'identifier':'H3 Base Agreement section 10',
                    'unit':'H3 section 2.4, Appendix B and Amendment No. 1',
                    'compound_unit':'H3 Appendix B unit basis',
                    'mapping':'H3 Appendix B and Amendment No. 1',
                    'date':'H3 Base Agreement sections 1 and 10; Amendment A1.1',
                    'boundary':'H3 Base Agreement section 9',
                    'allocation':'H3 Base Agreement sections 7 and 10',
                    'dependency':'H3 Base Agreement sections 4-9',
                }.get(kind,'H3 contract documents')
            affected = [l for l in related if reason in l['review_reasons'].split('|')]
            # Invoice-level blockers still get an evidence row even when all
            # individual line amounts can be computed.
            for line in affected or [None]:
                details.append(dict(record_id=inv['record_id'],invoice_id=inv['invoice_id'],
                    line_id=line['line_id'] if line else '',reason=reason,kind=kind,
                    contract_reference=clause,description=line['description'] if line else '',
                    candidate_services=line['candidate_services'] if line else '',
                    billed_unit=line['unit_basis_as_billed'] if line else '',
                    service_date=line['service_date'] if line else '',required_resolution=action))
    write_csv(output/'pricing_review_queue.csv',rows,
              ['record_id','invoice_id','detected_errors','billed_total_cents','review_reasons',
               'unresolved_line_count','unresolved_line_ids','known_lines_subtotal_NOT_expected_total_cents','resolution_status'])
    write_csv(output/'pricing_review_evidence.csv',details,
              ['record_id','invoice_id','line_id','reason','kind','contract_reference','description',
               'candidate_services','billed_unit','service_date','required_resolution'])
    summary=dict(flagged_records_needing_pricing=len(pending),unique_invoice_ids=len({r['invoice_id'] for r in pending}),
        blocker_counts=dict(sorted(counts.items())),counts_overlap=True,
        policy='No record promoted. Known-line subtotal is not an expected invoice total.')
    (output/'pricing_review_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    text=['# Pricing review of flagged records','',
          f'I reviewed {len(pending)} flagged records whose payable totals are incomplete. Counts below overlap: one invoice may have several blockers.',
          '', '| Blocker | Records | Required resolution |', '|---|---:|---|']
    for reason,count in sorted(counts.items(),key=lambda x:(-x[1],x[0])):
        action=REASONS.get(reason,('','','Inspect the unresolved condition.'))[2]
        text.append(f'| {reason} | {count} | {action} |')
    text += ['', 'The queue retains all findings without adding fabricated amounts to the submission. '
             'The evidence CSV includes line descriptions, mapping candidates, dates and the required resolution. '
             'A known-line subtotal must not be submitted as a full expected total.', '',
             '## Questions requiring task-owner clarification', '',
             '1. May an invoice with a proven error but an unresolved payable amount be submitted with a blank expected_total_cents? If so, how should confidence represent that incomplete row?',
             '2. For services stated as "per hour, per item", does this mean a single item-hour unit, and is quantity already the number of item-hours?',
             '3. Does "within N days" include exactly N days? How should repeated invoice identifiers be represented in the single-ID submission schema?', '',
             'These questions have not been sent to the task owner. Current output assumes no permission to submit missing amounts.']
    (output/'PRICING_REVIEW.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    return summary
