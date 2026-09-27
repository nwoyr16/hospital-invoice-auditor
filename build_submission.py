"""Select complete H4 totals and validate the exact submission representation."""
import csv
import json
from decimal import Decimal
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent


def integer(value):
    number = Decimal(str(value))
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f'Invalid integer amount: {value}')
    return int(number)


def main():
    out = ROOT/'outputs/hospital_4'
    reports = ROOT/'reports'
    reports.mkdir(exist_ok=True)
    config = json.loads((ROOT/'submission_config.json').read_text(encoding='utf-8'))
    invoices = pd.read_csv(out/'invoice_pricing_review.csv', keep_default_na=False)
    lines = pd.read_csv(out/'line_pricing_review.csv', keep_default_na=False)
    parent = pd.read_csv(out/'json_invoice_checks.csv', keep_default_na=False)
    selected = invoices.loc[invoices.pricing_status.eq('complete_under_documented_rules')].copy()
    if selected.invoice_id.duplicated().any() or not parent.record_id.is_unique or not lines.line_id.is_unique:
        raise ValueError('Ambiguous identifiers in submission evidence.')
    groups = {key: group for key, group in lines.groupby('record_id')}
    inferred = lines.mapping_status.eq('mapped_reviewed_inference')
    inferred_records = set(lines.loc[inferred, 'record_id'])
    inferred_patients = set(lines.loc[inferred, 'patient_id'])
    patient_by_record = parent.set_index('record_id').patient_id.to_dict()
    fields = ['invoice_id','flagged','error_category','expected_total_cents','billed_total_cents','confidence']
    with (ROOT/'submission_template.csv').open(encoding='utf-8-sig',newline='') as f:
        if next(csv.reader(f)) != fields:
            raise ValueError('Template columns differ from expected schema.')
    rows, evidence = [], []
    for _, invoice in selected.iterrows():
        group = groups.get(invoice.record_id)
        if group is None or group.empty or group.pricing_review_reasons.ne('').any():
            raise ValueError('A selected invoice has unresolved line evidence.')
        expected = integer(invoice.expected_total_cents)
        billed = integer(invoice.billed_total_cents)
        if sum(integer(v) for v in group.expected_line_total_cents) != expected:
            raise ValueError('Complete total does not reconcile with line evidence.')
        errors = set(filter(None, invoice.detected_errors.split('|')))
        if expected != billed:
            errors.add('recomputed_total_mismatch')
        own_inference = invoice.record_id in inferred_records
        exposed = patient_by_record[invoice.record_id] in inferred_patients
        confidence = config['inference_exposed_confidence' if exposed else 'direct_mapping_confidence']
        if not Decimal(0) <= Decimal(confidence) <= Decimal(1):
            raise ValueError('Confidence outside [0,1].')
        rows.append(dict(zip(fields,[invoice.invoice_id,int(bool(errors)), '|'.join(sorted(errors)),expected,billed,confidence])))
        evidence.append(dict(record_id=invoice.record_id,invoice_id=invoice.invoice_id,
                             contains_inferred_mapping=own_inference,inference_exposed=exposed,
                             confidence=confidence,amount_difference_cents=billed-expected,
                             evidence_file='outputs/hospital_4/line_pricing_review.csv',
                             line_ids='|'.join(group.line_id),
                             confidence_basis='subjective_unvalidated_mapping_inference' if exposed else 'subjective_unvalidated_complete_calculation'))
    rows.sort(key=lambda r:r['invoice_id'])
    with (ROOT/'submission.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    with (ROOT/'submission.csv').open(encoding='utf-8',newline='') as f:
        saved=list(csv.DictReader(f))
    assert len(saved)==len(selected)
    for row in saved:
        assert row['invoice_id'].startswith('INV-H4-')
        assert row['flagged'] in ['0','1']
        assert bool(row['error_category']) == (row['flagged']=='1')
        for name in ['expected_total_cents','billed_total_cents']:
            assert str(integer(row[name]))==row[name]
    pd.DataFrame(evidence).to_csv(reports/'submission_evidence.csv',index=False)
    invoices.loc[~invoices.record_id.isin(selected.record_id)].to_csv(reports/'abstentions.csv',index=False)
    summary=dict(invoice_records=len(invoices),submitted=len(rows),flagged=sum(r['flagged'] for r in rows),
                 unflagged=sum(not r['flagged'] for r in rows),omitted=len(invoices)-len(rows),
                 amount_mismatches=sum(r['expected_total_cents']!=r['billed_total_cents'] for r in rows),
                 contains_inferred_mapping=sum(e['contains_inferred_mapping'] for e in evidence),
                 inference_exposed=sum(e['inference_exposed'] for e in evidence),
                 confidence_note=config['confidence_note'])
    (reports/'submission_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
