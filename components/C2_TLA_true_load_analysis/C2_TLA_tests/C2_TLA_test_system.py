import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from C2_TLA_core import reconstruct, solar_profile, validate, consistency
from C2_TLA_synthetic import generate
from C2_TLA_model import train, predict, explain, features, splits, load, FEATURES
from C2_TLA_adapters import c1_forecast, csi_to_power, interval_meter_energy, monthly_energy, c3_static_load
from C2_TLA_ingest import prepare_ceb, load_measurements, capacities
from C2_TLA_api import app


@pytest.fixture
def example():
    return pd.DataFrame({'feeder_id':['F1']*4,'timestamp':pd.date_range('2026-07-01 10:00',periods=4,freq='15min',tz='Asia/Colombo'),
        'net_mw':[-1.,0.,np.nan,2.], 'solar_mw':[2.]*4,'solar_low_mw':[1.]*4,'solar_high_mw':[3.]*4,'capacity_mw':[4.]*4})


def test_balance_export_zero_missing_and_vli(example):
    d=reconstruct(example,1.5)
    assert d.true_mw.iloc[0]==1 and d.vli.iloc[0]==2
    assert d.reverse_flow.iloc[0] and d.hidden_threshold_crossing.iloc[1]
    assert 'zero_net_review' in d.quality_flags.iloc[1]
    assert pd.isna(d.true_mw.iloc[2]) and d.threshold_status.iloc[2]=='unknown_missing_measurement'
    np.testing.assert_allclose(d.residual_mw,d.net_mw,equal_nan=True)
    example.loc[0,'net_mw']=-3
    bad=reconstruct(example)
    assert bad.true_mw.iloc[0]==-1 and pd.isna(bad.vli.iloc[0])
    assert 'solar_or_boundary_inconsistent' in bad.quality_flags.iloc[0]


@pytest.mark.parametrize('case',['duplicate','naive','inf','negative_solar','inverted_interval','missing_key','empty_id'])
def test_invalid_inputs(example,case):
    if case=='duplicate': example=pd.concat([example,example.iloc[:1]])
    if case=='naive': example['timestamp']=example.timestamp.dt.tz_localize(None)
    if case=='inf': example.loc[0,'net_mw']=np.inf
    if case=='negative_solar': example.loc[0,'solar_mw']=-1
    if case=='inverted_interval': example.loc[0,'solar_low_mw']=4
    if case=='missing_key': example=example.drop(columns='feeder_id')
    if case=='empty_id': example.loc[0,'feeder_id']=' '
    with pytest.raises(ValueError): reconstruct(example)


def test_energy_night_and_irregular(example):
    d=example.dropna().copy()
    d[['solar_mw','solar_low_mw','solar_high_mw']]=0
    r=reconstruct(d); c=consistency(r)
    assert c['night_max_difference_mw']==0
    assert abs(c['energy_balance_error_mwh'])<1e-12
    assert r.quality_flags.str.contains('irregular_intervals').all()
    with pytest.raises(ValueError): reconstruct(d,0)


def test_profile_night_and_bounds():
    t=pd.date_range('2026-01-01',periods=96,freq='15min',tz='Asia/Colombo')
    m,l,h=solar_profile(t,4)
    assert m[0]==m[24]==m[72]==0 and m[48]==3.2
    assert ((l<=m)&(m<=h)&(h<=4)).all()
    with pytest.raises(ValueError): solar_profile(t.tz_localize(None),4)


def test_synthetic_reproducible_and_scenarios():
    a=generate(days=20); b=generate(days=20)
    pd.testing.assert_frame_equal(a,b)
    assert a.net_mw.isna().any() and a.net_mw.lt(0).any() and a.net_mw.eq(0).any()
    assert a.scenario.eq('cloudy').any()
    assert not np.allclose(a.solar_mw,a.target_hidden_mw)
    assert not np.array_equal(a.target_hidden_mw,generate(seed=1,days=20).target_hidden_mw)


