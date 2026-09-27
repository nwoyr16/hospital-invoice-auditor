"""Separate repricing implementation from raw JSONL and contract text.

This checks all selected rows, conditional on the existing service mappings.
It does not import the audit/pricing functions or establish ground truth.
"""
import csv
import json
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def main():
    contract=(ROOT/'contracts/hospital_4/conditional_reimbursement_agreement.txt').read_text(encoding='utf-8-sig')
    def section(a,b):return contract.split(a,1)[1].split(b,1)[0]
    def cents(x):return int(Decimal(x.replace(',',''))*100)
    def rounded(x):return int(x.quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    def day(x):
        try:return date.fromisoformat(x)
        except (ValueError,TypeError):return None
    units={'per hour':'per_hour','per visit':'per_visit','per procedure':'per_procedure','per test':'per_test',
           'per day of service':'per_day','per night of occupancy':'per_night','per item supplied':'per_item','per unit dispensed':'per_unit_dispensed'}
    rates={}
    for row in section('3. BASE RATES','4. ORDER OF ADJUSTMENTS').splitlines():
        m=re.fullmatch(r'(.+?)\s{2,}(per .+?)\s{2,}GBP ([\d,.]+)',row.strip())
        if m:rates[m[1].strip()]=(units.get(m[2],''),cents(m[3]))
    premiums={}
    for row in section('5. THRESHOLD PREMIUMS','6. DAILY QUANTITY LIMITS').splitlines():
        m=re.fullmatch(r'(.+?)\s{2,}more than (\d+) \w+\s+\+(\d+)%',row.strip())
        if m:premiums[m[1].strip()]=(int(m[2]),int(m[3]))
    caps={}
    for row in section('6. DAILY QUANTITY LIMITS','7. BUNDLED DELIVERY').splitlines():
        m=re.fullmatch(r'(.+?)\s{2,}(\d+) \w+',row.strip())
        if m:caps[m[1].strip()]=int(m[2])
    bundles={}
    for row in section('7. BUNDLED DELIVERY','8. DISCOUNTS').splitlines():
        m=re.fullmatch(r'(.+?)\s{2,}GBP ([\d,.]+)\s+(.+?)\s{2,}GBP ([\d,.]+)',row.strip())
        if m:
            a,b=m[1].strip(),m[3].strip()
            bundles[a]=(b,cents(m[2]));bundles[b]=(a,cents(m[4]))
    discounts=defaultdict(list)
    for row in section('8. DISCOUNTS','9. EXCLUSION WINDOWS').splitlines():
        m=re.fullmatch(r'(.+?)\s{2,}.+?\((\d+)\)\s+.+?\((\d+)%\)',row.strip())
        if m:discounts[m[1].strip()].append((int(m[2]),int(m[3])))
    exclusions={}
    for row in section('9. EXCLUSION WINDOWS','10. NON-BUSINESS-DAY UPLIFTS').splitlines():
        m=re.fullmatch(r'(.+?)\s{2,}(\d+) days\s+(.+?)',row.strip())
        if m:exclusions[m[1].strip()]=(int(m[2]),m[3].strip())
    assert (len(rates),len(premiums),len(caps),len(bundles),len(discounts),len(exclusions))==(98,18,18,14,3,15)
    with (ROOT/'outputs/hospital_4/service_line_checks.csv').open(encoding='utf-8-sig',newline='') as f:
        mapping={r['line_id']:r for r in csv.DictReader(f)}
    with (ROOT/'outputs/hospital_4/line_pricing_review.csv').open(encoding='utf-8-sig',newline='') as f:
        calculated={r['line_id']:r for r in csv.DictReader(f)}
    invoices={};all_lines=[];by_patient=defaultdict(list);invoice_ids=defaultdict(list)
    with (ROOT/'invoices/hospital_4_invoices.jsonl').open(encoding='utf-8-sig') as f:
        for record_id,text in enumerate(f,1):
            if not text.strip():continue
            invoice=json.loads(text);invoices[record_id]=invoice;invoice_ids[invoice['invoice_id']].append(record_id)
            for item in invoice['line_items']:
                m=mapping[item['line_id']]
                assert m['description']==item['description'] and int(m['record_id'])==record_id
                x=dict(item,record_id=record_id,patient=invoice['patient_id'],day=day(item['service_date']),
                       service=m['contract_service'],candidates=set(filter(None,m['candidate_services'].split('|'))),
                       inference=m['mapping_status']=='mapped_reviewed_inference')
                all_lines.append(x);by_patient[x['patient']].append(x)
    raw_by_id={x['line_id']:x for x in all_lines}
    assert len(raw_by_id)==len(all_lines)==len(mapping)
    def possible(x,service):return x['service']==service or (not x['service'] and (not x['candidates'] or service in x['candidates']))
    def discount_percent(q,table):return max([pct for threshold,pct in table if q>threshold] or [0])
    totals=[];details=[];issues=[]
    with (ROOT/'submission.csv').open(encoding='utf-8',newline='') as f:selected=list(csv.DictReader(f))
    for prediction in selected:
        ids=invoice_ids[prediction['invoice_id']]
        assert len(ids)==1
        invoice=invoices[ids[0]];total=0;flags=set();own_inferences=0
        assert int(prediction['billed_total_cents'])==invoice['invoice_total_cents']
        assert invoice['contract_number']=='INS-H4-2024-2049'
        if sum(i['line_total_cents'] for i in invoice['line_items'])!=invoice['invoice_total_cents']:flags.add('invoice_total_mismatch')
        for item in invoice['line_items']:
            x=raw_by_id[item['line_id']];service=x['service'];context=by_patient[x['patient']]
            if x['inference']:own_inferences+=1
            assert service in rates
            unit,base=rates[service]
            assert unit and unit==x['unit_basis_as_billed']
            assert x['day'] and date(2024,1,1)<=x['day']<=date(2025,12,31)
            q=Decimal(str(x['quantity']));assert q>=0 and q==q.to_integral_value()
            if x['day']>day(invoice['invoice_date']):flags.add('service_date_after_invoice_date')
            if q*Decimal(str(x['unit_price_cents']))!=Decimal(str(x['line_total_cents'])):flags.add('line_total_arithmetic')
            same=[y for y in context if y['service']==service and y['day']==x['day']]
            assert len(same)==1, 'Unresolved repeated service in selected invoice'
            assert not any(not y['service'] and possible(y,service) and (y['day'] is None or y['day']==x['day']) for y in context)
            rate=base;steps=[f'base={base}'];daily=sum(Decimal(str(y['quantity'])) for y in same)
            if service in bundles:
                partner,bundle_rate=bundles[service]
                assert not any(y['day'] is None for y in context)
                assert not any(y['day']==x['day'] and not y['service'] for y in context)
                if any(y['service']==partner and y['day']==x['day'] for y in context):rate=bundle_rate;steps.append(f'bundle={rate}')
            if service in premiums:
                assert not any(possible(y,service) and y['day'] is None for y in context)
                threshold,pct=premiums[service]
                if daily>threshold:rate=rounded(Decimal(rate)*Decimal(100+pct)/100);steps.append(f'premium={pct}%')
            if service in caps:
                assert not any(possible(y,service) and y['day'] is None for y in context)
                assert daily<=caps[service];steps.append(f'quantity={daily}<=cap={caps[service]}')
            if service in discounts:
                valid=lambda y:y['day'] is not None and date(2024,1,1)<=y['day']<=date(2025,12,31)
                before=sum(Decimal(str(y['quantity'])) for y in all_lines if y['service']==service and valid(y) and (y['day'],y['line_id'])<(x['day'],x['line_id']))
                extra=sum(Decimal(str(y['quantity'])) for y in all_lines if possible(y,service) and (not y['service'] or not valid(y)))
                low=discount_percent(before,discounts[service]);high=discount_percent(before+extra,discounts[service]);assert low==high
                rate=rounded(Decimal(rate)*Decimal(100-low)/100);steps.append(f'prior=[{before},{before+extra}],discount={low}%')
            if service in exclusions:
                window,trigger=exclusions[service]
                trigger_distances=[abs((y['day']-x['day']).days) for y in context if y['service']==trigger and y['day']]
                assert window not in trigger_distances
                if any(d<window for d in trigger_distances):rate=0;steps.append('excluded=0')
                else:
                    assert not any(possible(y,trigger) and (y['day'] is None or (not y['service'] and abs((y['day']-x['day']).days)<=window)) for y in context)
                    steps.append('no identified exclusion trigger')
            line_amount=int(q*rate)
            if line_amount!=int(calculated[x['line_id']]['expected_line_total_cents']):issues.append({'line_id':x['line_id'],'separate_amount':line_amount,'pipeline_amount':calculated[x['line_id']]['expected_line_total_cents']})
            if rate!=x['unit_price_cents']:flags.add('calculated_unit_price_difference')
            total+=line_amount
            details.append(dict(invoice_id=invoice['invoice_id'],line_id=x['line_id'],service=service,inferred_mapping=x['inference'],quantity=str(q),expected_unit_price_cents=rate,expected_line_total_cents=line_amount,contract_steps='; '.join(steps)))
        if total!=invoice['invoice_total_cents']:flags.add('recomputed_total_mismatch')
        if total!=int(prediction['expected_total_cents']) or bool(flags)!=(prediction['flagged']=='1'):
            issues.append({'invoice_id':prediction['invoice_id'],'separate_total':total,'submitted_total':prediction['expected_total_cents'],'separate_flags':sorted(flags)})
        totals.append(dict(invoice_id=prediction['invoice_id'],separate_total_cents=total,submitted_total_cents=prediction['expected_total_cents'],separate_findings='|'.join(sorted(flags)),inferred_line_count=own_inferences))
    for filename,rows in [('separate_repricing_lines.csv',details),('separate_repricing_invoices.csv',totals)]:
        with (ROOT/'reports'/filename).open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=dict(selected_invoices=len(totals),checked_lines=len(details),disagreements=len(issues),issues=issues,
                 limitation='Separate implementation of the contract arithmetic and selected-record checks, using raw JSONL but the same saved service mappings and candidate vocabulary. Agreement does not validate mapping semantics, shared interpretations, or confidence calibration; this is not an external independent audit.')
    (ROOT/'reports/separate_repricing_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
    if issues:raise ValueError('Separate repricing disagrees with submission')


if __name__=='__main__':main()
