"""Reproducible component commands: prepare, ceb, audit, and all."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
from C2_TLA_core import reconstruct, consistency
from C2_TLA_synthetic import generate
from C2_TLA_model import train, predict, explain, ROOT
from C2_TLA_ingest import prepare_ceb, audit


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','ceb','audit','all'])
    p.add_argument('--ceb-path',help='Extracted CEB directory; never silently use synthetic data')
    p.add_argument('--days',type=int,default=120)
    args=p.parse_args()
    out=ROOT/'C2_TLA_outputs'; out.mkdir(exist_ok=True)
    if args.command in ['ceb','audit','all'] and not args.ceb_path: p.error('--ceb-path is required for CEB commands')
    scale=4.
    if args.command in ['ceb','all']:
        start=time.perf_counter(); d=prepare_ceb(args.ceb_path); r=reconstruct(d)
        r.to_csv(out/'C2_TLA_ceb_reconstruction.csv',index=False)
        # Actual observed nonzero channels inform simulation magnitude, not simulation labels.
        scale=float(d.loc[d.net_mw.abs()>.01,'net_mw'].abs().median())
        report=consistency(r); report['seconds_including_ingestion']=time.perf_counter()-start
        report['rows']=len(r); report['unmatched_measurement_feeders']=d.attrs.get('unmatched_measurement_feeders',[])
        report['independent_accuracy']='unavailable: no measured true demand or feeder PV generation targets'
        (out/'C2_TLA_ceb_consistency.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
    if args.command in ['prepare','all']:
        start=time.perf_counter(); demo=generate(days=args.days,demand_scale_mw=scale)
        _,meta,report=train(demo)
        predicted=predict(demo)
        sample=demo.iloc[np.linspace(0,len(demo)-1,min(512,len(demo)),dtype=int)]
        values,check=explain(sample)
        report['shap_max_additivity_error_mw']=check['max_additivity_error_mw']
        report['training_and_prediction_seconds']=time.perf_counter()-start
        report['synthetic_demand_scale_mw']=scale
        report['scale_source']='CEB nontrivial measured net absolute median' if args.command=='all' else 'explicit development assumption 4 MW'
        report['global_shap_sample']='up to 512 evenly spaced intervals across feeders and dates'
        (out/'C2_TLA_experiment_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        values.abs().mean().sort_values(ascending=False).rename('mean_absolute_shap_mw').to_csv(out/'C2_TLA_global_shap.csv')
        demo.to_csv(out/'C2_TLA_synthetic.csv',index=False)
        predicted.to_csv(out/'C2_TLA_synthetic_predictions.csv',index=False)
        print('Synthetic model, schema, calibration, predictions and explanations saved.',report['training_and_prediction_seconds'])
    if args.command in ['audit','all']:
        result=audit(args.ceb_path,out)
        print('Audited files:',len(result['files']),'Access tables:',len((result.get('access') or {}).get('tables',[])))


if __name__=='__main__': main()
