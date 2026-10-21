"""Local Streamlit research workbench. Run through C2_TLA_launch.cmd ui."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import json
import os
import pandas as pd
import altair as alt
import streamlit as st
from C2_TLA_core import reconstruct, consistency
from C2_TLA_ingest import prepare_ceb
from C2_TLA_model import predict, explain, load, MODELS, DEMO, ROOT
from C2_TLA_synthetic import generate

st.set_page_config(page_title='C2 • True Load Analysis',page_icon='⚡',layout='wide')
st.markdown('''<style>
[data-testid="stMetric"] {
    background:var(--secondary-background-color);
    border:1px solid rgba(128,128,128,.35);
    border-radius:12px;
    padding:16px;
}
</style>''',unsafe_allow_html=True)


@st.cache_data(show_spinner='Reading actual CEB quarter-hour channels…')
def ceb(path,derating,scale): return prepare_ceb(path,derating=derating,capacity_scale=scale)


@st.cache_data
def synthetic(): return generate(days=120)


def chart(d,columns,colors):
    long=d[['timestamp']+columns].melt('timestamp',var_name='Signal',value_name='MW')
    return alt.Chart(long).mark_line().encode(x=alt.X('timestamp:T',title='Time (display timezone may follow browser; exports UTC / +05:30)'),y=alt.Y('MW:Q',title='Active power (MW)'),
        color=alt.Color('Signal:N',scale=alt.Scale(domain=columns,range=colors)),tooltip=['timestamp:T','Signal:N',alt.Tooltip('MW:Q',format='.3f')]).interactive()


st.caption('SOLARVERA  /  COMPONENT 02  /  RESEARCH WORKBENCH')
st.title('See the demand behind solar')
st.write('Compare the power observed at the feeder with estimated hidden and true demand. Every result keeps its evidence and assumptions visible.')
default_path=os.environ.get('C2_TLA_CEB_PATH',str(Path.home()/'Downloads'/'CEB_data'))
prepared=ROOT/'C2_TLA_outputs'/'C2_TLA_ceb_reconstruction.csv'
with st.sidebar:
    st.subheader('Analysis controls')
    mode=st.radio('Data source',['CEB-based estimates','Synthetic demonstration'],index=0 if prepared.exists() or os.environ.get('C2_TLA_CEB_PATH') else 1)
    path=st.text_input('Extracted CEB data directory',default_path)
    if st.button('Reload local inputs'): st.cache_data.clear()
    derating=st.slider('Solar profile derating',.35,1.,.8,.05,help='Assumed AC yield; this is not measured generation.')
    scale=st.slider('Capacity sensitivity multiplier',0.,2.,1.,.1,help='1 uses the register as supplied. Other values are counterfactual scenarios.')
    method=st.selectbox('Reconstruction method',['Direct solar addition','XGBoost experiment'])
    threshold=st.number_input('Demand threshold (MW)',min_value=.1,value=10.,step=.5)

try:
    if mode=='CEB-based estimates':
        # A prepared local result is an explicit CEB input cache, never a synthetic fallback.
        if not Path(path).is_dir() and prepared.exists() and path==default_path:
            data=pd.read_csv(prepared)
            data['timestamp']=pd.to_datetime(data.timestamp,utc=True).dt.tz_convert('Asia/Colombo')
            if derating!=.8 or scale!=1.: raise ValueError('Sensitivity controls require the extracted source directory. Enter its path.')
            st.info('Using the prepared CEB input cache. Enter the extracted source directory to refresh data or vary solar assumptions.')
        else: data=ceb(path,derating,scale)
        st.warning('CEB measured net demand + assumed solar profile from real capacity. Feeder mapping is provisional; capacity effective dates and other generation/storage are unverified. These are research estimates, not measured true demand.')
        st.caption('Excluded without capacity matches: 3_EMBIL_F3, F9, F10. F6–F8 contain suspicious near-zero MW channels.')
    else:
        data=synthetic().copy()
        st.info('SYNTHETIC DEMONSTRATION • Simulated consumption, solar, forecast error, clouds, missing readings and penetration scenarios. Accuracy shown here is simulation accuracy.')
    feeders=sorted(data.feeder_id.unique())
    with st.sidebar:
        feeder=st.selectbox('Feeder',feeders,index=feeders.index('3_EMBIL_F2') if '3_EMBIL_F2' in feeders else 0,key='C2_TLA_feeder_'+mode)
        dates=data.timestamp.dt.date
        start=dates.min(); end=dates.max()
        selection=st.date_input('Date range (Asia/Colombo)',(start,min(end,start+pd.Timedelta(days=2))),min_value=start,max_value=end,key='C2_TLA_dates_'+mode)
    if not isinstance(selection,(tuple,list)) or len(selection)!=2:
        st.info('Select both a start and end date.'); st.stop()
    chosen=data[data.feeder_id.eq(feeder)&data.timestamp.dt.date.between(*selection)].copy()
    if chosen.empty: st.info('No records for that selection. Choose dates within the source range.'); st.stop()
    chosen=chosen.sort_values(['feeder_id','timestamp']).reset_index(drop=True)
    if method=='XGBoost experiment':
        load()
        st.warning('XGBoost is trained on synthetic latent solar targets. Applying it to CEB inputs is an unvalidated transfer experiment. Its intervals have no established CEB coverage.')
        result=predict(chosen,threshold_mw=threshold)
    else: result=reconstruct(chosen,threshold)
    a,b,c,d=st.columns(4)
    a.metric('Estimated true peak',f'{result.true_mw.max():.2f} MW')
    b.metric('Estimated hidden peak',f'{result.hidden_mw.max():.2f} MW')
    c.metric('Reverse-flow intervals',str(int(result.reverse_flow.sum())))
    d.metric('Hidden threshold crossings',str(int(result.hidden_threshold_crossing.sum())))
    demand,solar,visibility,explanations,evaluation,quality=st.tabs(['Demand curves','Solar & uncertainty','Visibility','XGBoost & SHAP','Research evidence','Data quality & exports'])
    with demand:
        st.subheader('Observed demand and reconstructed demand')
        st.altair_chart(chart(result,['apparent_mw','true_mw','hidden_mw','residual_mw'],['#2764b0','#009e73','#e69f00','#b15ba5']),width='stretch')
        st.caption('Feeder-boundary true demand includes downstream losses. Hidden demand here is total local PV contribution, not separately measured customer self-consumption. With direct addition, residual = true − solar = observed net demand by construction.')
    with solar:
        st.subheader('Solar estimate and demand uncertainty')
        st.altair_chart(chart(result,['solar_low_mw','solar_mw','solar_high_mw'],['#b4bfcd','#e69f00','#785a08']),width='stretch')
        st.altair_chart(chart(result,['true_low_mw','true_mw','true_high_mw'],['#a6d8cc','#009e73','#487e74']),width='stretch')
        st.caption('Direct-addition limits are an assumption envelope (35–100% of capacity × daylight profile), not calibrated probabilities. XGBoost uses a synthetic calibration error interval. Neither includes net-meter error, mapping uncertainty or unobserved non-solar generation.')
    with visibility:
        st.subheader('Visibility Loss Index')
        st.line_chart(result.set_index('timestamp')[['vli']])
        st.caption('VLI = hidden / true. Undefined when true ≤ 0.000001 MW; values above 1 are retained under reverse flow. The index is not a probability.')
        st.dataframe(result[['timestamp','vli','reverse_flow','peak','threshold_status','hidden_threshold_crossing']],hide_index=True,width='stretch')
    with explanations:
        try:
            model,meta=load()
            st.success('Demo model loaded • synthetic training provenance')
            sample=chosen.iloc[:min(384,len(chosen))].copy()
            values,info=explain(sample)
            position=st.slider('Interval to explain',0,len(sample)-1,0)
            st.write(str(sample.timestamp.iloc[position]))
            local=values.iloc[position].rename('Contribution (MW)').to_frame()
            st.bar_chart(local)
            st.write({'base_hidden_mw':info['base_mw'][position],'raw_hidden_mw':info['raw_hidden_mw'][position],
                'physical_correction_mw':info['physical_correction_mw'][position],'max_additivity_error_mw':info['max_additivity_error_mw']})
            st.caption('Base + SHAP contributions = raw hidden prediction. Physical correction is separate; adding measured net then yields true demand. SHAP describes this simulator-trained model, not causal evidence about CEB consumers.')
            st.subheader('Global contribution summary for the first selected intervals')
            st.bar_chart(values.abs().mean().rename('Mean absolute contribution (MW)'))
            with st.expander('Feature schema and training provenance'): st.json(meta)
        except (ValueError,OSError) as e: st.warning(str(e))
    with evaluation:
        st.subheader('Selected reconstruction consistency')
        st.json(consistency(result))
        report=MODELS/'C2_TLA_evaluation.json'
        if not report.exists(): report=DEMO/'C2_TLA_evaluation.json'
        if report.exists():
            ev=json.loads(report.read_text(encoding='utf-8'))
            st.subheader('Synthetic chronological benchmark experiment')
            st.caption(ev['provenance'])
            st.dataframe(pd.DataFrame({k:v['overall'] for k,v in ev['benchmarks'].items()}).T,width='stretch')
            with st.expander('Calibration, scenario results and split dates'): st.json(ev)
        st.write('Independent CEB accuracy and expert-validation scores are unavailable. Use C2_TLA_expert_review.csv to record future review.')
    with quality:
        warnings=result[result.quality_flags.ne('')]
        st.write(f'{len(warnings):,} / {len(result):,} intervals carry review flags.')
        if result.net_mw.abs().max()<.01: st.error('Near-zero channel: confirm telemetry scaling and channel availability before interpreting this feeder.')
        st.dataframe(result,hide_index=True,width='stretch')
        x,y=st.columns(2)
        x.download_button('Download selected CSV',result.to_csv(index=False).encode('utf-8'),'C2_TLA_selected_results.csv','text/csv')
        y.download_button('Download selected JSON',result.to_json(orient='records',date_format='iso'),'C2_TLA_selected_results.json','application/json')
        st.caption('Timestamps in JSON use UTC Z; CSV retains timezone offsets. Both represent the same Asia/Colombo intervals. Exports retain method, units, provenance and flags.')
except (ValueError,OSError,KeyError) as e:
    st.error(str(e))
    st.info('Enter the extracted CEB directory, run the preparation pipeline, or explicitly select Synthetic demonstration. Data sources never switch silently.')
