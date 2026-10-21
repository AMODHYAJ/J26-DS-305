"""Read actual CEB layouts; never interpret AMP as MW or capacity as generation."""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import re
import subprocess
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from C2_TLA_core import TZ, solar_profile


def clean(v):
    return re.sub('[\u200b\u200c\u200d\ufeff]', '', str(v)).strip() if v is not None else ''


def data_root(path):
    p = Path(path).expanduser().resolve()
    if (p/'CEB_data').is_dir(): p = p/'CEB_data'
    if not p.is_dir():
        raise ValueError('CEB path must be an extracted directory. Extract CEB_data.zip outside the repository first.')
    return p


def capacities(root):
    records, accounts = [], []
    for p in sorted(data_root(root).glob('*.xlsx')):
        w = load_workbook(p, read_only=True, data_only=True)
        for s in w:
            mode, csc = None, ''
            for r in s.values:
                if clean(r[0]) == 'CSC :': csc=clean(r[5])
                if clean(r[0]) == 'No' and len(r) > 20:
                    mode='summary' if clean(r[13])=='SIN Cap.' else 'detail'
                elif clean(r[0]).isdigit() and mode:
                    if mode=='summary':
                        records.append(dict(source=p.name,csc=csc,gss=clean(r[2]),register_feeder=clean(r[4]),section=clean(r[8]),sin=clean(r[10]),scheme=clean(r[15]),capacity_kw=float(r[20])))
                    else:
                        accounts.append(dict(source=p.name,csc=csc,gss=clean(r[1]),register_feeder=clean(r[3]),section=clean(r[7]),sin=clean(r[9]),account=clean(r[12]),capacity_kw=float(r[14]),date=str(r[16]),scheme=clean(r[18])))
        w.close()
    if not records: raise ValueError('No embedded-generation capacity registers found in the selected CEB directory.')
    return pd.DataFrame(records), pd.DataFrame(accounts)


def load_measurements(root, *, gss='Embilipitiya'):
    files = list(data_root(root).glob('GSPL*.xlsx'))
    if len(files)!=1: raise ValueError('Expected exactly one GSPL measurement workbook; select a directory with one export.')
    w = load_workbook(files[0], read_only=True, data_only=True)
    records=[]
    for s in w:
        it=iter(s.values); header=next(it)
        if tuple(header[:6]) != ('GSS','Device Type','Device','Analog','Date','Day'): continue
        intervals=[(i,v) for i,v in enumerate(header) if isinstance(v,str) and re.fullmatch(r'\d{2}:\d{2}',v)]
        if len(intervals)!=96: raise ValueError(f'{s.title}: expected 96 quarter-hour columns.')
        for r in it:
            if r[0]!=gss or r[3]!='MW' or not re.fullmatch(r'3_EMBIL_F\d+',str(r[2])): continue
            base=pd.Timestamp(r[4])
            # Export contains local dates/day labels and no offset. Explicit CEB-local assumption.
            base=base.tz_localize(TZ) if base.tzinfo is None else base.tz_convert(TZ)
            for i,hm in intervals:
                h,m=map(int,hm.split(':'))
                records.append(dict(feeder_id=clean(r[2]),timestamp=base+pd.Timedelta(hours=h,minutes=m),net_mw=r[i],source_sheet=s.title))
    w.close()
    d=pd.DataFrame(records)
    if d.empty: raise ValueError('No Embilipitiya feeder MW channels found; AMP channels cannot establish active power.')
    if d.duplicated(['feeder_id','timestamp']).any(): raise ValueError('Duplicate feeder/timestamp in CEB source.')
    d['net_mw']=pd.to_numeric(d.net_mw,errors='raise')
    if np.isinf(d.net_mw).any(): raise ValueError('Infinite measured net demand.')
    return d.sort_values(['feeder_id','timestamp']).reset_index(drop=True)


def prepare_ceb(root, *, derating=.8, capacity_scale=1.):
    if not np.isfinite(capacity_scale) or capacity_scale<0: raise ValueError('Capacity scale must be finite/nonnegative.')
    d=load_measurements(root)
    cap,_=capacities(root)
    cap=cap[cap.gss.eq('Embilipitiya')].copy()
    # Explicit provisional crosswalk, visible in every row; operator confirmation is outstanding.
    mapping={f'Feeder {i:02d}':f'3_EMBIL_F{i}' for i in range(1,11)}
    cap['feeder_id']=cap.register_feeder.map(mapping)
    if cap.feeder_id.isna().any(): raise ValueError('Unmapped capacity-register feeder. Supply an approved crosswalk.')
    totals=cap.groupby('feeder_id').capacity_kw.sum()/1000
    d['capacity_mw']=d.feeder_id.map(totals)
    # Exclude channels lacking a register match, rather than silently assigning zero capacity.
    unmatched=sorted(d.loc[d.capacity_mw.isna(),'feeder_id'].unique())
    d=d[d.capacity_mw.notna()].copy()
    if d.empty: raise ValueError('No capacity/measurement matches; review the explicit crosswalk.')
    for feeder,g in d.groupby('feeder_id'):
        mid,lo,hi=solar_profile(g.timestamp,float(g.capacity_mw.iloc[0])*capacity_scale,derating)
        d.loc[g.index,'solar_mw']=mid; d.loc[g.index,'solar_low_mw']=lo; d.loc[g.index,'solar_high_mw']=hi
    d['capacity_mw']*=capacity_scale
    d['mapping_status']='PROVISIONAL: exact GSS plus feeder ordinal; not CEB-confirmed'
    d['network_feeder_id']=d.feeder_id.str.replace('3_EMBIL_', 'EMBILIPITIYA_',regex=False)
    d['provenance']='CEB measured net MW + estimated solar from real capacity register'
    d['solar_provenance']='model-derived daylight envelope; assumed 06:00–18:00, no weather observations'
    d.attrs['unmatched_measurement_feeders']=unmatched
    return d.reset_index(drop=True)


