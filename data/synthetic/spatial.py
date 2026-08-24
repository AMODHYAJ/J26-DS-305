"""
Spatial stream stand-in — real GPS/capacity data for rooftop and
ground-mounted installations hasn't arrived from the external supervisor.

Stand-in strategy: scatter a dozen plausible points around Embilipitiya's
coordinates, split across the two synthetic feeders in grid_topology.py.
Replace `synthetic_plants()` with a real loader (from the GIS/PDF map the
supervisor will supply) once available — same SpatialRecord shape.
"""
from __future__ import annotations

import random
from typing import List

from schemas.contracts import PlantType, SpatialRecord

_CENTER_LAT = 6.3406
_CENTER_LON = 80.8492


def synthetic_plants(n: int = 12, seed: int = 42) -> List[SpatialRecord]:
    rng = random.Random(seed)
    feeders = ["FDR-EMB-A", "FDR-EMB-B"]
    plants = []
    for i in range(n):
        plant_type = PlantType.GROUND_MOUNTED if i % 4 == 0 else PlantType.ROOFTOP
        capacity = rng.uniform(200, 1000) if plant_type == PlantType.GROUND_MOUNTED else rng.uniform(3, 15)
        plants.append(
            SpatialRecord(
                plant_id=f"PLANT-{i:03d}",
                feeder_id=feeders[i % len(feeders)],
                latitude=_CENTER_LAT + rng.uniform(-0.05, 0.05),
                longitude=_CENTER_LON + rng.uniform(-0.05, 0.05),
                capacity_kw=round(capacity, 1),
                plant_type=plant_type,
            )
        )
    return plants
