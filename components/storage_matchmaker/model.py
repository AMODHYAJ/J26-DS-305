"""
Component 4 — Storage Matchmaker (owner: Geethma).

Recommends the optimal storage technology per substation using LCOS
(Levelized Cost of Storage) and the feeder's ramp-rate/terrain profile.
Per the TAF, this consumes Components 1 & 3's outputs only at the dashboard
layer, never inside its own model — LCOS/technology parameters come from
public literature and datasheets, not CEB data, so this can be built out
almost fully today.

TODO(Geethma): replace the flat LCOS table with the PuLP/SciPy optimisation
described in the TAF (energy density, degradation under high-ramp-rate
conditions, space/heat-loss constraints).
"""
from __future__ import annotations

from schemas.contracts import StorageRecommendation, StorageTechnology

# Placeholder LCOS figures (USD/MWh) — replace with sourced literature values.
_LCOS_TABLE = {
    StorageTechnology.BESS: 280.0,
    StorageTechnology.FLYWHEEL: 410.0,
    StorageTechnology.COMPRESSED_AIR: 180.0,
}

_EFFICIENCY_LOSS = {
    StorageTechnology.BESS: 10.0,
    StorageTechnology.FLYWHEEL: 15.0,
    StorageTechnology.COMPRESSED_AIR: 30.0,
}


def recommend(substation_id: str, avg_ramp_rate_kw_per_min: float) -> StorageRecommendation:
    """
    Very rough placeholder rule: high ramp rate favours flywheels (spike
    tolerance), moderate favours batteries, low/steady favours compressed
    air (cheapest for long-duration, non-spiky conditions).
    """
    if avg_ramp_rate_kw_per_min > 50:
        tech = StorageTechnology.FLYWHEEL
        rationale = "High ramp-rate volatility favours flywheels' unlimited spike tolerance."
    elif avg_ramp_rate_kw_per_min > 15:
        tech = StorageTechnology.BESS
        rationale = "Moderate ramp rate is within typical BESS degradation tolerance."
    else:
        tech = StorageTechnology.COMPRESSED_AIR
        rationale = "Low, steady ramp rate suits compressed air's cheaper long-duration storage."

    return StorageRecommendation(
        substation_id=substation_id,
        recommended_tech=tech,
        lcos_usd_per_mwh=_LCOS_TABLE[tech],
        efficiency_loss_pct=_EFFICIENCY_LOSS[tech],
        rationale=rationale,
    )
