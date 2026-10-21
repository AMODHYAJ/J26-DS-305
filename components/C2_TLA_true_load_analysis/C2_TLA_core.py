"""Feeder-boundary active-power reconstruction. All power values are MW."""
from __future__ import annotations
import numpy as np
import pandas as pd

TZ = 'Asia/Colombo'
KEY = ['feeder_id', 'timestamp']


def validate(frame: pd.DataFrame, *, allow_missing_net=True) -> pd.DataFrame:
    d = frame.copy()
    required = KEY + ['net_mw', 'solar_mw', 'solar_low_mw', 'solar_high_mw']
    missing = set(required) - set(d)
    if missing:
        raise ValueError(f'Missing columns: {sorted(missing)}')
    if d.empty:
        raise ValueError('No rows selected. Select a feeder and a nonempty date range.')
    if d.feeder_id.isna().any() or d.feeder_id.astype(str).str.strip().eq('').any():
        raise ValueError('Every row needs an explicit feeder identifier.')
    times = [pd.Timestamp(t) for t in d.timestamp]
    if any(pd.isna(t) or t.tzinfo is None for t in times):
        raise ValueError('Timestamps must include a timezone offset.')
    d['timestamp'] = pd.to_datetime(d.timestamp, utc=True).dt.tz_convert(TZ)
    if d.duplicated(KEY).any():
        raise ValueError('Duplicate feeder/timestamp records: reconcile the source before inference.')
    for col in required[2:]:
        d[col] = pd.to_numeric(d[col], errors='raise')
        values = d[col].to_numpy(dtype=float)
        if np.isinf(values).any() or (np.isnan(values).any() and not (col == 'net_mw' and allow_missing_net)):
            raise ValueError(f'{col} contains non-finite values.')
    if (d[['solar_mw', 'solar_low_mw', 'solar_high_mw']] < 0).any().any():
        raise ValueError('Solar generation must be nonnegative; net demand may be negative.')
    if ((d.solar_low_mw > d.solar_mw) | (d.solar_mw > d.solar_high_mw)).any():
        raise ValueError('Solar interval must satisfy low <= estimate <= high.')
    return d.sort_values(KEY).reset_index(drop=True)


def reconstruct(frame: pd.DataFrame, threshold_mw=10.0, *, hidden=None, method='direct_solar_addition'):
    if not np.isfinite(threshold_mw) or threshold_mw <= 0:
        raise ValueError('Demand threshold must be finite and greater than zero MW.')
    d = validate(frame)
    # hidden must already be aligned to the validated, sorted input.
    h = d.solar_mw.to_numpy() if hidden is None else np.asarray(hidden, dtype=float)
    if h.shape != (len(d),) or not np.isfinite(h).all() or (h < 0).any():
        raise ValueError('Hidden-demand predictions must be finite, nonnegative, and aligned.')
    d['apparent_mw'] = d.net_mw
    d['hidden_mw'] = h
    d['true_mw'] = d.net_mw + h
    if np.isinf(d.true_mw).any(): raise ValueError('Power balance overflow; check the input units and magnitudes.')
    d['residual_mw'] = d.true_mw - d.solar_mw
    d['true_low_mw'] = d.net_mw + d.solar_low_mw
    d['true_high_mw'] = d.net_mw + d.solar_high_mw
    d['vli'] = d.hidden_mw / d.true_mw.where(d.true_mw > 1e-6)
    d['reverse_flow'] = d.net_mw < 0
    d['threshold_mw'] = threshold_mw
    d['threshold_exceeded'] = d.true_mw > threshold_mw
    d['threshold_status'] = np.where(d.true_mw.isna(),'unknown_missing_measurement',np.where(d.threshold_exceeded,'exceeded','below'))
    d['hidden_threshold_crossing'] = d.threshold_exceeded & (d.net_mw <= threshold_mw)
    d['peak'] = d.true_mw.eq(d.groupby('feeder_id').true_mw.transform('max')) & d.true_mw.notna()
    d['units'] = 'MW'
    d['method'] = method
    if 'provenance' not in d:
        d['provenance'] = 'caller_supplied_inputs'
    d['quality_flags'] = ''
    for mask,flag in [
        (d.net_mw.isna(),'missing_net_measurement'),
        (d.net_mw.eq(0),'zero_net_review'),
        (d.reverse_flow,'observed_reverse_flow'),
        (d.true_mw.le(1e-6),'nonpositive_true_vli_undefined'),
        (d.true_mw.lt(0),'solar_or_boundary_inconsistent'),
        (d.provenance.str.contains('CEB',na=False),'solar_profile_assumption;other_generation_storage_unobserved')]:
        d.loc[mask,'quality_flags'] += ';'+flag
    d['quality_flags']=d.quality_flags.str.lstrip(';')
    for _, g in d.groupby('feeder_id'):
        if g.net_mw.abs().max() < .01:
            d.loc[g.index, 'quality_flags'] += ';near_zero_channel_review'
        delta = g.timestamp.diff().dt.total_seconds()
        if len(g) > 2 and delta.dropna().nunique() > 1:
            d.loc[g.index, 'quality_flags'] += ';irregular_intervals'
    return d


def consistency(d):
    """Consistency is algebraic, never an accuracy claim. Energy uses left-held intervals."""
    e = dict(net_mwh=0., solar_mwh=0., true_mwh=0.)
    gaps = 0
    for _, g in d.groupby('feeder_id'):
        dt = g.timestamp.diff().shift(-1).dt.total_seconds() / 3600
        # Do not integrate through gaps or missing measurements; omit final interval.
        nominal = dt[dt > 0].median()
        mask = dt.gt(0) & dt.le(1.5 * nominal) & g.net_mw.notna()
        gaps += int((~mask).sum())
        for name, col in [('net','net_mw'), ('solar','solar_mw'), ('true','true_mw')]:
            e[name+'_mwh'] += float((g.loc[mask,col] * dt[mask]).sum())
    e['energy_balance_error_mwh'] = e['true_mwh'] - e['net_mwh'] - e['solar_mwh']
    e['excluded_or_final_intervals'] = gaps
    e['max_balance_error_mw'] = float((d.true_mw-d.net_mw-d.hidden_mw).abs().max())
    night = d.solar_mw.eq(0) & d.net_mw.notna()
    e['night_max_difference_mw'] = float((d.loc[night,'true_mw']-d.loc[night,'net_mw']).abs().max()) if night.any() else None
    e['reference'] = 'internal consistency only; no independent true-demand labels'
    return e


def solar_profile(timestamps, capacity_mw, derating=0.8):
    """Local-time daylight envelope, not a validated generation forecast."""
    if not np.isfinite(capacity_mw) or capacity_mw < 0 or not 0 <= derating <= 1:
        raise ValueError('Capacity must be finite/nonnegative and derating within [0,1].')
    ts = pd.DatetimeIndex(timestamps)
    if ts.tz is None: raise ValueError('Solar profile requires timezone-aware timestamps.')
    ts = ts.tz_convert(TZ)
    hour = ts.hour + ts.minute / 60
    envelope = np.maximum(0., np.sin(np.pi * (hour-6)/12))
    envelope = np.where((hour > 6) & (hour < 18), envelope, 0.)
    mid = capacity_mw * derating * envelope
    return mid, capacity_mw * .35 * envelope, capacity_mw * envelope
