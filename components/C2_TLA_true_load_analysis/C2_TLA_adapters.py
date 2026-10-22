"""Explicit integration adapters. No teammate service is required by the local demo."""
import numpy as np
import pandas as pd
from C2_TLA_core import KEY, TZ


def c1_forecast(net, forecast, *, unit, provenance):
    """Adapt the historical SolarForecast p10_kw/p50_kw/p90_kw contract.

    Actual C1 main predicts clear_sky_index, so this adapter needs an upstream
    power forecast supplied explicitly; it does not pretend that service exists.
    """
    if unit!='kW': raise ValueError('C1 adapter requires explicit kW units for p10_kw/p50_kw/p90_kw.')
    if not provenance.strip(): raise ValueError('Solar-forecast provenance is required.')
    f=forecast.copy(); n=net.copy()
    for d in [f,n]:
        if not set(KEY)<=set(d): raise ValueError('Feeder and timestamp keys are required.')
        if any(pd.Timestamp(t).tzinfo is None for t in d.timestamp): raise ValueError('C1 timestamps need offsets.')
        d['timestamp']=pd.to_datetime(d.timestamp,utc=True).dt.tz_convert(TZ)
        if d.duplicated(KEY).any(): raise ValueError('Duplicate integration keys.')
    for old,new in [('p10_kw','solar_low_mw'),('p50_kw','solar_mw'),('p90_kw','solar_high_mw')]:
        if old not in f: raise ValueError(f'Missing C1 field {old}; CSI is not feeder power.')
        f[new]=pd.to_numeric(f[old],errors='raise')/1000
        if not np.isfinite(f[new]).all(): raise ValueError('Non-finite C1 power.')
    n=n.drop(columns=['solar_mw','solar_low_mw','solar_high_mw'],errors='ignore')
    result=n.merge(f[KEY+['solar_mw','solar_low_mw','solar_high_mw']],on=KEY,how='left',validate='one_to_one',indicator=True)
    if result._merge.ne('both').any(): raise ValueError('Missing exact C1 feeder/timestamp matches; interpolation is not implicit.')
    result['solar_provenance']=provenance
    return result.drop(columns='_merge')


def csi_to_power(csi, clear_sky_ac_mw, capacity_mw):
    """Explicit optional conversion requiring a justified feeder clear-sky AC model."""
    c=np.asarray(csi,float); ref=np.asarray(clear_sky_ac_mw,float)
    if not np.isfinite(c).all() or not np.isfinite(ref).all() or (c<0).any() or (ref<0).any() or not np.isfinite(capacity_mw) or capacity_mw<0:
        raise ValueError('CSI conversion needs finite nonnegative CSI, reference AC MW, and capacity.')
    return np.minimum(c*ref,capacity_mw)


def interval_meter_energy(d, *, interval_minutes, meaning):
    """Import minus export ENERGY to interval mean POWER, not gross consumption."""
    if meaning!='grid_import_export': raise ValueError('Meter scheme must explicitly identify grid import/export.')
    if not np.isfinite(interval_minutes) or interval_minutes<=0: raise ValueError('Positive interval duration required.')
    out=d.copy()
    for col in ['kwh_import','kwh_export']:
        if not np.isfinite(out[col]).all() or (out[col]<0).any(): raise ValueError('Import/export kWh must be finite/nonnegative.')
    out['net_mw']=(out.kwh_import-out.kwh_export)/(interval_minutes/60)/1000
    out['provenance']='measured interval grid energy converted to mean net MW; not gross consumption'
    return out


def monthly_energy(d):
    """Preserve billing energy and semantics separately; never create interval labels."""
    required={'customer_id','billing_period_start','billing_period_end','energy_kwh','metering_scheme','energy_meaning','available_at'}
    if not required<=set(d): raise ValueError(f'Billing input requires {sorted(required)}')
    if not np.isfinite(d.energy_kwh).all(): raise ValueError('Non-finite billing kWh.')
    if not d.energy_meaning.isin(['grid_import','grid_export','net_billed','gross_consumption','unknown']).all():
        raise ValueError('Unknown billing-energy semantics.')
    return d.copy()  # intentionally excluded from inference until availability and meter semantics are established


def c3_static_load(solar, loads):
    """Exact section join only. A SIN-only join is ambiguous across CSC/sections."""
    if 'SectionId' not in solar or 'SectionId' not in loads: raise ValueError('Explicit verified SectionId required on both sides.')
    p=['Phase1Kw','Phase2Kw','Phase3Kw']
    if not np.isfinite(loads[p]).all().all(): raise ValueError('Static phase load contains non-finite values.')
    grouped=loads.assign(model_load_kw=loads[p].sum(axis=1)).groupby('SectionId',as_index=False).model_load_kw.sum()
    out=solar.merge(grouped,on='SectionId',how='left',validate='many_to_one')
    out['load_provenance']='static network allocation; not measured time series'
    return out
