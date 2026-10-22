"""
Configuration settings for Component 1: Solar Forecasting & Ramp Event Detection.
Centralized parameters for coordinates, horizons, thresholds, paths, and BESS simulation.
Dynamically loads CSC locations and capacities from csc_locations.csv.
"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
CONFIGS_DIR = BASE_DIR / "configs"
EXPERIMENTS_DIR = BASE_DIR / "experiments"


def load_csc_locations_config() -> Dict[str, Dict[str, Any]]:
    """Dynamically loads CSC locations from configs/csc_locations.csv."""
    csv_path = CONFIGS_DIR / "csc_locations.csv"
    if not csv_path.exists():
        csv_path = Path("csc_locations.csv")  # Fallback to root if needed

    if csv_path.exists():
        df = pd.read_csv(csv_path)
        locations = {}
        for _, row in df.iterrows():
            loc_id = row["location_id"]
            locations[loc_id] = {
                "name": loc_id.upper() if "name" not in row else str(row.get("name", loc_id)).title(),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "altitude_m": float(row.get("altitude_m", 100.0)),
                "rooftop_solar_kw": float(row.get("rooftop_solar_kw", 0.0)),
                "transformers": int(row.get("n_transformers", 0))
            }
        return locations
    else:
        # Fallback dictionary if CSV is missing
        return {
            "emb": {"name": "Embilipitiya", "lat": 6.30786, "lon": 80.85806, "altitude_m": 63.0, "rooftop_solar_kw": 12924.8, "transformers": 125},
            "god": {"name": "Godakawela",   "lat": 6.51197, "lon": 80.69227, "altitude_m": 241.0, "rooftop_solar_kw": 5976.4,  "transformers": 88},
            "kol": {"name": "Kolonna",      "lat": 6.36618, "lon": 80.70113, "altitude_m": 269.0, "rooftop_solar_kw": 2900.5,  "transformers": 52},
            "uda": {"name": "Udawalawa",    "lat": 6.39983, "lon": 80.85726, "altitude_m": 91.0, "rooftop_solar_kw": 6142.9,  "transformers": 92}
        }


# Geographic Anchors loaded dynamically from csc_locations.csv
CSC_LOCATIONS = load_csc_locations_config()

# Primary Anchor (Embilipitiya - 'emb')
LOCATION_NAME = "Embilipitiya"
LATITUDE = CSC_LOCATIONS.get("emb", {}).get("lat", 6.30786)
LONGITUDE = CSC_LOCATIONS.get("emb", {}).get("lon", 80.85806)
ALTITUDE = CSC_LOCATIONS.get("emb", {}).get("altitude_m", 63.0)

TIMEZONE_INTERNAL = "UTC"
TIMEZONE_DISPLAY = "Asia/Colombo"

# Forecasting Horizons (in minutes)
FORECAST_HORIZONS_MIN = [15, 30, 60, 120, 240]

# Solar Geometry & Masking Thresholds
MIN_SOLAR_ELEVATION_DEG = 10.0  # Daylight threshold (avoids numerical instability at horizon)
CURTAILMENT_MARGIN_MIN = 30     # Minutes buffer around curtailment events
RECONNECT_DELAY_SEC = 600       # 10 min grid reconnect hold
RECONNECT_RAMP_SEC = 900        # 15 min soft ramp-up limit

# Ramp Event Grid for Sensitivity Study
RAMP_DELTA_T_MIN: List[int] = [1, 5, 10, 15]
RAMP_THRESHOLDS_NORM: List[float] = [0.05, 0.10, 0.15, 0.20, 0.30]

# Primary Operational Ramp Setting
PRIMARY_RAMP_DELTA_T_MIN = 10
PRIMARY_RAMP_THRESHOLD = 0.15     # 15% rated capacity swing in 10 minutes
PRIMARY_ALERT_HORIZON_MIN = 30    # 30-minute lookahead window for ramp onset

# BESS Operational Parameters (Scaled from Anuradhapura & Galle systems)
BESS_CAPACITY_KWH = 500.0         # Feeder-scale battery energy capacity
BESS_POWER_KW = 250.0             # Continuous inverter power (0.5C)
BESS_MIN_SOC = 0.10               # 10% lower floor
BESS_MAX_SOC = 0.90               # 90% upper ceiling
BESS_INITIAL_SOC = 0.50           # 50% initial state
BESS_ROUNDTRIP_EFF = 0.88         # AC-AC roundtrip efficiency
BESS_ONEWAY_EFF = BESS_ROUNDTRIP_EFF ** 0.5

# Split Configuration
SPLIT_TRAIN_RATIO = 0.70
SPLIT_VAL_RATIO = 0.15
SPLIT_TEST_RATIO = 0.15
RANDOM_SEED = 42