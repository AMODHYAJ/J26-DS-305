"""Seeded simulation for development/evaluation, never measured ground truth."""
import numpy as np
import pandas as pd
from C2_TLA_core import TZ, solar_profile


def generate(seed=23177000, days=120, demand_scale_mw=4.0):
    rng=np.random.default_rng(seed)
    ts=pd.date_range('2026-01-01',periods=days*96,freq='15min',tz=TZ)
    hour=ts.hour.to_numpy()+ts.minute.to_numpy()/60
    frames=[]
    for i,penetration in enumerate([.4,1.,2.]):
        capacity=demand_scale_mw*penetration
        clear,_,_=solar_profile(ts,capacity,1.)
        day_weather=rng.uniform(.4,1.,days)
        cloud=np.clip(np.repeat(day_weather,96)+rng.normal(0,.10,len(ts)),.08,1.)
        # Multi-hour cloudy spells, present in every temporal partition.
        cloudy=(ts.dayofyear.to_numpy()%7==0)&(hour>9)&(hour<15)
        cloud[cloudy]*=.35
        generation=clear*.82*cloud
        forecast=np.clip(clear*.90*np.clip(cloud+rng.normal(0,.12,len(ts)),.05,1.),0,capacity)
        demand=demand_scale_mw*(.65+.45*np.exp(-((hour-7)/1.7)**2)+.75*np.exp(-((hour-19)/2.4)**2)+.15*np.exp(-((hour-12)/3)**2))
        industrial=(ts.dayofyear.to_numpy()%9==3)
        demand+=demand_scale_mw*.95*np.exp(-((hour-12)/1.8)**2)*industrial
        demand*=np.where(ts.dayofweek.to_numpy()>=5,.85,1.)
        demand=np.maximum(.1,demand+rng.normal(0,.05*demand_scale_mw,len(ts)))
        net=demand-generation
        missing=rng.random(len(ts))<.004
        observed=net.copy(); observed[missing]=np.nan
        zero=(rng.random(len(ts))<.002)&~missing; observed[zero]=0
        frames.append(pd.DataFrame(dict(feeder_id=f'SYNTHETIC_F{i+1}',timestamp=ts,net_mw=observed,solar_mw=forecast,
            solar_low_mw=np.maximum(0,forecast-.25*clear),solar_high_mw=np.minimum(capacity,forecast+.25*clear),
            capacity_mw=capacity,target_hidden_mw=generation,target_true_mw=demand,
            scenario=np.where(cloudy,'cloudy',np.where(industrial,'hidden_midday_peak',f'penetration_{penetration}')),
            provenance='synthetic simulation; latent solar target; not CEB accuracy')))
    return pd.concat(frames,ignore_index=True).sort_values(['feeder_id','timestamp']).reset_index(drop=True)
