"""Build a two-page first-person report from current results, not legacy outputs."""
import csv
import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, PageBreak, Spacer

ROOT=Path(__file__).resolve().parent


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    results=ROOT/'results'
    reports=ROOT/'reports'
    summary=json.loads((results/'summary.json').read_text(encoding='utf-8'))
    config=json.loads((ROOT/'submission_config.json').read_text(encoding='utf-8-sig'))
    if summary.get('submission',{}).get('hospitals') != [3,4] or 'h1_development' not in summary:
        raise ValueError('Run python run.py --evaluate-h1 for H1/H3/H4 before building this report.')
    submission=read_csv(ROOT/'submission.csv')
    if submission != read_csv(results/'submission.csv'):
        raise ValueError('Root submission and results submission differ.')
    if len(submission)!=summary['submission']['rows'] or sum(int(r['flagged']) for r in submission)!=summary['submission']['flagged']:
        raise ValueError('Submission does not match current summary.')
    categories=read_csv(results/'hospital_1/category_metrics.csv')
    evaluation=read_csv(results/'hospital_1/invoice_evaluation.csv')
    m=summary['h1_development']
    if len(evaluation)!=m['invoices_evaluated']:
        raise ValueError('H1 evaluation does not match summary.')
    reports.mkdir(exist_ok=True)
    name=config.get('candidate_name','Nwoyr Alshahrani')
    minutes=int(config.get('candidate_reported_minutes',390))
    h3,h4=summary['hospital_3'],summary['hospital_4']
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='AuditTitle',fontName='Helvetica-Bold',fontSize=17,leading=20,textColor=colors.HexColor('#15374b'),spaceAfter=6))
    styles.add(ParagraphStyle(name='AuditBody',fontName='Helvetica',fontSize=8.8,leading=11.2,spaceAfter=6))
    styles.add(ParagraphStyle(name='AuditHead',fontName='Helvetica-Bold',fontSize=10,leading=13,textColor=colors.HexColor('#15374b'),spaceBefore=7,spaceAfter=4))
    styles.add(ParagraphStyle(name='AuditSmall',fontName='Helvetica',fontSize=7.7,leading=9.7,spaceAfter=5))
    story=[]
    def p(text,style='AuditBody'):
        story.append(Paragraph(text,styles[style]))
    def table(data,widths,font=8):
        t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#15374b')),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTNAME',(0,1),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),font),
            ('LEADING',(0,0),(-1,-1),font+2),('VALIGN',(0,0),(-1,-1),'TOP'),
            ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#eef3f6'),colors.white]),
            ('ALIGN',(1,0),(-1,-1),'RIGHT')]))
        story.append(t)
    p('Hospital Invoice Audit | Revised Submission','AuditTitle')
    p(escape(name)+' | H1 development; H3 and H4 submission','AuditSmall')
    p('I revised my initial H4-only submission after reviewer feedback. I use deterministic Python checks driven by contract text, explicit service mappings and integer-cent arithmetic. I use no billed prices or labels to choose service mappings, and make no LLM calls at runtime.')
    table([['Scope','Records','Submitted','Flagged','Omitted'],
           ['Hospital 3',h3['invoice_records'],h3['complete_totals'],h3['complete_flagged'],h3['invoice_records']-h3['complete_totals']],
           ['Hospital 4',h4['invoice_records'],h4['complete_totals'],h4['complete_flagged'],h4['invoice_records']-h4['complete_totals']],
           ['Combined',h3['invoice_records']+h4['invoice_records'],len(submission),summary['submission']['flagged'],
            h3['invoice_records']+h4['invoice_records']-len(submission)]],[155,75,85,75,105])
    p('My initial submission contained 227 H4 invoices and 7 flags. The revision preserves the flags and monetary amounts on those rows and extends coverage. Submitted totals are complete under my documented interpretations, not independently established ground truth. H2 and H5 remain outside scope.','AuditSmall')
    p('H1 development evaluation','AuditHead')
    p(f"I evaluated {m['invoices_evaluated']} records and excluded {m['excluded_records']} reused-ID records. TP={m['tp']}, FP={m['fp']}, FN={m['fn']}, TN={m['tn']}; precision={m['precision']:.3f}, recall={m['recall']:.3f}, F1={m['f1']:.3f}. I matched the reference amount for {m['correct_complete_totals']}/{m['complete_totals_evaluated']} complete totals. H1 informed development; these are not held-out or H3/H4 accuracy estimates.")
    fmt=lambda v:'-' if v=='' or v is None else f'{float(v):.3f}'
    data=[['Error category','TP','FP','FN','Precision','Recall']]
    data += [[r['category'],r['tp'],r['fp'],r['fn'],fmt(r['precision']),fmt(r['recall'])] for r in categories]
    table(data,[267,35,35,35,64,59],7.6)
    p('I compare category names literally. Generic unit-price or recomputed-total findings can overlap more specific reference categories. In particular, the 13 recomputed-total category false positives are label-name disagreements, not 13 invoice-level false alarms. Category specificity remains a limitation. A dash denotes an undefined metric.','AuditSmall')
    story.append(PageBreak())
    p('My Decision Log and Error Analysis','AuditTitle')
    sections=[
        ('Contract interpretation and scope',
         'I added H3 by reading its Base Agreement, Appendix B and Amendment No. 1. I apply the seven amended rates by service date from 1 January 2025 and treat the two newly introduced services as non-billable before that date. Discounts continue across the amendment. I have no settlement-status evidence to apply the already-settled-invoice exception. I retained H4 rules and amounts; I did not reuse its rules for other contracts.'),
        ('Failure type 1: ambiguous service identity',
         'I retain multiple textual candidates for review and expose unique partial matches as inferences. I never choose the first candidate merely to increase coverage. H1 INV-H1-000657 is the remaining wholly missed erroneous invoice: an unresolved description prevents a reliable unit comparison. Broader mapping can improve coverage but needs independent semantic review.'),
        ('Failure type 2: a finding without a complete amount',
         f"I retain findings on {h3['findings_without_complete_totals']} H3 and {h4['findings_without_complete_totals']} H4 records outside the submission because their totals remain unresolved. For example, H4 INV-H4-000003 has a unit mismatch with no justified quantity conversion. I do not copy billed amounts into the expected field. Detailed queues identify the affected lines and required resolution."),
        ('Failure type 3: boundaries and allocation',
         'I defer exact exclusion-window endpoints and duplicate-charge allocation. H4 INV-H4-000235 has an exclusion-boundary blocker; H1 exclusion detection still misses three labelled cases. I use invoice date and identifiers only to order candidate duplicate occurrences, not to certify the payable allocation. Reused invoice IDs are not collapsed into a guessed submission record.'),
        ('Failure type 4: correct rule, differing reference amount',
         'For H1 INV-H1-000015, the line bills 9 tests and the contract caps payment at 4. My invoice total is 1,210,600 cents; the reference is 1,195,825 cents, one test lower. I preserve the general cap rule and report the disagreement instead of fitting an invoice-specific exception.'),
        ('Confidence and validation',
         'My confidence values of 0.40/0.60 are subjective and uncalibrated. I mark same-patient mapping inference and global discount mapping exposure. I passed 18 tests, including adjustment thresholds, amendment dates, cross-invoice bundles, raw-input shuffling, and combined H3/H4 output without H1 labels. These tests do not validate every mapping, resolve the private generalisation failure, or establish an updated leaderboard score. The previous separate repricing check covered the original 227 rows only.'),
        ('AI assistance, time and another week',
         f'I used Codex substantially for code, debugging, tests, analysis and documentation; I supplied inputs, ran scripts and chose scope. My first submission recorded {minutes//60} hours {minutes%60} minutes of hands-on work. This invited revision adds time that I have not yet recorded separately. With another week, I would validate inferred mappings, clarify units and exclusion boundaries, obtain the failed generalisation traceback, calibrate full-row correctness on a held-out set and extend coverage to another contract.')]
    for heading,body in sections:
        p(heading,'AuditHead');p(escape(body))
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#586876'))
        canvas.drawString(42,24,name+' | Revised audit')
        canvas.drawRightString(A4[0]-42,24,str(doc.page))
    doc=SimpleDocTemplate(str(reports/'report.pdf'),pagesize=A4,leftMargin=42,rightMargin=42,
                          topMargin=35,bottomMargin=40,title='Revised Hospital Invoice Audit',author=name)
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    (reports/'decision_log.md').write_text('# My revision decision log\n\n'+'\n\n'.join('## '+h+'\n\n'+b for h,b in sections)+'\n',encoding='utf-8')
    sources=[ROOT/'submission.csv',results/'summary.json',results/'hospital_1/category_metrics.csv',results/'hospital_1/invoice_evaluation.csv']
    manifest={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    (reports/'report_sources.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Updated report:',reports/'report.pdf')


if __name__=='__main__':
    main()
