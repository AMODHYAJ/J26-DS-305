
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RampEventInput(BaseModel):
    """Ramp event forecast received from Component 1."""

    event_id: str = Field(
        ...,
        description="Unique identifier for the forecast event",
    )

    forecast_timestamp: datetime = Field(
        ...,
        description="Time when the forecast was generated",
    )

    predicted_event_time: datetime = Field(
        ...,
        description="Expected time of the ramp event",
    )

    event_direction: Literal[
        "RAMP_UP",
        "RAMP_DOWN",
        "NO_EVENT",
    ] = Field(
        ...,
        description="Predicted direction of the solar ramp",
    )

    forecast_horizon_minutes: int = Field(
        ...,
        ge=0,
        description="Forecast lead time in minutes",
    )

    predicted_change_mw: float | None = Field(
        default=None,
        description="Expected change in solar generation in MW",
    )

    geographic_scope: str = Field(
        ...,
        description="Area covered by the forecast",
    )

    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Forecast confidence between 0 and 1, if available",
    )


class GridRiskInput(BaseModel):
    """Grid risk assessment received from Component 3."""

    asset_id: str = Field(
        ...,
        description="Identifier of the affected network asset",
    )

    asset_type: Literal[
        "TRANSFORMER",
        "FEEDER",
    ] = Field(
        ...,
        description="Type of network asset being assessed",
    )

    risk_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="Risk score on a proposed 0-100 scale",
    )

    risk_category: Literal[
        "LOW",
        "MEDIUM",
        "HIGH",
    ] = Field(
        ...,
        description="Risk category assigned by Component 3",
    )


class SolarPlantInput(BaseModel):
    """Solar plant information for curtailment assessment."""

    plant_id: str = Field(
        ...,
        description="Unique identifier for the solar plant",
    )

    plant_name: str | None = Field(
        default=None,
        description="Readable name of the solar plant",
    )

    feeder_id: str | None = Field(
        default=None,
        description="Identifier of the connected feeder",
    )

    transformer_id: str | None = Field(
        default=None,
        description="Identifier of the connected transformer",
    )

    installed_capacity_mw: float = Field(
        ...,
        gt=0,
        description="Installed solar capacity in MW",
    )

    available_generation_mw: float | None = Field(
        default=None,
        ge=0,
        description="Current available generation in MW, if known",
    )

    curtailment_eligible: bool = Field(
        ...,
        description="Whether the plant is eligible for curtailment",
    )

    control_status: str | None = Field(
        default=None,
        description="Known control or operational status",
    )

