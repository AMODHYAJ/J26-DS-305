"""
Layer 3 — Decision Engine (all members).

Reconciles Components 1-4's outputs into Dispatch Advice, per the TAF's
example logic: if the forecaster predicts a sharp high-ramp-rate drop, the
demand analyzer shows True Demand at peak, and the risk mapper flags a
high-risk transformer, query the storage matchmaker for the cheapest
adequate response and alert the dashboard.
"""
from __future__ import annotations

from typing import List

from components.storage_matchmaker.model import recommend
from schemas.contracts import (
    DispatchAdvice,
    RiskLevel,
    SolarForecast,
    SubstationRating,
    TransformerRisk,
)

RAMP_RATE_ALERT_THRESHOLD = 20.0  # kW/min, placeholder — tune once real data is in


def reconcile(substation: SubstationRating, solar: List[SolarForecast],
              risks: List[TransformerRisk]) -> List[DispatchAdvice]:
    solar_by_ts = {s.timestamp: s for s in solar if s.feeder_id == substation.feeder_id}
    ramp_values = [abs(s.ramp_rate_kw_per_min) for s in solar]
    avg_ramp = sum(ramp_values) / len(ramp_values) if ramp_values else 0.0

    advice = []
    for r in risks:
        if r.substation_id != substation.substation_id:
            continue
        s = solar_by_ts.get(r.timestamp)
        ramp = s.ramp_rate_kw_per_min if s else 0.0

        if r.risk_level == RiskLevel.HIGH and abs(ramp) > RAMP_RATE_ALERT_THRESHOLD:
            storage_rec = recommend(substation.substation_id, avg_ramp)
            action = (
                f"High reverse-flow risk with fast ramp ({ramp:.1f} kW/min) — "
                f"discharge/charge {storage_rec.recommended_tech.value} at "
                f"{substation.substation_id}."
            )
            tech = storage_rec.recommended_tech
        elif r.risk_level == RiskLevel.HIGH:
            action = f"High reverse-flow risk at {substation.substation_id} — monitor closely."
            tech = None
        elif r.risk_level == RiskLevel.MEDIUM:
            action = f"Elevated reverse-flow risk at {substation.substation_id} — watch trend."
            tech = None
        else:
            action = "Normal operation."
            tech = None

        advice.append(
            DispatchAdvice(
                substation_id=r.substation_id,
                feeder_id=r.feeder_id,
                timestamp=r.timestamp,
                risk_level=r.risk_level,
                ramp_rate_kw_per_min=ramp,
                recommended_action=action,
                recommended_tech=tech,
            )
        )
    return advice