@pytest.fixture(scope='module')
def trained(tmp_path_factory):
    folder=tmp_path_factory.mktemp('C2_TLA_models')
    d=generate(days=20); b,meta,ev=train(d,folder)
    return folder,d,b,meta,ev


def test_chronological_splits_preprocessing_and_no_target_leakage(trained):
    folder,d,b,meta,ev=trained
    tr,va,te=splits(d)
    assert d.loc[tr,'timestamp'].max()<d.loc[va,'timestamp'].min()<d.loc[te,'timestamp'].min()
    assert set(d.loc[tr,'timestamp']).isdisjoint(d.loc[va,'timestamp'])
    expected=features(d).loc[tr].median().to_dict()
    assert meta['imputation_medians']==expected
    altered=d.copy(); altered['target_hidden_mw']=999; altered['target_true_mw']=-999
    pd.testing.assert_frame_equal(features(d),features(altered))
    assert list(features(d))==FEATURES
    assert ev['benchmarks'].keys()=={'apparent','direct_solar_addition','historical_profile','xgboost'}
    assert 0<=ev['hidden_interval_coverage']<=1
    assert all('SYNTHETIC' in ev['provenance'] for _ in [0])


def test_model_reload_schema_postprocessing_and_shap(trained):
    folder,d,b,meta,_=trained
    selected=d.iloc[:96]
    out=predict(selected,folder)
    assert out.hidden_mw.between(0,out.capacity_mw).all()
    assert (out.loc[out.timestamp.dt.hour<6,'hidden_mw']==0).all()
    reloaded,_=load(folder)
    import xgboost as xgb
    x=features(selected).fillna(meta['imputation_medians'])
    np.testing.assert_allclose(b.predict(xgb.DMatrix(x)),reloaded.predict(xgb.DMatrix(x)))
    values,info=explain(selected,folder)
    assert info['max_additivity_error_mw']<1e-4
    np.testing.assert_allclose(values.sum(axis=1)+info['base_mw'],info['raw_hidden_mw'],atol=1e-5)
    # Cross-check native Tree SHAP against the SHAP package.
    import shap
    check=shap.TreeExplainer(reloaded,feature_perturbation='tree_path_dependent')(x)
    np.testing.assert_allclose(check.values,values.to_numpy(),atol=1e-5)
    assert (folder/'C2_TLA_model.ubj').is_file()
    assert not list(folder.glob('*.pkl'))


def test_adapters_units_keys_and_billing(example):
    f=example[['feeder_id','timestamp']].assign(p10_kw=1000,p50_kw=2000,p90_kw=3000)
    d=c1_forecast(example,f,unit='kW',provenance='local contract mock, not live C1')
    assert d.solar_mw.eq(2).all()
    with pytest.raises(ValueError): c1_forecast(example,f.iloc[:-1],unit='kW',provenance='mock')
    with pytest.raises(ValueError): c1_forecast(example,pd.concat([f,f]),unit='kW',provenance='mock')
    with pytest.raises(ValueError): c1_forecast(example,f,unit='CSI',provenance='mock')
    np.testing.assert_allclose(csi_to_power([.5,1.2],[2,2],2),[1,2])
    meter=pd.DataFrame({'kwh_import':[100.],'kwh_export':[200.]})
    assert interval_meter_energy(meter,interval_minutes=15,meaning='grid_import_export').net_mw.iloc[0]==-.4
    with pytest.raises(ValueError): interval_meter_energy(meter,interval_minutes=15,meaning='gross')
    with pytest.raises(ValueError): monthly_energy(pd.DataFrame({'usage':[100]}))
    loads=pd.DataFrame({'SectionId':['S1','S1'],'Phase1Kw':[1,2],'Phase2Kw':[1,2],'Phase3Kw':[1,2]})
    joined=c3_static_load(pd.DataFrame({'SectionId':['S1','S2']}),loads)
    assert joined.model_load_kw.iloc[0]==9 and pd.isna(joined.model_load_kw.iloc[1])


