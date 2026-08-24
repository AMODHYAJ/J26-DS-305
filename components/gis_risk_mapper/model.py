"""
Component 3 — GIS Risk Mapper (owner: Edirisinghe).

Maps Reverse Power Flow risk per transformer/substation: whenever local
solar production at a substation exceeds local demand, flag the risk level.

TODO(Edirisinghe): replace the threshold logic below with real AC power-flow
analysis via OpenDSS (dss-python) against the IEEE 13-bus stand-in feeder
(see data/synthetic/grid_topology.py), then swap in the real Embilipitiya
feeder model once CEB delivers it.
"""
from __future__ import annotations

from datetime import datetime
from typing import List

from schemas.contracts import (
    DemandDecomposition,
    RiskLevel,
    SolarForecast,
    SubstationRating,
    TransformerRisk,
)


def _risk_level(reverse_flow_kw: float, rated_kva: float) -> RiskLevel:
    ratio = reverse_flow_kw / rated_kva if rated_kva else 0.0
    if ratio > 0.5:
        return RiskLevel.HIGH
    if ratio > 0.15:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def assess_risk(substation: SubstationRating, solar: List[SolarForecast],
                 demand: List[DemandDecomposition]) -> List[TransformerRisk]:
    demand_by_ts = {d.timestamp: d for d in demand if d.feeder_id == substation.feeder_id}
    out = []
    for s in solar:
        if s.feeder_id != substation.feeder_id:
            continue
        d = demand_by_ts.get(s.timestamp)
        local_demand = d.true_demand_kw if d else 0.0
        reverse_flow = max(0.0, s.p50_kw - local_demand)
        out.append(
            TransformerRisk(
                substation_id=substation.substation_id,
                feeder_id=substation.feeder_id,
                timestamp=s.timestamp,
                reverse_flow_kw=round(reverse_flow, 2),
                risk_level=_risk_level(reverse_flow, substation.rated_kva),
            )
        )
    return out
