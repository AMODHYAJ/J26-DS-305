"""
C3 synthetic operating-scenario generator (V2)

Real CEB inputs (per transformer): sin, csc, feeder, kva, solar_kw (+ coordinates if present).
SYNTHETIC: daily weather, hourly PV generation, hourly demand, export events.

All demand/weather assumptions are illustrative, NOT CEB-calibrated or measured.
Demand profile types (residential / commercial / mixed) are hypothetical and are
assigned at random; they do not represent the real customer mix of any transformer.
Simplified active-power balance only: no power factor, voltage, losses or AC power flow.

Outputs (components/gis_risk_mapper/output/):
  synthetic_hourly{tag}.csv           hourly scenarios (transformer x day x hour)
  synthetic_transformer_days{tag}.csv ML dataset, one row per transformer-day
  synthetic_exposure_summary{tag}.csv per-transformer score, rank, tier (for UI / C4)

Prediction task encoded in the transformer-day file:
  Using information available up to 10:00, predict whether simulated reverse export
  occurs during 11:00-14:00 on the same day (same-day nowcast).

Usage:
  python components/gis_risk_mapper/synthetic_data.py
  python components/gis_risk_mapper/synthetic_data.py --load-scale 0.7 --tag _lowload   # sensitivity run
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- paths
C3_DIR = Path(__file__).resolve().parent
OUT_DIR = C3_DIR / "output"
INPUT_FILE = OUT_DIR / "solar_with_coords.csv"

# ---------------------------------------------------------------- settings
NUM_DAYS = 49                           # 7 weeks
HOURS = np.arange(6, 19)                # 06:00-18:00 hourly readings (13)
SIM_START = pd.Timestamp("2026-01-05")  # a Monday; synthetic calendar, not real dates
HISTORY_DAYS = 3                        # days of history needed before first ML row
MORNING_HOURS = [6, 7, 8, 9, 10]        # information available to the model
TARGET_HOURS = [11, 12, 13, 14]         # window being predicted

# Weather (synthetic, area-wide clearness index with day-to-day persistence)
CLEARNESS_MEAN, CLEARNESS_PHI, CLEARNESS_SIGMA = 0.70, 0.70, 0.10
CSC_DEV_SIGMA = 0.05                    # small regional difference per CSC per day
HOURLY_CLOUD_PHI, HOURLY_CLOUD_SIGMA = 0.60, 0.06
SITE_NOISE_SIGMA = 0.02                 # per-transformer shading/inverter variation
PV_PEAK_FRACTION = 0.90                 # max output as fraction of installed kW

# Demand (synthetic, hypothetical profile types)
PROFILE_TYPES = ["residential", "mixed", "commercial"]
PROFILE_PROBS = [0.50, 0.30, 0.20]
_RES = np.array([0.75, 0.90, 0.85, 0.70, 0.60, 0.55, 0.55, 0.55, 0.55, 0.60, 0.70, 0.85, 1.00])
_COM = np.array([0.35, 0.45, 0.65, 0.85, 0.95, 1.00, 1.00, 0.95, 1.00, 0.95, 0.85, 0.65, 0.50])
SHAPES = np.stack([_RES, (_RES + _COM) / 2, _COM])   # order matches PROFILE_TYPES
WEEKEND_FACTOR = np.array([1.15, 0.90, 0.55])        # order matches PROFILE_TYPES
PEAK_LOAD_FRACTION_RANGE = (0.15, 0.65)              # daytime peak demand as fraction of kVA
LEVEL_PHI, LEVEL_SIGMA = 0.60, 0.05                  # day-to-day demand level continuity
HOURLY_DEMAND_NOISE = 0.05


def ar1(rng, shape, phi, sigma):
    """Zero-mean AR(1) series along the last axis."""
    out = np.empty(shape)
    out[..., 0] = rng.normal(0, sigma / np.sqrt(1 - phi ** 2), size=shape[:-1])
    for i in range(1, shape[-1]):
        out[..., i] = phi * out[..., i - 1] + rng.normal(0, sigma, size=shape[:-1])
    return out


def load_transformers():
    df = pd.read_csv(INPUT_FILE)
    required = ["sin", "csc", "feeder", "kva", "solar_kw"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    if df[required].isna().any().any():
        raise ValueError("Missing required transformer values.")
    if (df["kva"] <= 0).any() or (df["solar_kw"] < 0).any():
        raise ValueError("Invalid transformer ratings or solar capacity.")
    if df["sin"].duplicated().any():
        raise ValueError("Duplicate SIN values.")
    return df.reset_index(drop=True)


def simulate(df, rng, load_scale):
    T, D, H = len(df), NUM_DAYS, len(HOURS)
    kva = df["kva"].to_numpy(float)
    solar = df["solar_kw"].to_numpy(float)

    dates = SIM_START + pd.to_timedelta(np.arange(D), unit="D")
    dow = dates.dayofweek.to_numpy()
    is_weekend = dow >= 5

    # --- weather: area-wide clearness with persistence + CSC deviation + hourly cloud noise
    k_day = CLEARNESS_MEAN + ar1(rng, (D,), CLEARNESS_PHI, CLEARNESS_SIGMA)
    csc_codes, csc_idx = np.unique(df["csc"].to_numpy(), return_inverse=True)
    C = len(csc_codes)
    csc_dev = rng.normal(0, CSC_DEV_SIGMA, size=(C, D))
    hourly = ar1(rng, (C, D, H), HOURLY_CLOUD_PHI, HOURLY_CLOUD_SIGMA)
    cloud_csc = np.clip(k_day[None, :, None] + csc_dev[:, :, None] + hourly, 0.05, 1.0)
    cloud = cloud_csc[csc_idx] * (1 + rng.normal(0, SITE_NOISE_SIGMA, size=(T, D, H)))

    # --- PV generation (kW)
    clear_sky = np.sin(np.pi * (HOURS - 5.5) / 13.0)
    pv = solar[:, None, None] * PV_PEAK_FRACTION * clear_sky[None, None, :] * cloud
    pv = np.clip(pv, 0, None)

    # --- demand (kW)
    ptype = rng.choice(len(PROFILE_TYPES), size=T, p=PROFILE_PROBS)
    peak_frac = rng.uniform(*PEAK_LOAD_FRACTION_RANGE, size=T) * load_scale
    level = 1 + ar1(rng, (T, D), LEVEL_PHI, LEVEL_SIGMA)
    wk = np.where(is_weekend[None, :], WEEKEND_FACTOR[ptype][:, None], 1.0)
    demand = (kva * peak_frac)[:, None, None] * SHAPES[ptype][:, None, :] \
             * (wk * level)[:, :, None] * (1 + rng.normal(0, HOURLY_DEMAND_NOISE, size=(T, D, H)))
    demand = np.clip(demand, 0, None)

    return dict(dates=dates, dow=dow, is_weekend=is_weekend, pv=pv, demand=demand,
                ptype=np.array(PROFILE_TYPES)[ptype], T=T, D=D, H=H)


def build_hourly(df, sim):
    T, D, H = sim["T"], sim["D"], sim["H"]
    pv, demand = sim["pv"], sim["demand"]
    export = np.clip(pv - demand, 0, None)
    out = pd.DataFrame({
        "sin": np.repeat(df["sin"].to_numpy(), D * H),
        "csc": np.repeat(df["csc"].to_numpy(), D * H),
        "feeder": np.repeat(df["feeder"].to_numpy(), D * H),
        "kva": np.repeat(df["kva"].to_numpy(), D * H),
        "solar_kw": np.repeat(df["solar_kw"].to_numpy(), D * H),
        "demand_profile": np.repeat(sim["ptype"], D * H),   # hidden; do NOT use as ML feature
        "day_index": np.tile(np.repeat(np.arange(D), H), T),
        "date": np.tile(np.repeat(sim["dates"].strftime("%Y-%m-%d"), H), T),
        "day_of_week": np.tile(np.repeat(sim["dow"], H), T),
        "hour": np.tile(HOURS, T * D),
        "pv_kw": pv.ravel(),
        "demand_kw": demand.ravel(),
        "net_load_kw": (demand - pv).ravel(),
        "export_kw": export.ravel(),
        "simulated_export_event": (pv > demand).ravel().astype(int),
        "data_basis": "SYNTHETIC",
    })
    return out.round(3), export


def build_transformer_days(df, sim, export):
    pv, demand = sim["pv"], sim["demand"]
    kva = df["kva"].to_numpy(float)
    net = demand - pv
    event = pv > demand
    midx = [h - HOURS[0] for h in MORNING_HOURS]
    tidx = [h - HOURS[0] for h in TARGET_HOURS]

    target_event = event[:, :, tidx].any(axis=2)                     # (T, D)
    target_peak = export[:, :, tidx].max(axis=2) / kva[:, None]      # (T, D)
    morning = net[:, :, midx] / kva[:, None, None]                   # (T, D, 5)

    frames = []
    for d in range(HISTORY_DAYS, sim["D"]):
        f = pd.DataFrame({
            "sin": df["sin"], "csc": df["csc"], "feeder": df["feeder"],
            "kva": df["kva"], "solar_kw": df["solar_kw"],
            "solar_to_kva": df["solar_kw"] / df["kva"],
            "day_index": d,
            "date": sim["dates"][d].strftime("%Y-%m-%d"),
            "day_of_week": sim["dow"][d],
            "is_weekend": int(sim["is_weekend"][d]),
        })
        for j, h in enumerate(MORNING_HOURS):
            f[f"morning_net_h{h:02d}"] = morning[:, d, j]
        f["morning_net_mean"] = morning[:, d, :].mean(axis=1)
        f["morning_net_trend"] = morning[:, d, -1] - morning[:, d, 2]   # 10:00 minus 08:00
        f["prev_day_export_event"] = target_event[:, d - 1].astype(int)
        f["prev_day_peak_export_ratio"] = target_peak[:, d - 1]
        f["prev3day_export_rate"] = target_event[:, d - HISTORY_DAYS:d].mean(axis=1)
        f["target_export_11_14"] = target_event[:, d].astype(int)
        f["target_peak_export_ratio_11_14"] = target_peak[:, d]   # target-side; never use as a feature
        f["data_basis"] = "SYNTHETIC"
        frames.append(f)
    return pd.concat(frames, ignore_index=True).round(4)


def build_summary(df, sim, export):
    kva = df["kva"].to_numpy(float)
    ratio = export / kva[:, None, None]
    event = (sim["pv"] > sim["demand"])
    s = df[["sin", "csc", "feeder", "kva", "solar_kw"]].copy()
    for c in ["latitude", "longitude", "lat", "lon", "lng"]:
        if c in df.columns:
            s[c] = df[c]
    s["solar_to_kva"] = s["solar_kw"] / s["kva"]
    s["export_frequency"] = event.mean(axis=(1, 2))
    s["peak_export_ratio"] = ratio.max(axis=(1, 2))
    s["exposure_score"] = ratio.mean(axis=(1, 2))    # mean hourly export / kVA: severity and frequency together
    s["priority_rank"] = s["exposure_score"].rank(ascending=False, method="min").astype(int)
    s["tier"] = np.select(
        [s["peak_export_ratio"] >= 1.0, s["export_frequency"] > 0],
        ["High", "Medium"], default="Low")           # High = simulated export exceeds transformer rating
    s["data_basis"] = "SYNTHETIC"
    return s.sort_values("priority_rank").round(4)


def report(hourly, days, summary):
    print(f"Hourly rows            : {len(hourly):,}")
    print(f"Transformer-day rows   : {len(days):,}")
    print(f"Transformers           : {summary['sin'].nunique()}")
    print(f"Hourly export rate     : {hourly['simulated_export_event'].mean():.1%}")
    t = days["target_export_11_14"].mean()
    print(f"Target (11-14) positive: {t:.1%}")
    if not 0.10 <= t <= 0.90:
        print("WARNING: target is heavily imbalanced; review assumptions (do not just tune to 50/50).")
    print("Tier counts            :", summary["tier"].value_counts().to_dict())
    print("Profile mix            :", hourly.drop_duplicates("sin")["demand_profile"].value_counts().to_dict())
    nan = int(hourly.isna().sum().sum() + days.isna().sum().sum())
    print(f"Missing values         : {nan}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--load-scale", type=float, default=1.0, help="scale demand for sensitivity runs")
    ap.add_argument("--tag", default="", help="suffix for output files, e.g. _lowload")
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    df = load_transformers()
    sim = simulate(df, rng, a.load_scale)
    hourly, export = build_hourly(df, sim)
    days = build_transformer_days(df, sim, export)
    summary = build_summary(df, sim, export)

    OUT_DIR.mkdir(exist_ok=True)
    hourly.to_csv(OUT_DIR / f"synthetic_hourly{a.tag}.csv", index=False)
    days.to_csv(OUT_DIR / f"synthetic_transformer_days{a.tag}.csv", index=False)
    summary.to_csv(OUT_DIR / f"synthetic_exposure_summary{a.tag}.csv", index=False)
    report(hourly, days, summary)


if __name__ == "__main__":
    main()