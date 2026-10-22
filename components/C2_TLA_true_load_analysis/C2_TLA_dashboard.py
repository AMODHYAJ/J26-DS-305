"""React workbench services, sharing the existing research engine."""
from functools import lru_cache
from pathlib import Path
from datetime import date
from typing import Literal
import json
import os
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator
from C2_TLA_core import reconstruct, consistency, solar_profile, TZ
from C2_TLA_ingest import prepare_ceb
from C2_TLA_synthetic import generate
from C2_TLA_model import ROOT, MODELS, DEMO, load, predict, explain


class Selection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source: Literal['ceb','synthetic']='synthetic'
    ceb_path: str=Field(default='',max_length=2000)
    feeder_id: str | None=None
    start: date | None=None
    end: date | None=None
    method: Literal['direct_solar_addition','xgboost']='direct_solar_addition'
    threshold_mw: FiniteFloat=Field(default=10,gt=0)
    derating: FiniteFloat=Field(default=.8,ge=.35,le=1)
    capacity_scale: FiniteFloat=Field(default=1,ge=0,le=2)
    @model_validator(mode='after')
    def dates(self):
        if self.start and self.end and self.start>self.end: raise ValueError('Start date must be on or before end date.')
        return self


def default_path():
    return os.environ.get('C2_TLA_CEB_PATH',str(Path.home()/'Downloads'/'CEB_data'))


def fingerprint(path):
    p=Path(path)
    if (p/'CEB_data').is_dir(): p=p/'CEB_data'
    if p.is_dir():
        return tuple((str(f),f.stat().st_mtime_ns,f.stat().st_size) for f in sorted(p.glob('*.xlsx')))
    cached=ROOT/'C2_TLA_outputs'/'C2_TLA_ceb_reconstruction.csv'
    return (cached.stat().st_mtime_ns,) if cached.exists() else ()


@lru_cache(maxsize=3)
def source_data(source,path,stamp):
    if source=='synthetic': return generate(days=120)
    if path and Path(path).is_dir(): return prepare_ceb(path)
    cached=ROOT/'C2_TLA_outputs'/'C2_TLA_ceb_reconstruction.csv'
    if (not path or path==default_path()) and cached.exists():
        d=pd.read_csv(cached); d['timestamp']=pd.to_datetime(d.timestamp,utc=True).dt.tz_convert(TZ)
        d.attrs['input_cache']=True
        return d
    raise ValueError('CEB directory not found. Enter the extracted CEB_data directory, or explicitly select Synthetic demonstration.')


def get_data(q):
    path=q.ceb_path.strip() or default_path()
    return source_data(q.source,path,fingerprint(path) if q.source=='ceb' else ())


def selected(q):
    base=get_data(q)
    if q.feeder_id is None: raise ValueError('Select a feeder before requesting analysis.')
    if q.feeder_id not in base.feeder_id.unique(): raise ValueError('Feeder does not belong to the selected data source. Reload its catalog.')
    d=base[base.feeder_id.eq(q.feeder_id)].copy()
    dates=d.timestamp.dt.date
    if q.start: d=d.loc[dates>=q.start]
    if q.end: d=d.loc[d.timestamp.dt.date<=q.end]
    if d.empty: raise ValueError('No observations in that date range. Choose dates within the source range.')
    d=d.sort_values(['feeder_id','timestamp']).reset_index(drop=True)
    if q.source=='ceb':
        if base.attrs.get('input_cache') and (q.derating!=.8 or q.capacity_scale!=1):
            raise ValueError('Sensitivity controls require the extracted CEB source directory; the cached estimate cannot establish new assumptions.')
        if not base.attrs.get('input_cache'):
            d['capacity_mw']*=q.capacity_scale
            m,lo,hi=solar_profile(d.timestamp,float(d.capacity_mw.iloc[0]),q.derating)
            d['solar_mw']=m; d['solar_low_mw']=lo; d['solar_high_mw']=hi
    elif q.capacity_scale!=1 or q.derating!=.8:
        raise ValueError('Solar-profile sensitivity controls apply to CEB estimates; the synthetic scenario already includes forecast error.')
    return d


def results(q):
    d=selected(q)
    return predict(d,threshold_mw=q.threshold_mw) if q.method=='xgboost' else reconstruct(d,q.threshold_mw)


def clean_json(value):
    # Pandas handles null / nonfinite values consistently for browser and API exports.
    return json.loads(pd.Series([value]).to_json(orient='values',date_format='iso'))[0]


