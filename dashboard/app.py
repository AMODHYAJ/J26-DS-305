"""
Layer 4 — NSO Dashboard (all members).

Wires the entire synthetic pipeline end-to-end so the team has something
demoable before real CEB data arrives:

  weather + spatial -> Component 1 (forecast)
  billing -> Component 2 (demand decomposition)
  grid ratings + Component 1 + Component 2 -> Component 3 (risk)
  Component 1 + Component 3 -> Decision Engine -> dispatch advice
  Component 4 is queried by the Decision Engine internally.

Run with: streamlit run dashboard/app.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Allow running via `streamlit run dashboard/app.py` from repo root
sys.path.append(str(Path(__file__).resolve().parent.parent))

from components.demand_analyzer.model import decompose
from components.gis_risk_mapper.model import assess_risk
from components.solar_forecaster.model import forecast
from data.synthetic.billing import synthetic_meter_readings
from data.synthetic.grid_topology import load_test_feeder_ratings
from data.synthetic.spatial import synthetic_plants
from data.synthetic.weather import synthetic_clear_sky_day
from decision_engine.engine import reconcile

st.set_page_config(page_title="S-GISM NSO Dashboard (Prototype)", layout="wide")
st.title("S-GISM — NSO Dashboard (prototype, synthetic data)")
st.caption(
    "Running entirely on synthetic/proxy data — real CEB feeder, spatial, "
    "and billing data has not been received yet. See README.md."
)

today = datetime(2026, 8, 24)

# --- Layer 1: synthetic data -------------------------------------------------
weather = synthetic_clear_sky_day(today)
plants = synthetic_plants()
ratings = load_test_feeder_ratings()

feeder_ids = sorted({r.feeder_id for r in ratings})
selected_feeder = st.selectbox("Feeder", feeder_ids)

meter_readings = synthetic_meter_readings(selected_feeder, "METER-SYNTH-01", today)

# --- Layer 2: component engines ---------------------------------------------
solar_forecasts = forecast(selected_feeder, weather, plants)
demand = decompose(selected_feeder, meter_readings)

feeder_substations = [r for r in ratings if r.feeder_id == selected_feeder]

all_risks = []
all_advice = []
for sub in feeder_substations:
    risks = assess_risk(sub, solar_forecasts, demand)
    all_risks.extend(risks)
    all_advice.extend(reconcile(sub, solar_forecasts, risks))

# --- View B: Duck Curve Forecaster ("When") ---------------------------------
st.subheader("View B — Duck Curve Forecaster")
duck_df = pd.DataFrame(
    {
        "timestamp": [f.timestamp for f in solar_forecasts],
        "solar_p50_kw": [f.p50_kw for f in solar_forecasts],
        "ramp_rate_kw_per_min": [f.ramp_rate_kw_per_min for f in solar_forecasts],
    }
).merge(
    pd.DataFrame({"timestamp": [d.timestamp for d in demand], "true_demand_kw": [d.true_demand_kw for d in demand]}),
    on="timestamp",
    how="left",
)
st.line_chart(duck_df.set_index("timestamp")[["solar_p50_kw", "true_demand_kw"]])

# --- View A: GIS Heatmap ("Where") ------------------------------------------
st.subheader("View A — Reverse-Flow Risk by Substation")
risk_df = pd.DataFrame(
    [{"substation_id": r.substation_id, "timestamp": r.timestamp,
      "reverse_flow_kw": r.reverse_flow_kw, "risk_level": r.risk_level.value} for r in all_risks]
)
if not risk_df.empty:
    st.dataframe(risk_df, use_container_width=True)
    plant_df = pd.DataFrame([p.model_dump() for p in plants if p.feeder_id == selected_feeder])
    if not plant_df.empty:
        st.map(plant_df.rename(columns={"latitude": "lat", "longitude": "lon"}))

# --- View C: Storage Recommendation Panel ("How") ---------------------------
st.subheader("View C — Dispatch Advice / Storage Recommendation")
advice_df = pd.DataFrame(
    [{"substation_id": a.substation_id, "timestamp": a.timestamp, "risk_level": a.risk_level.value,
      "recommended_action": a.recommended_action} for a in all_advice]
)
st.dataframe(advice_df, use_container_width=True)