def payload(example):
    d=example.copy(); d['units']='MW'; d['provenance']='local API contract mock'
    records=json.loads(d.to_json(orient='records',date_format='iso'))
    return {'records':records,'threshold_mw':3}


def test_api_contract_validation_and_auth(example,monkeypatch):
    client=TestClient(app); body=payload(example)
    r=client.post('/v1/reconstruct',json=body)
    assert r.status_code==200,r.text
    rows=r.json()['records']; assert rows[0]['units']=='MW' and rows[0]['vli']==2
    assert rows[2]['true_mw'] is None
    assert r.json()['schema_version']=='c2.tla.v1'
    body['records'].append(body['records'][0])
    assert client.post('/v1/reconstruct',json=body).status_code==422
    body=payload(example); body['records'][0]['timestamp']='2026-01-01T00:00:00'
    assert client.post('/v1/reconstruct',json=body).status_code==422
    body=payload(example); body['records'][0]['units']='kWh'
    assert client.post('/v1/reconstruct',json=body).status_code==422
    body=payload(example); body['records'][1]['timestamp']='2026-07-01T11:00:00+05:30'
    assert client.post('/v1/reconstruct',json=body).status_code==422
    monkeypatch.setenv('C2_TLA_API_TOKEN','test-token')
    assert client.post('/v1/reconstruct',json=payload(example)).status_code==401
    assert client.post('/v1/reconstruct',json=payload(example),headers={'Authorization':'Bearer test-token'}).status_code==200


def test_download_roundtrip_and_demo_reload(example):
    import io
    d=reconstruct(example)
    csv=pd.read_csv(io.StringIO(d.to_csv(index=False)))
    encoded=json.loads(d.to_json(orient='records',date_format='iso'))
    assert csv.net_mw.iloc[0]==-1 and encoded[2]['true_mw'] is None
    assert pd.Timestamp(encoded[0]['timestamp'])==d.timestamp.iloc[0]
    from C2_TLA_model import DEMO
    b,meta=load(DEMO)
    assert meta['features']==FEATURES
    assert 'synthetic' in meta['target_provenance']


CEB_PATH=os.environ.get('C2_TLA_CEB_PATH')


@pytest.mark.skipif(not CEB_PATH,reason='Set C2_TLA_CEB_PATH to run private real-input integration checks')
def test_real_ceb_loader_and_register_reconciliation():
    d=prepare_ceb(CEB_PATH); measured=load_measurements(CEB_PATH)
    assert len(measured)==88320 and len(d)==61824
    assert str(d.timestamp.dt.tz)=='Asia/Colombo'
    assert d.timestamp.min()==pd.Timestamp('2026-07-01',tz='Asia/Colombo')
    assert d.net_mw.lt(0).any() and not d.duplicated(['feeder_id','timestamp']).any()
    assert d.mapping_status.str.startswith('PROVISIONAL').all()
    caps,accounts=capacities(CEB_PATH)
    assert abs(caps.capacity_kw.sum()-accounts.capacity_kw.sum())<.05
    assert accounts.csc.ne('').all()
    key=['csc','gss','register_feeder','section','sin_number']
    grouped=[]
    for frame in [caps,accounts]:
        frame=frame.assign(sin_number=frame.sin.str.extract(r'(\d+)',expand=False).astype('Int64'))
        grouped.append(frame.groupby(key).capacity_kw.sum())
    pd.testing.assert_series_equal(grouped[0],grouped[1],check_exact=False,atol=.05,rtol=0)
    assert d.loc[d.feeder_id.eq('3_EMBIL_F2'),'capacity_mw'].iloc[0]==pytest.approx(2.66668)
    assert reconstruct(d[d.feeder_id.eq('3_EMBIL_F6')]).quality_flags.str.contains('near_zero_channel_review').all()
    report=consistency(reconstruct(d)); assert report['max_balance_error_mw']<1e-10
    assert abs(report['energy_balance_error_mwh'])<1e-8


