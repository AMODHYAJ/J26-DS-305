"""
Component 2 — Demand Analyzer (owner: Hapuarachchi).

Reconciles CEB/LECO billing + net-metering data against forecast solar
output to compute "True Demand" vs "Net Load" per feeder.

True Demand = what the customer actually consumed (their own use, whether
served by the grid or by their own solar).
Net Load = what the grid sees at the feeder (import minus export) — this is
what CEB's meters actually measure today.

TODO(Hapuarachchi): replace the direct-sum decomposition below with the
explainable demand-decomposition model described in the TAF (feature
selection over consumption-history patterns, residential vs commercial
segmentation, etc.).
"""
from __future__ import annotations

from collections import defaultdict
from typing import List

from schemas.contracts import DemandDecomposition, MeterReading


def decompose(feeder_id: str, readings: List[MeterReading]) -> List[DemandDecomposition]:
    by_ts = defaultdict(lambda: {"import": 0.0, "export": 0.0})
    for r in readings:
        if r.feeder_id != feeder_id:
            continue
        by_ts[r.timestamp]["import"] += r.kwh_import
        by_ts[r.timestamp]["export"] += r.kwh_export

    out = []
    for ts, totals in sorted(by_ts.items()):
        net_load = totals["import"] - totals["export"]
        # Naive decomposition: assume all export is self-consumption offset
        true_demand = totals["import"] + totals["export"]
        out.append(
            DemandDecomposition(
                feeder_id=feeder_id,
                timestamp=ts,
                net_load_kw=round(net_load, 3),
                true_demand_kw=round(true_demand, 3),
                solar_self_consumption_kw=round(totals["export"], 3),
            )
        )
    return out