def column_audit(d):
    result={}
    for col in d:
        s=d[col]; n=pd.to_numeric(s,errors='coerce'); valid=n.dropna()
        result[str(col)]={'missing':int(s.isna().sum()),'distinct':int(s.nunique()),
            'numeric_count':int(n.notna().sum()),'zeros':int(n.eq(0).sum()),'negative':int(n.lt(0).sum()),
            'min':float(valid.min()) if len(valid) else None,'max':float(valid.max()) if len(valid) else None}
    return result


def audit(root, out, *, access=True):
    root=data_root(root); out=Path(out); out.mkdir(parents=True,exist_ok=True)
    result={'timezone_assumption':TZ,'files':[],'access':None}
    for p in sorted(root.rglob('*')):
        if not p.is_file(): continue
        entry={'file':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        if p.suffix=='.xlsx':
            w=load_workbook(p,read_only=True,data_only=True); sheets=[]
            for s in w:
                rows=list(s.values); header=rows[0]; body=rows[1:]
                # Report every column, including embedded-report columns whose first row is blank.
                names=[f'{i}:{clean(v) or "unnamed"}' for i,v in enumerate(header)]
                d=pd.DataFrame(body,columns=names)
                item={'sheet':s.title,'rows':len(body),'columns':names,'duplicate_rows':int(d.duplicated().sum()),'statistics':column_audit(d)}
                if any(clean(r[0])=='No' for r in rows):
                    item['embedded_report_header_rows']=[{'excel_row':i+1,'cells':[clean(v) for v in r]} for i,r in enumerate(rows) if clean(r[0])=='No']
                    item['classification']='installed-capacity register and agreement/account metadata; not measured consumption'
                elif p.name in ['Loads.xlsx','Gnodes.xlsx']:
                    item['classification']='static network model, not measured time series'
                if header[:6]==('GSS','Device Type','Device','Analog','Date','Day'):
                    item['units']=sorted(set(clean(r[3]) for r in body)); item['devices']=sorted(set(clean(r[2]) for r in body))
                    item['classification']='operational telemetry, subject to channel quality and sign/scaling confirmation'
                    dates=pd.to_datetime([r[4] for r in body]); item['date_range']=[str(dates.min()),str(dates.max())]
                    vals=pd.to_numeric(pd.Series([v for r in body for v in r[6:102]]),errors='coerce')
                    item['interval_statistics']={'count':len(vals),'missing':int(vals.isna().sum()),'zeros':int(vals.eq(0).sum()),'negative':int(vals.lt(0).sum()),'min':float(vals.min()),'max':float(vals.max())}
                sheets.append(item)
            w.close(); entry['sheets']=sheets
        elif p.suffix=='.csv':
            d=pd.read_csv(p); entry.update(rows=len(d),columns=list(d),statistics=column_audit(d),duplicate_rows=int(d.duplicated().sum()))
        elif p.suffix.lower() in ['.jpeg','.jpg','.png']:
            from PIL import Image
            with Image.open(p) as im: entry['image']={'size':im.size,'interpretation':'2026-10-19 curtailment status/capacity snapshot: hydro, solar, dendro, wind; not interval generation'}
        result['files'].append(entry)
    if access:
        mdb=next(root.glob('*.mdb'),None)
        if mdb:
            script=Path(__file__).with_name('C2_TLA_access_audit.ps1')
            target=out/'C2_TLA_access_audit.json'
            # Arguments passed as structured process argv; no execution-policy changes.
            command="& ([scriptblock]::Create((Get-Content -Raw -LiteralPath '"+str(script).replace("'","''")+"'))) -Database '"+str(mdb).replace("'","''")+"' -Output '"+str(target.resolve()).replace("'","''")+"'"
            digest=hashlib.sha256(mdb.read_bytes()).hexdigest()
            cached=json.loads(target.read_text(encoding='utf-8-sig')) if target.exists() else {}
            if cached.get('database_sha256')==digest and cached.get('tables'):
                result['access']=cached
            else:
                try:
                    completed=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,timeout=600)
                    if completed.returncode: result['access']={'error':completed.stderr,'action':'Install/use matching Office ACE OLEDB provider; no raw database edits needed.'}
                    else: result['access']=json.loads(target.read_text(encoding='utf-8-sig'))
                except subprocess.TimeoutExpired:
                    result['access']={'error':'Access audit timed out after 600 seconds. Run read-only audit in a permitted local terminal.','action':'The remaining Excel/CSV audit and estimator are complete; Access provider access is a separate environment dependency.'}
    d=load_measurements(root); cap,accounts=capacities(root)
    result['measurement_summary']={'rows':len(d),'feeders':sorted(d.feeder_id.unique()),'start':str(d.timestamp.min()),'end':str(d.timestamp.max()),'statistics':column_audit(d[['net_mw']])}
    result['capacity_summary']=cap.groupby(['gss','register_feeder']).capacity_kw.sum().reset_index().to_dict('records')
    result['register_checks']={'summary_kw':float(cap.capacity_kw.sum()),'detail_kw':float(accounts.capacity_kw.sum()),'detail_rows':len(accounts)}
    (out/'C2_TLA_data_audit.json').write_text(json.dumps(result,indent=2,default=str,allow_nan=False),encoding='utf-8')
    return result