def test_react_workbench_synthetic_analysis_explanations_and_exports():
    client=TestClient(app)
    c=client.post('/v1/dashboard/catalog',json={'source':'synthetic'})
    assert c.status_code==200
    assert c.json()['feeders']==['SYNTHETIC_F1','SYNTHETIC_F2','SYNTHETIC_F3']
    q={'source':'synthetic','feeder_id':'SYNTHETIC_F3','start':'2026-01-01','end':'2026-01-03'}
    r=client.post('/v1/dashboard/analyze',json=q)
    assert r.status_code==200,r.text
    d=r.json(); assert len(d['records'])==288
    assert d['summary']['reverse_intervals']>0
    assert 'solar_profile_assumption' not in d['quality_counts']
    assert 'SYNTHETIC' in d['evaluation']['provenance']
    q['method']='xgboost'
    assert client.post('/v1/dashboard/analyze',json=q).status_code==200
    e=client.post('/v1/dashboard/explain',json=q)
    assert e.status_code==200 and e.json()['info']['max_additivity_error_mw']<1e-4
    for fmt in ['csv','json']:
        export=client.post('/v1/dashboard/export?format='+fmt,json=q)
        assert export.status_code==200
        assert 'C2_TLA_selected_results.'+fmt in export.headers['content-disposition']
        if fmt=='json': assert len(export.json())==288


def test_react_workbench_validation_no_silent_fallback_and_auth(monkeypatch):
    client=TestClient(app)
    assert client.post('/v1/dashboard/catalog',json={'source':'ceb','ceb_path':'Z:/C2_TLA_missing'}).status_code==422
    q={'source':'synthetic','feeder_id':'wrong_feeder','start':'2026-01-01','end':'2026-01-02'}
    assert client.post('/v1/dashboard/analyze',json=q).status_code==422
    q['feeder_id']='SYNTHETIC_F1'; q['end']='2025-01-01'
    assert client.post('/v1/dashboard/analyze',json=q).status_code==422
    q.update(start='2026-01-01',end='2026-01-02',capacity_scale=1.5)
    assert client.post('/v1/dashboard/analyze',json=q).status_code==422
    monkeypatch.setenv('C2_TLA_API_TOKEN','workbench-test')
    assert client.get('/v1/dashboard/bootstrap').status_code==401
    assert client.get('/v1/dashboard/bootstrap',headers={'Authorization':'Bearer workbench-test'}).status_code==200


@pytest.mark.skipif(not CEB_PATH,reason='Set C2_TLA_CEB_PATH for real React workbench integration checks')
def test_react_workbench_ceb_mode():
    client=TestClient(app)
    q={'source':'ceb','ceb_path':CEB_PATH}
    c=client.post('/v1/dashboard/catalog',json=q)
    assert c.status_code==200 and c.json()['rows']==61824
    q.update(feeder_id='3_EMBIL_F2',start='2026-07-01',end='2026-07-03')
    baseline=client.post('/v1/dashboard/analyze',json=q)
    assert baseline.status_code==200
    q['capacity_scale']=1.5
    sensitivity=client.post('/v1/dashboard/analyze',json=q)
    assert sensitivity.status_code==200
    assert sensitivity.json()['summary']['hidden_peak_mw']==pytest.approx(1.5*baseline.json()['summary']['hidden_peak_mw'])
    q.update(feeder_id='3_EMBIL_F6',capacity_scale=1)
    d=client.post('/v1/dashboard/analyze',json=q).json()
    assert 'near_zero_channel_review' in d['quality_counts']


def test_react_static_entry_is_served():
    client=TestClient(app); r=client.get('/')
    # Fresh checkouts need build-ui; built workspaces serve React with cache revalidation.
    assert r.status_code in [200,503]
    if r.status_code==200:
        assert 'id="root"' in r.text and 'C2_TLA_assets/' in r.text
        assert r.headers['cache-control']=='no-cache'
