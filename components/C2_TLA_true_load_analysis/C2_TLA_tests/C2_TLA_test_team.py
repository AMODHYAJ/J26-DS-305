from pathlib import Path
import sys
import copy
import json
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from C2_TLA_api import app
from C2_TLA_dashboard import Selection
import C2_TLA_team as team


@pytest.fixture
def snapshot():
    rows=[]
    for i in [1,2]:
        rows.append({'csc':'MOCK_CSC','sin':f'MOCK_R{i}','gss':'Embilipitiya','feeder':'Feeder 02',
            'kva':250,'solar_kw':i*100,'has_coordinates':False,
            'synthetic_summary':{'tier':'High' if i==1 else 'Low','exposure_score':.5,'priority_rank':i},
            'synthetic_day_prediction':{'predicted_export_probability':.6,'date':'2026-02-22'}})
    return {'metadata':{'data_basis':'REAL_CEB_ATTRIBUTES_PLUS_SYNTHETIC_OPERATING_SCENARIOS','transformer_count':2,'simulated_date':'2026-02-22'},'transformers':rows}


@pytest.mark.parametrize('case',['duplicate','probability','units','basis','date'])
def test_c3_handover_validation(snapshot,case):
    bad=copy.deepcopy(snapshot)
    if case=='duplicate':bad['transformers'][1]['sin']=bad['transformers'][0]['sin']
    if case=='probability':bad['transformers'][0]['synthetic_day_prediction']['predicted_export_probability']=1.1
    if case=='units':bad['transformers'][0]['solar_kw']=float('inf')
    if case=='basis':bad['metadata']['data_basis']='measured_risk'
    if case=='date':bad['transformers'][0]['synthetic_day_prediction']['date']='2026-01-01'
    with pytest.raises(ValueError):team.validate_snapshot(bad)


def test_explicit_c2_c3_join_units_provenance_and_no_synthetic_id_matching(snapshot,monkeypatch):
    monkeypatch.setattr(team,'selected',lambda _:pd.DataFrame({'capacity_mw':[.6]}))
    q=Selection(source='ceb',feeder_id='3_EMBIL_F2')
    result=team.feeder_context(q,team.validate_snapshot(snapshot))
    assert result['transformer_count']==2
    assert result['c3_solar_capacity_mw']==pytest.approx(.3)
    assert result['capacity_difference_mw']==pytest.approx(.3)
    assert 'PROVISIONAL' in result['mapping']['status']
    assert 'synthetic snapshot' in result['time_alignment']
    assert result['tiers']=={'Low':1,'Medium':0,'High':1}
    assert team.feeder_context(Selection(source='synthetic',feeder_id='SYNTHETIC_F2'),snapshot)['status']=='synthetic_ids_not_joined'
    with pytest.raises(ValueError):team.feeder_context(Selection(source='ceb',feeder_id='similar_F2'),snapshot)


def test_shared_c3_data_route_and_missing_input_are_explicit(snapshot,tmp_path,monkeypatch):
    path=tmp_path/'C2_TLA_c3_snapshot.json'; path.write_text(json.dumps(snapshot),encoding='utf-8')
    monkeypatch.setattr(team,'C3_SNAPSHOT',path)
    client=TestClient(app)
    response=client.get('/data/transformer_risk.json')
    assert response.status_code==200 and len(response.json()['transformers'])==2
    status=client.get('/v1/integration/status').json()
    assert status['c3']['connected'] and status['c4']['connected'] is False
    monkeypatch.setenv('C2_TLA_API_TOKEN','shared-test')
    assert client.get('/data/transformer_risk.json').status_code==401
    assert client.get('/data/transformer_risk.json',headers={'Authorization':'Bearer shared-test'}).status_code==200
    monkeypatch.setattr(team,'C3_SNAPSHOT',tmp_path/'C2_TLA_missing.json')
    monkeypatch.setattr(team,'C3_DIR',tmp_path/'C2_TLA_missing_component')
    missing=client.get('/data/transformer_risk.json',headers={'Authorization':'Bearer shared-test'})
    assert missing.status_code==503 and 'not prepared' in missing.json()['detail']


@pytest.mark.skipif(not team.C3_SNAPSHOT.exists(),reason='Run prepare-team for actual current-main C3 snapshot check')
def test_actual_current_main_c3_snapshot():
    p=team.read_snapshot()
    assert len(p['transformers'])==357
    assert sum(r['has_coordinates'] for r in p['transformers'])==62
    assert p['metadata']['data_basis']=='REAL_CEB_ATTRIBUTES_PLUS_SYNTHETIC_OPERATING_SCENARIOS'
