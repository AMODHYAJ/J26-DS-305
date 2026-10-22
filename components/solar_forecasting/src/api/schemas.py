"""
API Schemas for Component 1 (Solar Forecasting & Ramp Detection).
Standardized Pydantic contracts for interaction with:
  - Component 2 (Demand Analyzer)
  - Component 3 (GIS Risk Mapper)
  - Component 4 (Storage Matchmaker)
All internal timestamps in UTC; all external display strings formatted in Asia/Colombo (UTC+05:30).
"""
from __future__ import annotations

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class PlantForecastRequest(BaseModel):
    plant_id: str = Field(default="EMB_SOLAR_01", description="Identifier of the solar power plant")
    horizon_minutes: int = Field(default=30, ge=15, le=240, description="Forecast lookahead in minutes (15, 30, 60, 120, 240)")
    current_power_kw: Optional[float] = Field(default=None, description="Recent measured plant power in kW")
    clear_sky_index: Optional[float] = Field(default=None, description="Optional measured clear-sky index k_t")


class PlantForecastResponse(BaseModel):
    plant_id: str
    timestamp_utc: str
    timestamp_colombo: str
    horizon_minutes: int
    predicted_clear_sky_index: float
    predicted_power_kw: float
    theoretical_clearsky_power_kw: float
    plant_capacity_kw: float
    model_version: str


class FeederForecastRequest(BaseModel):
    area_code: str = Field(default="EMB-EMB", description="GSS area code: EMB-EMB, EMB-GOD, EMB-KOL, EMB-UDA")
    feeder_name: str = Field(default="Feeder 05", description="Specific feeder name or 'ALL'")
    horizon_minutes: int = Field(default=30, ge=15, le=240)


class FeederForecastResponse(BaseModel):
    area_code: str
    feeder_name: str
    timestamp_utc: str
    timestamp_colombo: str
    horizon_minutes: int
    connected_transformers_count: int
    total_rooftop_capacity_kw: float
    forecast_rooftop_generation_kw: float
    regional_clear_sky_index: float


class RampDetectionRequest(BaseModel):
    plant_id: str = Field(default="EMB_SOLAR_01")
    horizon_minutes: int = Field(default=30, description="Alert horizon (15 or 30 minutes)")
    threshold_r: float = Field(default=0.15, description="Normalized ramp magnitude threshold (0.05 to 0.30)")


class RampDetectionResponse(BaseModel):
    plant_id: str
    timestamp_utc: str
    timestamp_colombo: str
    horizon_minutes: int
    threshold_r: float
    ramp_down_probability: float
    ramp_up_probability: float
    ramp_down_alert: bool
    ramp_up_alert: bool
    decision_threshold: float
    alert_severity: str  # NORMAL, ADVISORY, WARNING, CRITICAL
    expected_lead_time_minutes: float


class BESSHeadroomRequest(BaseModel):
    feeder_id: str = Field(default="EMB-EMB_FEEDER_05")
    current_soc: Optional[float] = Field(default=0.50, ge=0.0, le=1.0)
    battery_capacity_kwh: Optional[float] = Field(default=500.0)
    battery_power_kw: Optional[float] = Field(default=250.0)


class BESSHeadroomResponse(BaseModel):
    feeder_id: str
    current_soc: float
    discharge_headroom_kwh: float
    discharge_power_kw: float
    discharge_headroom_score: float  # Normalized [0, 1] for Component 4 ranking
    charge_headroom_kwh: float
    charge_power_kw: float
    charge_headroom_score: float     # Normalized [0, 1] for Component 4 ranking
    recommended_reserve_action: str
    simulation_flag: bool = True
