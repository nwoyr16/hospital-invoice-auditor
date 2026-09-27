"""Recompute all audit evidence from raw JSONL and contract text."""
import argparse
import csv
import json
from pathlib import Path
from audit import audit,write_csv

FIELDS=['invoice_id','flagged','error_category','expected_total_cents','billed_total_cents','confidence']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent/'results')
    parser.add_argument('--hospital',type=int,choices=[1,4],default=4)
    parser.add_argument('--evaluate-h1',action='store_true',help='Explicit opt-in to labelled development evaluation')
    args=parser.parse_args()
    root=args.data_dir.resolve()
    out=args.output_dir.resolve()
    out.mkdir(parents=True,exist_ok=True)
    hospitals=sorted({args.hospital,1} if args.evaluate_h1 else {args.hospital})
    report={}
    for hospital in hospitals:
        invoices,lines,c=audit(root,hospital)
        target=out/f'hospital_{hospital}'
        write_csv(target/'invoice_audit.csv',invoices)
        write_csv(target/'line_audit.csv',lines)
        # Rules/mappings are rebuilt on every run; no cached invoice-specific input.
        mapping={r['description']:{k:r[k] for k in ['description','contract_service','mapping_status','candidate_services']} for r in lines}
        write_csv(target/'service_mapping.csv',list(mapping.values()))
        findings=[r for r in invoices if r['flagged']]
        complete=[r for r in invoices if r['pricing_complete']]
        report[f'hospital_{hospital}']=dict(invoice_records=len(invoices),line_items=len(lines),
            records_with_findings=len(findings),complete_totals=len(complete),
            complete_flagged=sum(r['flagged'] for r in complete),
            findings_without_complete_totals=sum(r['flagged'] and not r['pricing_complete'] for r in invoices),
            mapped_lines=sum(bool(r['contract_service']) for r in lines),
            inferred_lines=sum(r['mapping_status']=='unique_partial_inference' for r in lines))
        write_csv(target/'findings_requiring_pricing_review.csv',
                  [r for r in invoices if r['flagged'] and not r['pricing_complete']],list(invoices[0]))
        if hospital==4:
            from review_queue import build_review_queue
            build_review_queue(invoices,lines,target)
        if hospital==1 and args.evaluate_h1:
            from evaluate import evaluate
            report['h1_development']=evaluate(invoices,root,target)
        if hospital==4:
            with (root/'submission_template.csv').open(encoding='utf-8-sig',newline='') as stream:
                if next(csv.reader(stream)) != FIELDS:
                    raise ValueError('Submission template differs from supported schema')
            rows=[]
            for r in complete:
                rows.append(dict(invoice_id=r['invoice_id'],flagged=r['flagged'],error_category=r['detected_errors'],
                    expected_total_cents=r['expected_total_cents'],billed_total_cents=r['billed_total_cents'],
                    confidence='0.40' if r['mapping_inference_exposed'] else '0.60'))
            if len({r['invoice_id'] for r in rows}) != len(rows):
                raise ValueError('Duplicate IDs in submission')
            for r in rows:
                if bool(r['error_category']) != bool(r['flagged']):
                    raise ValueError('Flag/category inconsistency')
                if r['expected_total_cents'] != r['billed_total_cents'] and not r['flagged']:
                    raise ValueError('Unflagged amount mismatch')
            write_csv(out/'submission.csv',sorted(rows,key=lambda r:r['invoice_id']),FIELDS)
            # Keep the established root submission path in sync for this project.
            if out == (Path(__file__).resolve().parent/'results').resolve():
                write_csv(Path(__file__).resolve().parent/'submission.csv', sorted(rows,key=lambda r:r['invoice_id']),FIELDS)
    report['confidence_note']='0.40/0.60 remain subjective, uncalibrated estimates. No H4 accuracy is known. Inference exposure includes same-patient mappings and global discount-service mappings.'
    report['scope_note']='H4 submission only. Incomplete totals omitted rather than fabricated. H1 evaluation is optional and development-only. H2/H3/H5 remain outside scope.'
    (out/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    print('Results:',out)


if __name__=='__main__':
    main()
