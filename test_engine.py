"""Contract boundary tests and raw-input regression tests, using unittest."""
import copy
import csv
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

from audit import Contract,adjusted,audit,discount_percent,map_description,parse_contract,parse_date

ROOT=Path(__file__).resolve().parent


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        shutil.copytree(ROOT/'contracts',self.root/'contracts')
        (self.root/'invoices').mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def invoice(self, ident, service,quantity,rate,day='2024-01-01',patient='P',unit=None):
        c=parse_contract(self.root,4)
        return dict(invoice_id=ident,hospital_id='H4',contract_number=c.number,
            invoice_date='2024-12-31',patient_id=patient,facility_code='F-MAIN',plan_tier='GOLD',
            invoice_total_cents=quantity*rate,line_items=[dict(line_id=ident+'-L',invoice_id=ident,
                line_no=1,service_date=day,description=service,quantity=quantity,
                unit_basis_as_billed=unit or c.services[service]['unit'],
                unit_price_cents=rate,line_total_cents=quantity*rate)])

    def run_audit(self,records):
        with (self.root/'invoices/hospital_4_invoices.jsonl').open('w',encoding='utf-8') as stream:
            for row in records:
                stream.write(json.dumps(row)+'\n')
        return audit(self.root,4)

    def test_exact_thresholds_and_rounding(self):
        self.assertEqual(adjusted(105,10),116)
        self.assertEqual(discount_percent(80,[(80,15),(240,30)]),0)
        self.assertEqual(discount_percent(81,[(80,15),(240,30)]),15)
        self.assertEqual(discount_percent(240,[(80,15),(240,30)]),15)
        self.assertEqual(discount_percent(241,[(80,15),(240,30)]),30)
        self.assertIsNone(parse_date('2025-06-31'))
        self.assertIsNone(parse_date('2024-1-1'))

    def test_first_description_can_be_inferred(self):
        c=parse_contract(self.root,4)
        service,status,candidates=map_description('IMMUN spclst /ZZ-9999',c)
        self.assertEqual(service,'Specialist Immunologic Consultation')
        self.assertEqual(status,'unique_partial_inference')
        self.assertIsNone(map_description('card HOME vst',c)[0])
        row=self.invoice('X','Specialist Immunologic Consultation',1,114500)
        row['line_items'][0]['description']='IMMUN spclst /ZZ-9999'
        self.assertEqual(self.run_audit([row])[0][0]['expected_total_cents'],114500)

    def test_prices_cannot_change_mapping(self):
        row=self.invoice('X','Specialist Immunologic Consultation',1,114500)
        row['line_items'][0]['description']='IMMUN spclst /ZZ-9999'
        original=self.run_audit([row])[1][0]['contract_service']
        row['line_items'][0]['unit_price_cents']=1
        self.assertEqual(self.run_audit([row])[1][0]['contract_service'],original)

    def test_daily_aggregate_across_invoices(self):
        service='Advanced Vascular Endoscopic Procedure'
        a=self.invoice('A',service,6,321775)
        b=self.invoice('B',service,5,321775)
        invoices,lines,_=self.run_audit([b,a])
        self.assertTrue(all('daily_quantity=11;threshold=10;premium=25' in l['evidence'] for l in lines))
        self.assertTrue(all(not r['pricing_complete'] for r in invoices))
        self.assertIn('cross_invoice_duplicate',invoices[0]['detected_errors'])
        self.assertNotIn('cross_invoice_duplicate',invoices[1]['detected_errors'])

    def test_threshold_and_cap_payable_quantity(self):
        row=self.invoice('X','Advanced Vascular Endoscopic Procedure',10,321775)
        self.assertEqual(self.run_audit([row])[0][0]['expected_total_cents'],3217750)
        row=self.invoice('Y','Assisted Urologic Nursing Observation',6,132675)
        result=self.run_audit([row])[0][0]
        self.assertEqual(result['expected_total_cents'],4*132675)
        self.assertIn('daily_cap_exceeded',result['detected_errors'])

    def test_cross_invoice_bundle(self):
        a=self.invoice('A','Ambulatory Obstetric Case Conference',1,11875)
        b=self.invoice('B','Focused Vascular Infusion Therapy',1,4900)
        results=self.run_audit([a,b])[0]
        self.assertEqual([r['expected_total_cents'] for r in results],[11875,4900])
        self.assertFalse(any(r['flagged'] for r in results))

    def test_discount_order_is_date_then_line_identifier(self):
        service='Ambulatory Musculoskeletal Ventilation Support'
        records=[self.invoice('A',service,80,157150,patient='A'),
                 self.invoice('B',service,1,157150,patient='B'),
                 self.invoice('C',service,1,133578,patient='C')]
        results=self.run_audit(list(reversed(records)))[0]
        totals={r['invoice_id']:r['expected_total_cents'] for r in results}
        self.assertEqual(totals['B'],157150)
        self.assertEqual(totals['C'],133578)

    def test_exclusion_boundary_is_not_silently_resolved(self):
        a=self.invoice('A','Advanced Paediatric Theatre Time',1,37100,day='2024-01-01')
        b=self.invoice('B','Bedside Cardiac Home Visit',1,64800,day='2024-01-31')
        result=self.run_audit([a,b])[0][0]
        self.assertIn('exclusion_boundary_unresolved',result['review_reasons'])
        self.assertIsNone(result['expected_total_cents'])
        b['line_items'][0]['service_date']='2024-01-30'
        result=self.run_audit([a,b])[0][0]
        self.assertEqual(result['expected_total_cents'],0)
        self.assertIn('exclusion_window_violation',result['detected_errors'])

    def test_unknown_and_bad_units_are_not_fabricated_totals(self):
        row=self.invoice('X','Specialist Immunologic Consultation',1,114500,unit='per_hour')
        result=self.run_audit([row])[0][0]
        self.assertIn('wrong_unit_basis',result['detected_errors'])
        self.assertIsNone(result['expected_total_cents'])
        row['line_items'][0]['description']='Unrecognised new procedure'
        self.assertIsNone(self.run_audit([row])[0][0]['expected_total_cents'])

    def test_submission_reproducible_after_shuffle_without_labels_or_outputs(self):
        shutil.copy2(ROOT/'submission_template.csv',self.root/'submission_template.csv')
        raw=[json.loads(s) for s in (ROOT/'invoices/hospital_4_invoices.jsonl').read_text(encoding='utf-8-sig').splitlines() if s.strip()]
        path=self.root/'invoices/hospital_4_invoices.jsonl'
        def execute(records,dest):
            path.write_text('\n'.join(json.dumps(r) for r in records),encoding='utf-8')
            subprocess.run([sys.executable,str(ROOT/'run.py'),'--hospital','4','--data-dir',str(self.root),
                            '--output-dir',str(dest)],check=True,capture_output=True,text=True)
            return (dest/'submission.csv').read_bytes()
        first=execute(raw,self.root/'first')
        random.Random(42).shuffle(raw)
        for r in raw:
            random.Random(r['invoice_id']).shuffle(r['line_items'])
        second=execute(raw,self.root/'second')
        self.assertEqual(first,second)
        self.assertFalse((self.root/'labels').exists())

    def run_h3(self,records):
        with (self.root/'invoices/hospital_3_invoices.jsonl').open('w',encoding='utf-8') as stream:
            for row in records:
                stream.write(json.dumps(row)+'\n')
        return audit(self.root,3)

    def h3_invoice(self,ident,service,day,rate,invoice_day='2025-02-01',patient=None):
        c=parse_contract(self.root,3)
        return dict(invoice_id=ident,hospital_id='H3',contract_number=c.number,
            invoice_date=invoice_day,patient_id=patient or ident,facility_code='F-MAIN',plan_tier='BRONZE',
            invoice_total_cents=rate,line_items=[dict(line_id=ident+'-L',invoice_id=ident,
                line_no=1,service_date=day,description=service,quantity=1,
                unit_basis_as_billed=c.services[service]['unit'],unit_price_cents=rate,line_total_cents=rate)])

    def test_h3_amendment_uses_service_date_not_invoice_date(self):
        service='Ambulatory Otolaryngologic Imaging Interpretation'
        a=self.h3_invoice('OLD',service,'2024-12-31',182625)
        b=self.h3_invoice('NEW',service,'2025-01-01',208200)
        rows,_,_=self.run_h3([a,b])
        self.assertEqual([r['expected_total_cents'] for r in rows],[182625,208200])
        self.assertFalse(any(r['flagged'] for r in rows))

    def test_h3_added_services_are_not_payable_before_introduction(self):
        service='Advanced Dermatologic Nutritional Support'
        a=self.h3_invoice('EARLY',service,'2024-12-31',86525)
        b=self.h3_invoice('VALID',service,'2025-01-01',86525)
        rows,_,_=self.run_h3([a,b])
        self.assertEqual(rows[0]['expected_total_cents'],0)
        self.assertIn('service_not_contracted_on_date',rows[0]['detected_errors'])
        self.assertEqual(rows[1]['expected_total_cents'],86525)
        self.assertFalse(rows[1]['flagged'])

    def test_h3_weekend_applies_after_amended_rate(self):
        service='Specialist Psychiatric Discharge Planning'
        row=self.h3_invoice('WEEKEND',service,'2025-01-04',48455)
        rows,_,_=self.run_h3([row])
        self.assertEqual(rows[0]['expected_total_cents'],48455)
        self.assertFalse(rows[0]['flagged'])

    def test_h3_discount_history_does_not_reset_at_amendment(self):
        service='Assisted Urologic Endoscopic Procedure'
        rows=[self.h3_invoice('EARLY'+str(i),service,'2024-12-30',94250) for i in range(101)]
        rows.append(self.h3_invoice('LATE',service,'2025-01-02',100103))
        results,_,_=self.run_h3(rows)
        self.assertEqual(results[-1]['expected_total_cents'],100103)
        self.assertFalse(results[-1]['flagged'])

    def test_h3_missing_amendment_does_not_silently_use_old_rates(self):
        (self.root/'contracts/hospital_3/amendment_no_1.txt').rename(self.root/'saved_amendment.txt')
        with self.assertRaises(FileNotFoundError):
            parse_contract(self.root,3)

    def test_default_run_combines_h3_and_h4_without_h1_labels(self):
        h3=self.h3_invoice('INV-H3-TEST','Ambulatory Otolaryngologic Imaging Interpretation',
                           '2025-01-01',208200)
        h4=self.invoice('INV-H4-TEST','Specialist Immunologic Consultation',1,114500)
        self.run_h3([h3])
        self.run_audit([h4])
        shutil.copy2(ROOT/'submission_template.csv',self.root/'submission_template.csv')
        output=self.root/'combined'
        subprocess.run([sys.executable,str(ROOT/'run.py'),'--data-dir',str(self.root),
                        '--output-dir',str(output)],check=True,capture_output=True,text=True)
        with (output/'submission.csv').open(encoding='utf-8',newline='') as stream:
            result=list(csv.DictReader(stream))
        self.assertEqual({r['invoice_id'] for r in result},{'INV-H3-TEST','INV-H4-TEST'})
        self.assertFalse((self.root/'labels').exists())

    def test_review_queue_does_not_promote_partial_total(self):
        from review_queue import build_review_queue
        a=self.invoice('X','Specialist Immunologic Consultation',1,114500,unit='per_hour')
        records,lines,_=self.run_audit([a])
        original=copy.deepcopy(records)
        out=self.root/'review'
        out.mkdir()
        summary=build_review_queue(records,lines,out)
        self.assertEqual(records,original)
        self.assertEqual(summary['flagged_records_needing_pricing'],1)
        self.assertIsNone(records[0]['expected_total_cents'])
        with (out/'pricing_review_evidence.csv').open(encoding='utf-8',newline='') as stream:
            evidence=list(csv.DictReader(stream))
        self.assertEqual(evidence[0]['reason'],'unit_conversion_unresolved')
        self.assertEqual(evidence[0]['line_id'],'X-L')

    def test_review_queue_retains_invoice_level_identifier_blocker(self):
        from review_queue import build_review_queue
        a=self.invoice('X','Specialist Immunologic Consultation',1,114500,patient='P1')
        b=self.invoice('X','Specialist Immunologic Consultation',1,114500,patient='P2')
        b['line_items'][0]['line_id']='different-line'
        records,lines,_=self.run_audit([a,b])
        out=self.root/'review'
        out.mkdir()
        summary=build_review_queue(records,lines,out)
        self.assertEqual(summary['flagged_records_needing_pricing'],2)
        self.assertEqual(summary['unique_invoice_ids'],1)
        with (out/'pricing_review_evidence.csv').open(encoding='utf-8',newline='') as stream:
            evidence=list(csv.DictReader(stream))
        self.assertTrue(all(r['reason']=='ambiguous_invoice_identifier' for r in evidence))
        self.assertEqual(len(evidence),2)


if __name__=='__main__':
    unittest.main(verbosity=2)
