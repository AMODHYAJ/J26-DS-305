"""
Grid stream stand-in — real feeder A/V + substation ratings haven't arrived
from the external supervisor yet.

Stand-in strategy: use the IEEE 13-bus test feeder (a standard, freely
available distribution test network) as a plausible 33/11kV-scale topology.
It lets Component 3 (GIS Risk Mapper) exercise real AC power-flow logic via
OpenDSS today. When CEB delivers the real Embilipitiya feeder model, replace
`load_test_feeder_ratings()` with a loader over their data — Component 3's
code should not need to change, only which `SubstationRating` list it's fed.
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import List

from schemas.contracts import GridReading, SubstationRating

# A handful of substations modelled loosely on the IEEE 13-bus feeder,
# relabelled to sit inside the Embilipitiya study area.
_SUBSTATION_IDS = [
    ("SS-EMB-01", "FDR-EMB-A", 500.0, 11.0),
    ("SS-EMB-02", "FDR-EMB-A", 300.0, 11.0),
    ("SS-EMB-03", "FDR-EMB-B", 750.0, 33.0),
    ("SS-EMB-04", "FDR-EMB-B", 400.0, 11.0),
]


def load_test_feeder_ratings() -> List[SubstationRating]:
    """Stand-in for CEB-supplied substation ratings."""
    return [
        SubstationRating(substation_id=sid, feeder_id=fid, rated_kva=kva, nominal_kv=kv)
        for sid, fid, kva, kv in _SUBSTATION_IDS
    ]


def synthetic_grid_readings(feeder_id: str, date: datetime, n_points: int = 24) -> List[GridReading]:
    """
    Synthetic hourly A/V readings for a feeder, loosely tracking a daytime
    demand curve, until real feeder telemetry is available.
    """
    records = []
    for h in range(n_points):
        ts = date.replace(hour=h, minute=0, second=0, microsecond=0)
        base_load = 60 + 40 * max(0, 1 - abs(h - 19) / 8)  # evening peak
        amps = base_load + random.uniform(-5, 5)
        volts = 400 + random.uniform(-8, 8)
        records.append(GridReading(timestamp=ts, feeder_id=feeder_id, amps=amps, volts=volts))
    return records


def run_opendss_snapshot(ratings: List[SubstationRating]):
    """
    Placeholder for the real OpenDSS (via dss-python) power-flow call that
    Component 3 will run against the IEEE 13-bus .dss test file. Left as a
    stub here so the module imports cleanly without requiring OpenDSS to be
    installed for teammates who aren't working on Component 3 yet.
    """
    raise NotImplementedError(
        "Wire this up to dss-python + the IEEE 13-bus .dss file inside "
        "components/gis_risk_mapper/. Kept as a stub here to avoid making "
        "dss-python a hard dependency for the whole repo."
    )
