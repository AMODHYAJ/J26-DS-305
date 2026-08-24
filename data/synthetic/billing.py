"""
Commercial stream stand-in — real CEB/LECO billing + net-metering data
hasn't arrived from the external supervisor.

Stand-in strategy: generate plausible hourly import/export curves per meter
with a daytime solar-export bump and an evening import peak. Replace
`synthetic_meter_readings()` with a real billing-data loader later — same
MeterReading shape, so Component 2 (Demand Analyzer) doesn't change.
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import List

from schemas.contracts import MeterReading


def synthetic_meter_readings(feeder_id: str, meter_id: str, date: datetime,
                              n_points: int = 24, seed: int = 7) -> List[MeterReading]:
    rng = random.Random(seed)
    records = []
    for h in range(n_points):
        ts = date.replace(hour=h, minute=0, second=0, microsecond=0)
        # Import peaks morning + evening, export peaks midday (solar surplus)
        import_kwh = max(0.0, 2.0 + 1.5 * (abs(h - 7) < 2) + 2.5 * (abs(h - 19) < 2) + rng.uniform(-0.3, 0.3))
        export_kwh = max(0.0, 3.0 * max(0, 1 - abs(h - 12) / 5) + rng.uniform(-0.2, 0.2))
        records.append(
            MeterReading(
                meter_id=meter_id,
                feeder_id=feeder_id,
                timestamp=ts,
                kwh_import=round(import_kwh, 3),
                kwh_export=round(export_kwh, 3),
            )
        )
    return records