def create_router(authorize):
    router=APIRouter(prefix='/v1/dashboard',dependencies=[Depends(authorize)])

    @router.get('/bootstrap')
    def bootstrap():
        path=default_path()
        return {'default_source':'ceb' if Path(path).is_dir() or (ROOT/'C2_TLA_outputs'/'C2_TLA_ceb_reconstruction.csv').exists() else 'synthetic',
            'ceb_path':path,'timezone':TZ,'schema_version':'c2.tla.dashboard.v1'}

    @router.post('/catalog')
    def catalog(q:Selection):
        try:
            d=get_data(q)
            return {'feeders':sorted(d.feeder_id.unique()),'start':str(d.timestamp.dt.date.min()),'end':str(d.timestamp.dt.date.max()),
                'rows':len(d),'source':q.source,'input_cache':d.attrs.get('input_cache',False)}
        except (ValueError,OSError,KeyError) as e: raise HTTPException(422,str(e)) from e

    @router.post('/analyze')
    def analyze(q:Selection):
        try:
            r=results(q)
            values=r.true_mw.dropna()
            vli=r.vli.dropna()
            peak=r.loc[r.true_mw.idxmax(),'timestamp'] if len(values) else None
            warnings=[]
            if q.source=='ceb':
                warnings.extend(['Measured CEB net MW + estimated solar from real capacity; true demand is not measured.',
                    'Feeder mapping is provisional. Capacity effective dates, other generation, storage and telemetry scaling need CEB confirmation.',
                    'F3, F9 and F10 are excluded without capacity matches. F6–F8 have suspicious near-zero MW channels.'])
            else: warnings.append('Synthetic consumption, solar and forecast errors. Evaluation scores are simulation results, not CEB accuracy.')
            if q.method=='xgboost': warnings.append('XGBoost was trained on synthetic latent PV targets. Transfer to CEB and its uncertainty coverage are unvalidated.')
            if r.net_mw.abs().max()<.01: warnings.append('Near-zero telemetry channel: confirm scaling and channel availability before interpreting demand.')
            if r.true_mw.lt(0).any(): warnings.append('Some reconstructed demand remains negative: the solar estimate or feeder boundary is inconsistent with observed export.')
            quality=r.quality_flags.str.split(';').explode(); counts=quality[quality.ne('')].value_counts().to_dict()
            evfile=MODELS/'C2_TLA_evaluation.json'
            if not evfile.exists(): evfile=DEMO/'C2_TLA_evaluation.json'
            evaluation=json.loads(evfile.read_text(encoding='utf-8')) if evfile.exists() else None
            return clean_json({'records':json.loads(r.to_json(orient='records',date_format='iso')),
                'summary':{'true_peak_mw':float(values.max()) if len(values) else None,'hidden_peak_mw':float(r.hidden_mw.max()),
                    'reverse_intervals':int(r.reverse_flow.sum()),'hidden_crossings':int(r.hidden_threshold_crossing.sum()),
                    'peak_time':str(peak) if peak is not None else None,'max_vli':float(vli.max()) if len(vli) else None,
                    'rows':len(r),'flagged':int(r.quality_flags.ne('').sum()),'capacity_mw':float(r.capacity_mw.iloc[0])},
                'quality_counts':counts,'warnings':warnings,'consistency':consistency(r),'evaluation':evaluation,
                'source':q.source,'method':q.method,'timezone':TZ})
        except (ValueError,OSError,KeyError) as e: raise HTTPException(422,str(e)) from e

    @router.post('/explain')
    def explanations(q:Selection):
        try:
            d=selected(q)
            # Evenly spaced sample spans the entire selection and includes both endpoints.
            d=d.iloc[np.linspace(0,len(d)-1,min(384,len(d)),dtype=int)].reset_index(drop=True)
            values,info=explain(d)
            _,meta=load()
            return {'timestamps':d.timestamp.astype(str).tolist(),'contributions':values.to_dict(orient='records'),
                'global_contributions':values.abs().mean().sort_values(ascending=False).to_dict(),'info':info,'metadata':meta,
                'provenance':'synthetic-trained XGBoost; SHAP explains raw hidden MW, with physical correction separately reported'}
        except (ValueError,OSError,KeyError) as e: raise HTTPException(422,str(e)) from e

    @router.post('/export')
    def export(q:Selection,format:Literal['csv','json']='csv'):
        try:
            r=results(q)
            body=r.to_csv(index=False) if format=='csv' else r.to_json(orient='records',date_format='iso')
            return Response(body,media_type='text/csv' if format=='csv' else 'application/json',
                headers={'Content-Disposition':f'attachment; filename="C2_TLA_selected_results.{format}"'})
        except (ValueError,OSError,KeyError) as e: raise HTTPException(422,str(e)) from e
    return router
