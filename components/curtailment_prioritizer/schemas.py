
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


class CurtailmentRequest(BaseModel):
    """Operator requirements for a curtailment assessment."""

    event_id: str = Field(
        ...,
        description="Identifier of the ramp event being assessed",
    )

    target_reduction_mw: float = Field(
        ...,
        gt=0,
        description="Required reduction in solar generation in MW",
    )

    operator_authorized: bool = Field(
        default=False,
        description="Whether the operator has authorized curtailment",
    )


class PlantCurtailmentRecommendation(BaseModel):
    """Explainable curtailment recommendation for one solar plant."""

    plant_id: str = Field(
        ...,
        description="Identifier of the recommended solar plant",
    )

    plant_name: str | None = Field(
        default=None,
        description="Readable name of the solar plant",
    )

    priority_rank: int = Field(
        ...,
        ge=1,
        description="Priority ranking, with 1 being the highest priority",
    )

    available_generation_mw: float = Field(
        ...,
        ge=0,
        description="Available generation assumed for the assessment, in MW",
    )

    recommended_reduction_mw: float = Field(
        ...,
        ge=0,
        description="Proposed reduction in solar generation, in MW",
    )

    reason: str = Field(
        ...,
        description="Explanation for the plant's priority",
    )


class CurtailmentAssessmentOutput(BaseModel):
    """Overall result of a curtailment assessment."""

    event_id: str = Field(
        ...,
        description="Identifier of the ramp event being assessed",
    )

    assessment_status: Literal[
        "ASSESSMENT_COMPLETE",
        "TARGET_MET",
        "TARGET_NOT_MET",
        "RAMP_DOWN_WARNING",
        "NO_ACTION_REQUIRED",
        "INSUFFICIENT_DATA",
    ] = Field(
        ...,
        description="Outcome or status of the assessment",
    )

    target_reduction_mw: float = Field(
        ...,
        ge=0,
        description="Requested reduction in solar generation, in MW",
    )

    proposed_total_reduction_mw: float = Field(
        ...,
        ge=0,
        description="Total proposed reduction across recommended plants, in MW",
    )

    remaining_shortfall_mw: float = Field(
        ...,
        ge=0,
        description="Unmet portion of the requested reduction, in MW",
    )

    target_met: bool = Field(
        ...,
        description="Whether the requested reduction target is achievable by the recommendations",
    )

    operator_authorized: bool = Field(
        ...,
        description="Whether operator authorisation was recorded",
    )

    recommendations: list[PlantCurtailmentRecommendation] = Field(
        default_factory=list,
        description="Ranked plant curtailment recommendations",
    )

    limitations: list[str] = Field(
        default_factory=list,
        description="Data gaps, assumptions, or constraints affecting the assessment",
    )


