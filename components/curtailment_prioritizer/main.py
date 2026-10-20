
from fastapi import FastAPI, HTTPException, Query
import csv
from pathlib import Path
from fastapi import HTTPException

from components.curtailment_prioritizer.engine import assess_scenario
from components.curtailment_prioritizer.schemas import (
    CurtailmentAssessmentOutput,
)

app = FastAPI(
    title="DCC Curtailment Prioritizer",
    description=(
        "Explainable, synthetic-data-based decision support "
        "for distribution-level solar curtailment prioritisation."
    ),
    version="0.2.0",
)


@app.get("/")
def home():
    return {
        "message": "DCC Curtailment Prioritizer API is running",
        "status": "success",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post(
    "/assess/{scenario_id}",
    response_model=CurtailmentAssessmentOutput,
)
def assess(
        scenario_id: str,
        operator_authorized: bool = Query(
            default=False,
            description=(
                    "Records whether an operator has authorised the proposed "
                    "curtailment. This API does not issue control commands."
            ),
        ),
):
    result = assess_scenario(
        scenario_id=scenario_id,
        operator_authorized=operator_authorized,
    )

    if result["assessment_status"] == "INSUFFICIENT_DATA":
        raise HTTPException(
            status_code=404
            if "not found" in result["limitations"][0].lower()
            else 422,
            detail=result["limitations"],
        )

    return result

DATA_DIR = (
        Path(__file__).parent
        / "data"
        / "synthetic"
)


@app.get("/scenarios")
def list_scenarios():
    scenarios_file = DATA_DIR / "scenarios.csv"

    if not scenarios_file.exists():
        raise HTTPException(
            status_code=503,
            detail="Synthetic scenario dataset is unavailable.",
        )

    try:
        with scenarios_file.open(
                "r",
                newline="",
                encoding="utf-8-sig",
        ) as file:
            reader = csv.DictReader(file)
            scenarios = []

            for row in reader:
                scenarios.append({
                    "scenario_id": row["scenario_id"],
                    "transformer_id": row.get("transformer_id", ""),
                    "scenario_description": row.get(
                        "scenario_description", ""
                    ),
                })

        return {
            "count": len(scenarios),
            "scenarios": scenarios,
        }

    except (OSError, KeyError, csv.Error) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read the scenario dataset: {exc}",
        ) from exc
