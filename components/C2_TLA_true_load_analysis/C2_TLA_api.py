"""Versioned local integration endpoint. Bind to loopback; token optional locally."""
from datetime import datetime
from typing import Literal
import json
import os
import secrets
import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel, Field, ConfigDict, AwareDatetime, FiniteFloat, model_validator
from C2_TLA_core import reconstruct
from C2_TLA_model import predict

app=FastAPI(title='C2 True Load Analysis',version='1.0.0')


def authorize(authorization: str | None=Header(default=None)):
    token=os.environ.get('C2_TLA_API_TOKEN')
    if token and not secrets.compare_digest(authorization or '', 'Bearer '+token):
        raise HTTPException(401,'A valid Bearer token is required.')


class InputRow(BaseModel):
    model_config=ConfigDict(extra='forbid')
    feeder_id: str=Field(min_length=1,max_length=120)
    timestamp: AwareDatetime
    units: Literal['MW']
    net_mw: FiniteFloat | None
    solar_mw: FiniteFloat=Field(ge=0)
    solar_low_mw: FiniteFloat=Field(ge=0)
    solar_high_mw: FiniteFloat=Field(ge=0)
    capacity_mw: FiniteFloat=Field(ge=0)
    provenance: str=Field(min_length=3,max_length=500)
    @model_validator(mode='after')
    def interval(self):
        if not self.solar_low_mw<=self.solar_mw<=self.solar_high_mw<=self.capacity_mw:
            raise ValueError('Require 0 <= solar low <= median <= high <= installed capacity MW.')
        return self


class Request(BaseModel):
    model_config=ConfigDict(extra='forbid')
    records: list[InputRow]=Field(min_length=1,max_length=40000)
    threshold_mw: FiniteFloat=Field(default=10,gt=0)
    method: Literal['direct_solar_addition','xgboost']='direct_solar_addition'


class OutputRow(BaseModel):
    model_config=ConfigDict(extra='allow')
    feeder_id: str
    timestamp: AwareDatetime
    units: Literal['MW']
    apparent_mw: float | None
    hidden_mw: float
    true_mw: float | None
    residual_mw: float | None
    true_low_mw: float | None
    true_high_mw: float | None
    vli: float | None
    reverse_flow: bool
    threshold_exceeded: bool
    hidden_threshold_crossing: bool
    threshold_mw: float
    peak: bool
    method: str
    provenance: str
    quality_flags: str


class Response(BaseModel):
    schema_version: Literal['c2.tla.v1']='c2.tla.v1'
    timezone: str='Asia/Colombo'
    boundary: str='feeder import; gross demand plus downstream losses; other generation/storage unobserved'
    records: list[OutputRow]


@app.get('/health')
def health():
    from C2_TLA_model import load
    try: load(); ready=True
    except (ValueError,OSError): ready=False
    return {'status':'ok','model_ready':ready,'live_c1_service':False,'live_c4_integration':False}


@app.post('/v1/reconstruct',response_model=Response,dependencies=[Depends(authorize)])
def run(request: Request):
    d=pd.DataFrame([r.model_dump() for r in request.records])
    try:
        for _,g in d.groupby('feeder_id'):
            ts=pd.to_datetime(g.timestamp,utc=True).sort_values()
            delta=ts.diff().dropna().dt.total_seconds()
            if delta.nunique()>1: raise ValueError('Inconsistent intervals within feeder. Send a regular series or separate gap-free requests.')
        result=predict(d,threshold_mw=request.threshold_mw) if request.method=='xgboost' else reconstruct(d,request.threshold_mw)
        records=json.loads(result.to_json(orient='records',date_format='iso'))
        return Response(records=records)
    except (ValueError,TypeError,KeyError) as e:
        raise HTTPException(422,str(e)) from e


# Same-origin React workbench; no CORS service or separate development server needed.
from pathlib import Path
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from C2_TLA_dashboard import create_router

app.include_router(create_router(authorize))
WEB=Path(__file__).resolve().parent/'C2_TLA_web'
app.mount('/C2_TLA_assets',StaticFiles(directory=WEB/'C2_TLA_assets',check_dir=False),name='C2_TLA_assets')


@app.get('/',include_in_schema=False)
def workbench():
    index=WEB/'C2_TLA_index.html'
    if not index.exists():
        return HTMLResponse('<h1>C2 React UI needs a build</h1><p>Run C2_TLA_launch.cmd build-ui, then refresh.</p>',status_code=503)
    return FileResponse(index,headers={'Cache-Control':'no-cache'})
