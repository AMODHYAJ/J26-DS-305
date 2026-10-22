"""Integrate C2 with the C3 implementation actually present on current main."""
from pathlib import Path
import json
import math
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from C2_TLA_dashboard import Selection, selected
from C2_TLA_model import ROOT

REPO=ROOT.parents[1]
C3_DIR=REPO/'components'/'gis_risk_mapper'
C3_SNAPSHOT=ROOT/'C2_TLA_outputs'/'C2_TLA_c3_transformer_risk.json'


def validate_snapshot(payload):
    meta=payload.get('metadata',{})
    if meta.get('data_basis')!='REAL_CEB_ATTRIBUTES_PLUS_SYNTHETIC_OPERATING_SCENARIOS':
        raise ValueError('C3 data basis is unsupported. Preserve measured-attribute / synthetic-score provenance.')
    rows=payload.get('transformers',[])
    if not rows or len(rows)!=meta.get('transformer_count'): raise ValueError('C3 transformer count does not match metadata.')
    seen=set()
    for row in rows:
        key=(row.get('csc'),row.get('sin'))
        if not all(key) or key in seen: raise ValueError('C3 requires unique, nonempty compound (CSC, SIN) identifiers.')
        seen.add(key)
        if not row.get('gss') or not row.get('feeder'): raise ValueError('C3 GSS/feeder identifiers are missing.')
        for field in ['kva','solar_kw']:
            v=row.get(field)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 or (field=='kva' and v==0):
                raise ValueError(f'C3 {field} must be finite with explicit nameplate kVA / solar kW units.')
        prob=row.get('synthetic_day_prediction',{}).get('predicted_export_probability')
        if isinstance(prob,bool) or not isinstance(prob,(int,float)) or not math.isfinite(prob) or not 0<=prob<=1:
            raise ValueError('C3 simulated classifier score is outside [0,1].')
        if row.get('synthetic_summary',{}).get('tier') not in ['Low','Medium','High']:
            raise ValueError('C3 synthetic exposure tier is invalid.')
        if row['synthetic_day_prediction'].get('date')!=meta.get('simulated_date'):
            raise ValueError('C3 simulated dates do not match snapshot metadata.')
    return payload


def read_snapshot():
    # Prefer the explicitly generated, prefixed local integration artifact.
    path=C3_SNAPSHOT if C3_SNAPSHOT.exists() else C3_DIR/'output'/'transformer_risk.json'
    if not path.exists(): raise ValueError('C3 snapshot is not prepared. Run the documented prepare-team step; no synthetic fallback is substituted.')
    return validate_snapshot(json.loads(path.read_text(encoding='utf-8')))


def feeder_context(q,payload):
    meta=payload['metadata']
    if q.source!='ceb':
        return {'status':'synthetic_ids_not_joined','transformers':[],
            'message':'Synthetic C2 feeders are not mapped to real CEB transformer IDs.','metadata':meta}
    # Same explicit provisional ordinal crosswalk used by C2 ingestion; no fuzzy matching.
    crosswalk={f'3_EMBIL_F{i}':('Embilipitiya',f'Feeder {i:02d}') for i in range(1,11)}
    if q.feeder_id not in crosswalk: raise ValueError('No explicit C2-to-C3 crosswalk for the selected feeder.')
    gss,feeder=crosswalk[q.feeder_id]
    rows=[r for r in payload['transformers'] if r['gss']==gss and r['feeder']==feeder]
    d=selected(q)
    c2_capacity=float(d.capacity_mw.iloc[0])
    c3_capacity=sum(r['solar_kw'] for r in rows)/1000
    tiers={tier:sum(r['synthetic_summary']['tier']==tier for r in rows) for tier in ['Low','Medium','High']}
    return {'status':'matched_provisional' if rows else 'no_exact_matches','transformers':rows,'metadata':meta,
        'mapping':{'c2_feeder':q.feeder_id,'c3_gss':gss,'c3_feeder':feeder,'status':'PROVISIONAL — exact GSS and feeder ordinal; not CEB approved'},
        'transformer_count':len(rows),'mapped_count':sum(bool(r.get('has_coordinates')) for r in rows),
        'c3_solar_capacity_mw':c3_capacity,'c2_scenario_capacity_mw':c2_capacity,
        'capacity_difference_mw':c2_capacity-c3_capacity,'tiers':tiers,
        'time_alignment':'Context only: C3 scores are a synthetic snapshot, not observations simultaneous with the selected C2 period.',
        'message':'C3 transformer attributes join by explicit feeder context. Its exposure scores are not used as measured demand or as validated curtailment instructions.'}


def create_team_router(authorize):
    router=APIRouter()

    @router.get('/c3/',include_in_schema=False)
    def c3_page():
        path=ROOT/'C2_TLA_web'/'C2_TLA_C3_index.html'
        if not path.exists(): raise HTTPException(503,'Build the shared React workspace with C2_TLA_launch.cmd build-ui.')
        return FileResponse(path,headers={'Cache-Control':'no-cache'})

    @router.get('/data/transformer_risk.json',dependencies=[Depends(authorize)],include_in_schema=False)
    def c3_data():
        try:return read_snapshot()
        except (ValueError,OSError) as e: raise HTTPException(503,str(e)) from e

    @router.get('/v1/integration/status',dependencies=[Depends(authorize)])
    def status():
        try:
            p=read_snapshot(); c3={'connected':True,'transformers':len(p['transformers']),'data_basis':p['metadata']['data_basis']}
        except (ValueError,OSError) as e:c3={'connected':False,'message':str(e)}
        return {'c2':{'connected':True,'interface':'React/FastAPI'},'c3':c3,
            'c4':{'connected':False,'reason':'Current main contains only components/curtailment_prioritizer/.gitkeep; no C4 implementation was imported from another branch.'}}

    @router.post('/v1/integration/c3-context',dependencies=[Depends(authorize)])
    def context(q:Selection):
        try:return feeder_context(q,read_snapshot())
        except (ValueError,OSError,KeyError) as e: raise HTTPException(422,str(e)) from e
    return router
