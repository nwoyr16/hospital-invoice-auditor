"""Development-only evaluation. This module is not imported by the auditor."""
from collections import Counter
import csv
from audit import write_csv


def metrics(tp,fp,fn,tn):
    return dict(tp=tp,fp=fp,fn=fn,tn=tn,
                precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
                cost_5fn_plus_fp=5*fn+fp)


def evaluate(rows, root, output):
    with (root/'labels/hospital_1_labels.csv').open(encoding='utf-8-sig',newline='') as stream:
        labels = list(csv.DictReader(stream))
    pc = Counter(r['invoice_id'] for r in rows)
    lc = Counter(r['invoice_id'] for r in labels)
    reference = {r['invoice_id']:r for r in labels if lc[r['invoice_id']]==1}
    selected = [r for r in rows if pc[r['invoice_id']]==1 and r['invoice_id'] in reference]
    if any(int(r['is_erroneous']) not in (0,1) for r in labels):
        raise ValueError('Non-binary label')
    cats=set()
    joined=[]
    for row in selected:
        lab=reference[row['invoice_id']]
        truth=set(filter(None,lab['error_categories'].split('|')))
        pred=set(filter(None,row['detected_errors'].split('|')))
        cats.update(truth|pred)
        joined.append(dict(row,actual=int(lab['is_erroneous']),actual_categories=lab['error_categories'],
                           labelled_expected_total_cents=int(lab['expected_total_cents'])))
    def score(pairs):
        counts=Counter((bool(p),bool(a)) for p,a in pairs)
        return metrics(counts[True,True],counts[True,False],counts[False,True],counts[False,False])
    overall=score((r['flagged'],r['actual']) for r in joined)
    categories=[]
    for cat in sorted(cats):
        categories.append(dict(category=cat,**score((cat in r['detected_errors'].split('|'),
                        cat in r['actual_categories'].split('|')) for r in joined)))
    complete=[r for r in joined if r['pricing_complete']]
    amount_correct=sum(r['expected_total_cents']==r['labelled_expected_total_cents'] for r in complete)
    row_correct=sum(r['expected_total_cents']==r['labelled_expected_total_cents'] and
                    r['flagged']==r['actual'] for r in complete)
    write_csv(output/'invoice_evaluation.csv',joined)
    write_csv(output/'category_metrics.csv',categories)
    write_csv(output/'false_negatives.csv',[r for r in joined if r['actual'] and not r['flagged']],list(joined[0]))
    return dict(invoices_evaluated=len(joined),excluded_records=len(rows)-len(joined),**overall,
                complete_totals_evaluated=len(complete),correct_complete_totals=amount_correct,
                correct_complete_flags_and_totals=row_correct,
                note='Development evaluation after H1-assisted rule development. Not held-out calibration or H4 accuracy. Categories compared literally.')
