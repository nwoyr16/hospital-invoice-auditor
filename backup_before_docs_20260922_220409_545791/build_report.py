"""Two-page evaluation and one-page decision log, from current reproduced results."""
import json
from pathlib import Path
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, PageBreak

ROOT=Path(__file__).resolve().parent


def main():
    config=json.loads((ROOT/'submission_config.json').read_text(encoding='utf-8'))
    summary=json.loads((ROOT/'reports/submission_summary.json').read_text(encoding='utf-8'))
    evaluation=pd.read_csv(ROOT/'outputs/hospital_1/invoice_evaluation.csv',keep_default_na=False)
    metrics=pd.read_csv(ROOT/'outputs/hospital_1/all_category_metrics.csv')
    truth=evaluation.is_erroneous.eq(1);pred=evaluation.predicted_flag.eq(1)
    tp=int((truth&pred).sum());fp=int((~truth&pred).sum());fn=int((truth&~pred).sum());tn=int((~truth&~pred).sum())
    precision=tp/(tp+fp);recall=tp/(tp+fn);f1=2*tp/(2*tp+fp+fn);accuracy=(tp+tn)/len(evaluation)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleAudit',fontName='Helvetica-Bold',fontSize=16,leading=19,spaceAfter=6,textColor=colors.HexColor('#15374b')))
    styles.add(ParagraphStyle(name='BodyAudit',fontName='Helvetica',fontSize=8.5,leading=10.7,spaceAfter=5))
    styles.add(ParagraphStyle(name='HeadAudit',fontName='Helvetica-Bold',fontSize=9.2,leading=12,spaceBefore=6,spaceAfter=4,textColor=colors.HexColor('#15374b')))
    story=[]
    def p(text):story.append(Paragraph(text,styles['BodyAudit']))
    def h(text):story.append(Paragraph(text,styles['HeadAudit']))
    story.append(Paragraph('Nwoyr Alshahrani'
    ' | Invoice audit evaluation',styles['TitleAudit']))
    p(f"H1: development and evaluation. H4: {summary['submitted']} selected predictions from {summary['invoice_records']} records ({summary['flagged']} flagged, {summary['unflagged']} unflagged); {summary['omitted']} omitted because complete pricing remains unresolved. Five selected totals differ from billed amounts. H2/H3/H5 are outside the final scope.")
    h('Measurement')
    p(f"{len(evaluation)} H1 invoices with unambiguous identifiers were evaluated; ten records sharing five invoice IDs were excluded. TP {tp}, FP {fp}, FN {fn}, TN {tn}. Precision {precision:.2%}; recall {recall:.2%}; F1 {f1:.2%}; accuracy {accuracy:.2%}. H1 informed development, so these are not held-out results or H4 accuracy. A negative means no detected finding, not complete audit clearance; all eligible negatives remain in the evaluation.")
    data=[['H1 category (literal name)','TP','FP','FN','Precision','Recall']]
    for _,r in metrics.iterrows():
        data.append([r['category'],str(int(r.tp)),str(int(r.fp)),str(int(r.fn)),
                     '-' if pd.isna(r.precision) else f'{r.precision:.2f}',
                     '-' if pd.isna(r.recall) else f'{r.recall:.2f}'])
    table=Table(data,colWidths=[252,30,30,30,63,63],hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#15374b')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTNAME',(0,1),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),7.3),('LEADING',(0,0),(-1,-1),8.5),('TOPPADDING',(0,0),(-1,-1),2.8),('BOTTOMPADDING',(0,0),(-1,-1),2.8),('ALIGN',(1,0),(-1,-1),'CENTER'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#eef3f5'),colors.white])]))
    story.append(table)
    p('A dash means undefined, not zero. Categories are compared literally: weekend_rate_mismatch has no identically named reference category. Its two findings therefore cannot be interpreted as two proven incorrect weekend decisions. After-invoice category false positives are INV-H1-000179 and INV-H1-000852; both have other error labels.')
    h('Four systematic limitations, with examples')
    p('<b>Identification:</b> unresolved descriptions are deferred rather than automatically declared unknown. INV-H1-000667 is labelled unknown_service but received no finding. This category has 12 misses over the full evaluated population.')
    p('<b>Pricing coverage:</b> matching a service does not establish its adjusted price. INV-H1-000151 is a missed unit_price_mismatch; category recall is 0.30. H4-specific rules do not acquire validation from these H1 metrics.')
    p('<b>Daily aggregation:</b> H1 daily-cap checking is not implemented. INV-H1-000015 is a missed daily_cap_exceeded case. H4 has a separate daily aggregation implementation, with unresolved quantities deferred.')
    p('<b>Relationships across records:</b> H1 cross-invoice duplication, bundles and exclusions remain unimplemented. INV-H1-000231 is a missed cross_invoice_duplicate. The 18 wholly missed invoices are analysed separately; their 198 lines are not all proven erroneous.')
    h('Separate H4 calculation check')
    verification=json.loads((ROOT/'reports/separate_repricing_summary.json').read_text(encoding='utf-8'))
    p(f"A separate implementation parsed the contract and raw JSONL and recomputed all {verification['selected_invoices']} selected invoices ({verification['checked_lines']} lines), with {verification['disagreements']} disagreements in totals or invoice flags. It does not import the pricing functions, but shares the saved service mappings and candidate vocabulary. This is a consistency check, not independent ground truth, semantic validation or confidence calibration.")
    story.append(PageBreak())
    story.append(Paragraph(' Decision log',styles['TitleAudit']))
    decisions=[
        ('Scope and sequencing','Develop on labelled H1, then implement H4 rules. Earlier H3/H5 exploration was set aside. The final package executes only H1/H4. A complete computed total is required for submission; incomplete totals are not replaced with subtotals.'),
        ('Identity and amounts','Use nested JSONL record IDs to preserve parentage. Reused invoice IDs and unresolved duplicate allocations prevent selected totals. Money remains integer cents, with Decimal and half-up rounding. Any selected amount difference is explicitly labelled recomputed_total_mismatch in addition to existing findings.'),
        ('Mapping and reviewed inference',f"Abbreviations and compatible contract terms identify services without using billed prices or labels. Four H4 descriptions omit a qualifier but retain specialty and service terms; each has one compatible contractual candidate and is tagged mapped_reviewed_inference. {summary['contains_inferred_mapping']} selected invoices contain these mappings. Uniqueness within the contract is an assumption, not proof that an unknown service could not have a similar description."),
        ('Daily groups and exclusions','Daily quantities aggregate by patient, service and date across records. A known candidate list that excludes the current service does not block its daily count; an unclassified description with no candidates still does. Exclusion-trigger services are distinguished from the services being excluded. Exact window boundaries are withheld for review. This reading is deliberately unresolved rather than a claim that contract boundaries are exclusive.'),
        ('Utilisation and duplicate charges','Discounts use prior utilisation, strict threshold exceedance and service-date/line-ID ordering. Lower/upper bounds must agree before pricing; this conservatism depends on the candidate vocabulary. Repeated services on a patient-day generate review evidence without automatically retaining or removing any charge.'),
        ('Confidence and calibration',f"The confidence field concerns row correctness, including the amount. Values are subjective and uncalibrated: {config['direct_mapping_confidence']} for complete calculations without identified patient-level inference exposure, {config['inference_exposed_confidence']} when an inferred mapping appears anywhere in the same patient's records. {summary['inference_exposed']} selected rows receive the latter value. Same-patient exposure is conservative, not an exact dependency proof. Global utilisation or unidentified mapping risk can remain. These values are not derived from H1 precision; calibration is unfinished and a material limitation."),
        ('AI assistance and prompt history','An AI assistant substantially wrote and revised code, tests, mappings and report prose; the candidate supplied context and ran scripts interactively. No LLM/API is called at runtime. prompts/ contains selected authentic user requests, dated source snapshots and a retrospective change record; it is not an exhaustive original transcript. Git commits created during final packaging are not presented as contemporaneous development history.'),
        ('Time and next steps',config['time_note']+' With another week: validate inferred mappings and unresolved units, implement comparable H1 pricing to evaluate full-row confidence, test independent invoice-level calibration, resolve boundary clauses with the task owner, and extend hospital coverage. No claim of full H4 coverage is made.'),
    ]
    for title,body in decisions:h(title);p(body)
    def footer(canvas,doc):
        canvas.setStrokeColor(colors.HexColor('#c7d4da'));canvas.line(34,33,A4[0]-34,33)
        canvas.setFont('Helvetica',8);canvas.drawString(34,21,'Partial coverage; development evaluation; uncalibrated confidence.')
        canvas.drawRightString(A4[0]-34,21,f'{doc.page} / 2')
    SimpleDocTemplate(str(ROOT/'reports/report.pdf'),pagesize=A4,leftMargin=34,rightMargin=34,topMargin=28,bottomMargin=43).build(story,onFirstPage=footer,onLaterPages=footer)
    decision_md='# Decision log\n\n'+'\n\n'.join(f'## {title}\n\n{body}' for title,body in decisions)+'\n'
    (ROOT/'reports/decision_log.md').write_text(decision_md,encoding='utf-8')
    (ROOT/'reports/detection_metrics.json').write_text(json.dumps(dict(tp=tp,fp=fp,fn=fn,tn=tn,precision=precision,recall=recall,f1=f1,accuracy=accuracy),indent=2),encoding='utf-8')


if __name__=='__main__':main()
