
from fastapi import FastAPI, HTTPException, Query
import csv
from pathlib import Path

from components.curtailment_prioritizer.engine import assess_scenario
from components.curtailment_prioritizer.schemas import (
    CurtailmentAssessmentOutput,
)
from components.curtailment_prioritizer.fairness_engine import rank_plants


app = FastAPI(
    title="DCC Curtailment Prioritizer",
    description=(
        "Explainable, rule-based decision support for "
        "distribution-level solar curtailment prioritisation."
    ),
    version="0.3.0",
)

DATA_DIR = Path(__file__).parent / "data" / "synthetic"
CURTAILMENT_HISTORY_FILE = (
        Path(__file__).parent / "data" / "curtailment_events_2026_unique_review.csv"
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
            status_code=(
                404
                if result["limitations"]
                   and "not found" in result["limitations"][0].lower()
                else 422
            ),
            detail=result["limitations"],
        )

    return result


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



@app.get("/fairness/ranking")
def fairness_ranking(
        recent_days: int = Query(
            default=30,
            ge=1,
            description="Days used for the recent-curtailment indicator.",
        ),
):
    if not CURTAILMENT_HISTORY_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail="The 2026 curtailment dataset is unavailable.",
        )

    try:
        with CURTAILMENT_HISTORY_FILE.open(
                "r",
                newline="",
                encoding="utf-8-sig",
        ) as file:
            reader = csv.DictReader(file)

            required_columns = {
                "ac_number",
                "curtailment_date",
            }

            if not required_columns.issubset(
                    set(reader.fieldnames or [])
            ):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Dataset must contain ac_number "
                        "and curtailment_date."
                    ),
                )

            rows = list(reader)

        events = []
        skipped_records = 0

        for row in rows:
            ac_number = (row.get("ac_number") or "").strip()
            event_date = (row.get("curtailment_date") or "").strip()

            if not ac_number or not event_date:
                skipped_records += 1
                continue

            events.append({
                "ac_number": ac_number,
                "timestamp": event_date,
                "curtailed_mwh": None,
            })

        if not events:
            raise HTTPException(
                status_code=422,
                detail="No usable dated candidate records were found.",
            )

        ranking = rank_plants(
            events=events,
            recent_days=recent_days,
        )

        return {
            "count": len(ranking),
            "ranking_method": "rule_based_candidate_event_frequency_recency",
            "recent_days": recent_days,
            "weights": {
                "energy": 0.0,
                "recent": 0.5,
                "frequency": 0.5,
            },
            "weights_status": "provisional_not_supervisor_approved",
            "data_source": CURTAILMENT_HISTORY_FILE.name,
            "study_period": {
                "start": "2026-01-01",
                "end": "2026-10-19",
            },
            "data_status": "candidate_records_not_fully_validated",
            "candidate_records_used": len(events),
            "records_skipped": skipped_records,
            "ranking": ranking,
        }

    except HTTPException:
        raise
    except (OSError, csv.Error, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not calculate candidate ranking: {exc}",
        ) from exc

