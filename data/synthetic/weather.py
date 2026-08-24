"""
Weather stream — real data available today, no need to wait for CEB.

NASA POWER's free API gives historical irradiance/cloud-cover/temperature
for any lat/lon with no API key. This is used as the Weather Stream directly
(not really a "synthetic" proxy — it's the real thing), so this loader can
likely stay unchanged even after CEB data arrives.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

import requests

from schemas.contracts import WeatherRecord

# Approximate coordinates for Embilipitiya, Sabaragamuwa Province
EMBILIPITIYA_LAT = 6.3406
EMBILIPITIYA_LON = 80.8492

NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"


def fetch_nasa_power(start: str, end: str, lat: float = EMBILIPITIYA_LAT,
                      lon: float = EMBILIPITIYA_LON) -> List[WeatherRecord]:
    """
    Pull hourly GHI, cloud cover, and temperature for Embilipitiya.
    start/end format: YYYYMMDD
    """
    params = {
        "parameters": "ALLSKY_SFC_SW_DWN,CLOUD_AMT,T2M",
        "community": "RE",
        "longitude": lon,
        "latitude": lat,
        "start": start,
        "end": end,
        "format": "JSON",
    }
    resp = requests.get(NASA_POWER_URL, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()["properties"]["parameter"]

    records = []
    for ts_str, ghi in payload["ALLSKY_SFC_SW_DWN"].items():
        ts = datetime.strptime(ts_str, "%Y%m%d%H")
        records.append(
            WeatherRecord(
                timestamp=ts,
                cloud_cover_pct=payload["CLOUD_AMT"].get(ts_str, 0.0),
                ghi_wm2=max(ghi, 0.0),
                temperature_c=payload["T2M"].get(ts_str, 27.0),
            )
        )
    return records


def synthetic_clear_sky_day(date: datetime, n_points: int = 24) -> List[WeatherRecord]:
    """
    Offline fallback (no network): a simple bell-curve irradiance day plus
    a random cloud-cover event, for local dev without hitting NASA POWER.
    """
    import math
    import random

    records = []
    for h in range(n_points):
        ts = date.replace(hour=h, minute=0, second=0, microsecond=0)
        # Daylight roughly 6:00-18:00, bell-curve peak at solar noon
        daylight = max(0.0, math.sin(math.pi * (h - 6) / 12)) if 6 <= h <= 18 else 0.0
        cloud = random.uniform(0, 30) if random.random() > 0.1 else random.uniform(50, 90)
        ghi = 1000 * daylight * (1 - cloud / 150)
        records.append(
            WeatherRecord(
                timestamp=ts,
                cloud_cover_pct=cloud,
                ghi_wm2=max(ghi, 0.0),
                temperature_c=26 + 6 * daylight + random.uniform(-1, 1),
            )
        )
    return records
