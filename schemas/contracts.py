"""
Frozen data contracts for S-GISM.

Every component reads and writes ONLY these shapes. Real CEB data loaders
(added later under data/real/) must return objects that satisfy these same
models. Nothing downstream of Layer 1 should ever need to change when
synthetic data is replaced with real data.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Layer 1 — Data Ingestion contracts
# ---------------------------------------------------------------------------

class WeatherRecord(BaseModel):
    timestamp: datetime
    cloud_cover_pct: float = Field(ge=0, le=100)
    ghi_wm2: float = Field(ge=0, description="Global horizontal irradiance, W/m^2")
    temperature_c: float


class SubstationRating(BaseModel):
    substation_id: str
    feeder_id: str
    rated_kva: float
    nominal_kv: float  # e.g. 33 or 11


class GridReading(BaseModel):
    timestamp: datetime
    feeder_id: str
    amps: float
    volts: float


class PlantType(str, Enum):
    ROOFTOP = "rooftop"
    GROUND_MOUNTED = "ground_mounted"


class SpatialRecord(BaseModel):
    plant_id: str
    feeder_id: str
    latitude: float
    longitude: float
    capacity_kw: float
    plant_type: PlantType


class MeterReading(BaseModel):
    meter_id: str
    feeder_id: str
    timestamp: datetime
    kwh_import: float = Field(ge=0)
    kwh_export: float = Field(ge=0, description="Net-metering export, i.e. solar surplus")


# ---------------------------------------------------------------------------
# Layer 2 — Component output contracts
# ---------------------------------------------------------------------------

class SolarForecast(BaseModel):
    """Component 1 output — Jayathilaka."""
    feeder_id: str
    timestamp: datetime
    p10_kw: float
    p50_kw: float
    p90_kw: float
    ramp_rate_kw_per_min: float


class DemandDecomposition(BaseModel):
    """Component 2 output — Hapuarachchi."""
    feeder_id: str
    timestamp: datetime
    net_load_kw: float
    true_demand_kw: float
    solar_self_consumption_kw: float


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TransformerRisk(BaseModel):
    """Component 3 output — Edirisinghe."""
    substation_id: str
    feeder_id: str
    timestamp: datetime
    reverse_flow_kw: float
    risk_level: RiskLevel


class StorageTechnology(str, Enum):
    BESS = "battery"
    FLYWHEEL = "flywheel"
    COMPRESSED_AIR = "compressed_air"


class StorageRecommendation(BaseModel):
    """Component 4 output — Geethma."""
    substation_id: str
    recommended_tech: StorageTechnology
    lcos_usd_per_mwh: float
    efficiency_loss_pct: float
    rationale: str


# ---------------------------------------------------------------------------
# Layer 3 — Decision Engine output contract
# ---------------------------------------------------------------------------

class DispatchAdvice(BaseModel):
    substation_id: str
    feeder_id: str
    timestamp: datetime
    risk_level: RiskLevel
    ramp_rate_kw_per_min: float
    recommended_action: str
    recommended_tech: Optional[StorageTechnology] = None
