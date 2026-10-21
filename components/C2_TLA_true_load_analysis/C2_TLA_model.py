"""Small CPU XGBoost experiment, portable UBJ serialization and Tree SHAP."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import xgboost as xgb
from C2_TLA_core import TZ, validate, reconstruct

FEATURES=['net_mw','solar_mw','capacity_mw','sin_hour','cos_hour','day_of_week']
ROOT=Path(__file__).resolve().parent
MODELS=ROOT/'C2_TLA_models'
DEMO=ROOT/'C2_TLA_demo'


def features(d):
    ts=pd.to_datetime(d.timestamp,utc=True).dt.tz_convert(TZ)
    h=ts.dt.hour+ts.dt.minute/60
    x=d[['net_mw','solar_mw','capacity_mw']].copy()
    if not np.isfinite(x[['solar_mw','capacity_mw']]).all().all() or (x.capacity_mw<=0).any():
        raise ValueError('Inference requires finite solar and positive installed capacity MW.')
    if np.isinf(x.net_mw).any(): raise ValueError('Infinite net MW cannot be imputed.')
    x['sin_hour']=np.sin(2*np.pi*h/24); x['cos_hour']=np.cos(2*np.pi*h/24); x['day_of_week']=ts.dt.dayofweek
    return x[FEATURES].astype(float)


def splits(d):
    times=np.sort(d.timestamp.unique())
    if len(times)<96*10: raise ValueError('Need at least ten days for chronological training/calibration/test.')
    a,b=times[int(len(times)*.6)],times[int(len(times)*.8)]
    return d.timestamp<a,(d.timestamp>=a)&(d.timestamp<b),d.timestamp>=b


def metrics(y,p,timestamps):
    y=np.asarray(y,float); p=np.asarray(p,float); ok=np.isfinite(y)&np.isfinite(p)
    y=y[ok]; p=p[ok]; t=pd.DatetimeIndex(timestamps)[ok]
    if len(y)==0: return {'n':0}
    err=p-y; nonzero=np.abs(y)>1e-3
    daily=pd.DataFrame({'t':t,'y':y,'p':p}); daily['day']=daily.t.dt.date
    timing=[]; recovery=[]
    for _,g in daily.groupby('day'):
        iy=g.y.idxmax(); ip=g.p.idxmax()
        timing.append(abs((daily.loc[iy,'t']-daily.loc[ip,'t']).total_seconds())/60)
        if g.y.max()>1e-3: recovery.append(g.p.max()/g.y.max()*100)
    denom=((y-y.mean())**2).sum()
    return {'n':len(y),'mae_mw':float(np.abs(err).mean()),'rmse_mw':float(np.sqrt((err**2).mean())),
        'r2':float(1-(err**2).sum()/denom) if denom else None,
        'mape_pct':float((np.abs(err[nonzero])/np.abs(y[nonzero])).mean()*100) if nonzero.any() else None,
        'mape_excluded_zero_reference':int((~nonzero).sum()),
        'daily_peak_magnitude_recovery_pct':float(np.mean(recovery)) if recovery else None,
        'daily_peak_timing_mae_minutes':float(np.mean(timing))}


def physical(raw,d):
    h=np.clip(raw,0,d.capacity_mw.to_numpy())
    ts=pd.to_datetime(d.timestamp,utc=True).dt.tz_convert(TZ)
    hour=ts.dt.hour+ts.dt.minute/60
    return np.where((hour<=6)|(hour>=18),0,h)


def train(d, model_dir=MODELS,seed=23177000):
    if 'target_hidden_mw' not in d or not d.provenance.str.startswith('synthetic').all():
        raise ValueError('This experiment accepts explicitly synthetic labelled targets only.')
    d=validate(d); x=features(d); tr,va,te=splits(d)
    med=x.loc[tr].median().to_dict(); x=x.fillna(med)
    params={'objective':'reg:squarederror','max_depth':4,'eta':.06,'subsample':.9,'colsample_bytree':.9,'seed':seed,'nthread':2,'tree_method':'hist'}
    booster=xgb.train(params,xgb.DMatrix(x.loc[tr],label=d.loc[tr,'target_hidden_mw']),num_boost_round=100)
    raw=booster.predict(xgb.DMatrix(x)); pred=physical(raw,d)
    errors=np.abs(pred[va]-d.loc[va,'target_hidden_mw'].to_numpy())
    # Finite sample split-conformal 90% quantile, under exchangeability only.
    level=min(1,np.ceil((len(errors)+1)*.9)/len(errors))
    q=float(np.quantile(errors,level,method='higher'))
    md=Path(model_dir); md.mkdir(parents=True,exist_ok=True)
    metadata={'features':FEATURES,'imputation_medians':med,'preprocessing':'numeric MW; train-only medians, no scaling, no target-derived or future/billing features',
        'seed':seed,'params':params,'rounds':100,'target_provenance':'synthetic latent PV generation; not measured CEB ground truth',
        'split_dates':{name:[str(d.loc[mask,'timestamp'].min()),str(d.loc[mask,'timestamp'].max())] for name,mask in [('train',tr),('calibration',va),('test',te)]},
        'train_feature_ranges':{c:[float(x.loc[tr,c].min()),float(x.loc[tr,c].max())] for c in FEATURES},
        'calibration_absolute_error_q90_mw':q,'units':'MW','xgboost_version':xgb.__version__,
        'postprocessing':'clip hidden to [0,capacity]; force zero outside 06:00–18:00. SHAP explains raw prediction; correction reported separately.'}
    booster.save_model(md/'C2_TLA_model.ubj')
    (md/'C2_TLA_model_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    test=d.loc[te].copy(); test['pred_hidden_mw']=pred[te]
    # Historical baseline fit only on train synthetic true demand; no validation/test aggregates.
    clock=pd.to_datetime(d.timestamp,utc=True).dt.tz_convert(TZ).dt.strftime('%H:%M')
    hist=d.loc[tr].assign(clock=clock[tr]).groupby(['feeder_id','clock']).target_true_mw.mean()
    hist_pred=np.array([hist.get((f,c),d.loc[tr,'target_true_mw'].mean()) for f,c in zip(test.feeder_id,clock[te])])
    methods={'apparent':test.net_mw.to_numpy(),'direct_solar_addition':(test.net_mw+test.solar_mw).to_numpy(),
        'historical_profile':hist_pred,'xgboost':(test.net_mw+pred[te]).to_numpy()}
    report={'provenance':'SYNTHETIC held-out chronological experiment; no CEB accuracy validation',
        'split_dates':metadata['split_dates'],'benchmarks':{},'uncertainty_nominal':.9,
        'hidden_interval_coverage':float(np.mean((test.target_hidden_mw>=np.maximum(0,pred[te]-q))&(test.target_hidden_mw<=np.minimum(test.capacity_mw,pred[te]+q)))),
        'calibration_q90_mw':q,'scenarios':{}}
    # Compute daily peak metrics separately by feeder to avoid comparing unrelated boundaries.
    for name,p in methods.items():
        per={}
        for f,g in test.groupby('feeder_id'):
            positions=np.flatnonzero(test.feeder_id.eq(f).to_numpy())
            per[f]=metrics(g.target_true_mw,p[positions],g.timestamp)
        overall=metrics(test.target_true_mw,p,test.timestamp)
        for key in ['daily_peak_magnitude_recovery_pct','daily_peak_timing_mae_minutes']:
            overall[key]=float(np.mean([v[key] for v in per.values() if v[key] is not None]))
        report['benchmarks'][name]={'overall':overall,'by_feeder':per}
    for name,g in test.groupby('scenario'):
        summary=metrics(g.target_true_mw,g.net_mw+g.pred_hidden_mw,g.timestamp)
        per=[metrics(f.target_true_mw,f.net_mw+f.pred_hidden_mw,f.timestamp) for _,f in g.groupby('feeder_id')]
        for key in ['daily_peak_magnitude_recovery_pct','daily_peak_timing_mae_minutes']:
            summary[key]=float(np.mean([v[key] for v in per if v[key] is not None]))
        report['scenarios'][name]=summary
    (md/'C2_TLA_evaluation.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    return booster,metadata,report


def load(model_dir=MODELS):
    md=Path(model_dir)
    if md==MODELS and not (md/'C2_TLA_model.ubj').is_file() and (DEMO/'C2_TLA_model.ubj').is_file(): md=DEMO
    if not (md/'C2_TLA_model.ubj').is_file():
        raise ValueError('Model missing. Run C2_TLA_launch.cmd prepare to create the demo model.')
    meta=json.loads((md/'C2_TLA_model_metadata.json').read_text(encoding='utf-8'))
    if meta['features']!=FEATURES: raise ValueError('Saved feature schema differs; retrain this model.')
    b=xgb.Booster(); b.load_model(md/'C2_TLA_model.ubj'); b.set_param({'nthread':2})
    return b,meta


def predict(d, model_dir=MODELS, threshold_mw=10.):
    d=validate(d); b,meta=load(model_dir); x=features(d).fillna(meta['imputation_medians'])
    dm=xgb.DMatrix(x); raw=b.predict(dm); h=physical(raw,d)
    out=reconstruct(d,threshold_mw,hidden=h,method='xgboost_synthetic_training_experiment')
    q=meta['calibration_absolute_error_q90_mw']
    out['true_low_mw']=out.net_mw+np.maximum(0,h-q)
    out['true_high_mw']=out.net_mw+np.minimum(out.capacity_mw,h+q)
    out['raw_hidden_mw']=raw; out['physical_correction_mw']=h-raw
    out['quality_flags']+=';synthetic_trained_model;interval_coverage_not_validated_for_CEB'
    for col,(lo,hi) in meta['train_feature_ranges'].items():
        outside=(x[col]<lo)|(x[col]>hi)
        out.loc[outside,'quality_flags']+=';feature_outside_training_range:'+col
    return out


def explain(d,model_dir=MODELS):
    d=validate(d); b,meta=load(model_dir); x=features(d).fillna(meta['imputation_medians'])
    dm=xgb.DMatrix(x); contributions=b.predict(dm,pred_contribs=True); raw=b.predict(dm)
    error=float(np.max(np.abs(contributions.sum(axis=1)-raw)))
    if error>1e-4: raise ValueError(f'Tree SHAP additivity failed: {error}')
    return pd.DataFrame(contributions[:,:-1],columns=FEATURES),dict(base_mw=contributions[:,-1].tolist(),raw_hidden_mw=raw.tolist(),physical_correction_mw=(physical(raw,d)-raw).tolist(),max_additivity_error_mw=error)
