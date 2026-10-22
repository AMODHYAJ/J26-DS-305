"""Run main's existing C3 exporter with its known repository model and local inputs."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]


def main():
    model='components/gis_risk_mapper/models/rf_synthetic_export.joblib'
    expected=subprocess.check_output(['git','rev-parse','origin/main:'+model],cwd=REPO,text=True).strip()
    actual=subprocess.check_output(['git','hash-object',model],cwd=REPO,text=True).strip()
    if actual!=expected:
        raise SystemExit('C3 model differs from the known current-main artifact. Review it before running its joblib exporter; arbitrary model files are not loaded.')
    target=ROOT/'C2_TLA_outputs'/'C2_TLA_c3_transformer_risk.json'
    subprocess.run([sys.executable,str(REPO/'components'/'gis_risk_mapper'/'predict_risk.py'),'--output',str(target)],cwd=REPO,check=True)
    from C2_TLA_team import read_snapshot
    p=read_snapshot()
    print('Connected current-main C3 snapshot:',len(p['transformers']),'transformers; synthetic risk provenance retained.')


if __name__=='__main__': main()
