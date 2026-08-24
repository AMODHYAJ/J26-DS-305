"""
Component 1 — Solar Forecaster (owner: Jayathilaka).

Predicts short-term generation (kW) and Ramp Rate (volatility) per feeder.
Target model per the TAF: LightGBM/TFT quantile regression (P10/P50/P90).

This file currently ships a simple clear-sky-index heuristic so the rest of
the pipeline (Decision Engine, dashboard) has something real to consume.
Replace `forecast()`'s internals with the trained LightGBM/TFT model without
changing its signature — downstream code only depends on SolarForecast.
"""
from __future__ import annotations

from datetime import datetime
from typing import List

from schemas.contracts import SolarForecast, SpatialRecord, WeatherRecord


def _feeder_capacity_kw(feeder_id: str, plants: List[SpatialRecord]) -> float:
    return sum(p.capacity_kw for p in plants if p.feeder_id == feeder_id)


def forecast(feeder_id: str, weather: List[WeatherRecord],
             plants: List[SpatialRecord]) -> List[SolarForecast]:
    """
    TODO(Jayathilaka): replace this heuristic with the trained LightGBM/TFT
    quantile model. Feature engineering (clear-sky index Kt, solar geometry,
    lagged ramp rate, etc.) belongs in features.py.
    """
    capacity_kw = _feeder_capacity_kw(feeder_id, plants)
    forecasts = []
    prev_p50 = 0.0
    for w in sorted(weather, key=lambda r: r.timestamp):
        clear_sky_index = max(0.0, 1 - w.cloud_cover_pct / 100)
        p50 = capacity_kw * clear_sky_index * (w.ghi_wm2 / 1000)
        p50 = max(0.0, min(p50, capacity_kw))
        spread = 0.15 * p50  # placeholder uncertainty band
        ramp_rate = (p50 - prev_p50) / 60.0  # kW/min, assuming hourly steps
        forecasts.append(
            SolarForecast(
                feeder_id=feeder_id,
                timestamp=w.timestamp,
                p10_kw=max(0.0, p50 - spread),
                p50_kw=p50,
                p90_kw=min(capacity_kw, p50 + spread),
                ramp_rate_kw_per_min=ramp_rate,
            )
        )
        prev_p50 = p50
    return forecasts
