"""Focused regression checks on thresholds, rounding, aggregation and evidence."""
import csv
import sys
import tempfile
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from audit_discounts import discount_for
from audit import daily_quantity_checks

assert [discount_for(x,[(80,15),(240,30)]) for x in [80,81,240,241]]==[0,15,15,30]

with tempfile.TemporaryDirectory() as temp:
    def daily(qs, service='Advanced Vascular Endoscopic Procedure', unknown=None):
        rows=[dict(record_id=i+1,contract_service=service,candidate_services=service,
                   service_date='2024-04-01',quantity=q,unit_price_cents=101,base_rate_cents=101,
                   wrong_unit_basis=False,service_date_out_of_window=False) for i,q in enumerate(qs)]
        if unknown is not None:
            rows.append(dict(record_id=len(rows)+1,contract_service='',candidate_services=unknown,
                             service_date='2024-04-01',quantity=1,unit_price_cents=1,base_rate_cents=None,
                             wrong_unit_basis=False,service_date_out_of_window=False))
        data=pd.DataFrame(rows)
        parent=pd.DataFrame({'record_id':data.record_id,'patient_id':['P1']*len(data)})
        return daily_quantity_checks(data,parent,ROOT,Path(temp)).iloc[:len(qs)]
    assert daily([6,4]).daily_premium_percent.tolist()==[0,0]
    assert daily([6,5]).expected_checked_unit_price_cents.tolist()==[126,126]
    assert daily([6,5],unknown='Different Service').daily_premium_percent.tolist()==[25,25]
    assert daily([6,5],unknown='').daily_quantity_status.str.startswith('needs_review').all()
    assert daily([8,6],service='Advanced Orthopaedic Ward Bed Occupancy').daily_cap_exceeded.all()
    assert not daily([8,4],service='Advanced Orthopaedic Ward Bed Occupancy').daily_cap_exceeded.any()

lines=pd.read_csv(ROOT/'outputs/hospital_4/line_pricing_review.csv',keep_default_na=False)
invoices=pd.read_csv(ROOT/'outputs/hospital_4/invoice_pricing_review.csv',keep_default_na=False)
complete=invoices[invoices.pricing_status.eq('complete_under_documented_rules')]
assert len(invoices)==840 and len(complete)==227
assert lines.line_id.is_unique
for _,row in complete.iterrows():
    g=lines[lines.record_id.eq(row.record_id)]
    assert g.pricing_review_reasons.eq('').all()
    assert sum(Decimal(str(x)) for x in g.expected_line_total_cents)==Decimal(str(row.expected_total_cents))
    if int(row.expected_total_cents)!=int(row.billed_total_cents):
        assert 'recomputed_total_mismatch' in row.detected_errors.split('|')
with (ROOT/'submission.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
assert len(rows)==227 and sum(r['flagged']=='1' for r in rows)==7
assert len({r['invoice_id'] for r in rows})==len(rows)
for r in rows:
    assert bool(r['error_category'])==(r['flagged']=='1')
    assert Decimal(0)<=Decimal(r['confidence'])<=Decimal(1)
    for name in ['expected_total_cents','billed_total_cents']:
        assert r[name]==str(int(r[name]))
h1=pd.read_csv(ROOT/'outputs/hospital_1/invoice_evaluation.csv')
assert len(h1)==908 and h1.invoice_id.is_unique
t=h1.is_erroneous.eq(1);p=h1.predicted_flag.eq(1)
assert [int((p&t).sum()),int((p&~t).sum()),int((~p&t).sum()),int((~p&~t).sum())]==[35,0,18,855]
print('PASS: strict thresholds, daily aggregation and uncertainty, money, evidence, schema and development metrics.')
