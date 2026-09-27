"""Reproduce the final H1/H4 audit from this folder, regardless of shell cwd."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent


def main():
    reports=ROOT/'reports';reports.mkdir(exist_ok=True)
    steps=[('audit.py',['--hospital','1']),('evaluate_h1.py',[]),
           ('analyze_false_negatives.py',[]),('audit.py',['--hospital','4']),
           ('audit_bundles.py',[]),('audit_discounts.py',[]),('audit_exclusions.py',[]),
           ('audit_duplicates.py',[]),('audit_total.py',[]),('build_submission.py',[]),
           ('verify_selected.py',[]),('build_report.py',[])]
    with (reports/'run.log').open('w',encoding='utf-8') as log:
        for name,args in steps:
            print('Running',name,*args,flush=True)
            result=subprocess.run([sys.executable,str(ROOT/name),*args],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
            log.write(f'\n{name} {args}\n{result.stdout}\n{result.stderr}');log.flush()
            if result.returncode:
                print(result.stdout+result.stderr)
                raise RuntimeError(f'{name} failed; see reports/run.log')
    subprocess.run([sys.executable,str(ROOT/'tests/test_checks.py')],cwd=ROOT,check=True)
    inputs=[p for folder in ['contracts','invoices','labels'] for p in (ROOT/folder).rglob('*') if p.is_file()]
    manifest={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inputs)}
    (reports/'input_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('DONE: submission.csv and reports/report.pdf')
    print((reports/'submission_summary.json').read_text(encoding='utf-8'))


if __name__=='__main__':
    main()
