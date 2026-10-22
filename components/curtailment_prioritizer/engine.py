
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data" / "synthetic"

# Explicit prototype assumption, not a measured CEB value.
ASSUMED_POWER_FACTOR = 0.95
TOLERANCE_MW = 1e-6


def assess_scenario(
        scenario_id: str,
        data_dir: Path = DATA_DIR,
        operator_authorized: bool = False,
) -> dict:
    """Assess a synthetic transformer-loading scenario.

    This is an explainable decision-support prototype, not a power-flow
    simulator or an automatic plant-control system.
    """

    required_files = [
        "scenarios.csv",
        "transformers.csv",
        "plants.csv",
        "plant_outputs.csv",
    ]

    for filename in required_files:
        if not (data_dir / filename).exists():
            return _error_result(
                scenario_id,
                f"Required data file is missing: {filename}",
            )

    scenarios = pd.read_csv(data_dir / "scenarios.csv")
    transformers = pd.read_csv(data_dir / "transformers.csv")
    plants = pd.read_csv(data_dir / "plants.csv")
    outputs = pd.read_csv(data_dir / "plant_outputs.csv")

    scenario_rows = scenarios.loc[
        scenarios["scenario_id"].astype(str) == str(scenario_id)
        ]

    if len(scenario_rows) != 1:
        return _error_result(
            scenario_id,
            "Scenario ID was not found or is not unique.",
        )

    scenario = scenario_rows.iloc[0]
    transformer_id = str(scenario["transformer_id"])

    transformer_rows = transformers.loc[
        transformers["transformer_id"].astype(str) == transformer_id
        ]

    if len(transformer_rows) != 1:
        return _error_result(
            scenario_id,
            "Transformer data is missing or not unique.",
        )

    transformer = transformer_rows.iloc[0]

    try:
        observed_loading = float(scenario["observed_loading_pct"])
        target_loading = float(scenario["target_loading_pct"])
        rated_capacity_kva = float(transformer["rated_capacity_kva"])
        safe_loading = float(transformer["safe_loading_pct"])
    except (TypeError, ValueError):
        return _error_result(
            scenario_id,
            "Required loading or transformer-rating data is invalid.",
        )

    if (
            not all(
                pd.notna(value)
                for value in [
                    observed_loading,
                    target_loading,
                    rated_capacity_kva,
                    safe_loading,
                ]
            )
            or rated_capacity_kva <= 0
            or not 0 <= observed_loading <= 200
            or not 0 <= target_loading <= 200
            or not 0 <= safe_loading <= 200
    ):
        return _error_result(
            scenario_id,
            "Loading percentages or transformer rating are outside "
            "the supported prototype range.",
        )

    effective_target_pct = min(target_loading, safe_loading)
    excess_pct_points = max(
        0.0, observed_loading - effective_target_pct
    )

    # Convert the assumed excess apparent power into MW using an
    # explicitly assumed power factor. This is a scenario calculation,
    # not a validated electrical model.
    target_reduction_mw = (
            rated_capacity_kva
            * (excess_pct_points / 100.0)
            * ASSUMED_POWER_FACTOR
            / 1000.0
    )

    if target_reduction_mw <= TOLERANCE_MW:
        return {
            "event_id": str(scenario_id),
            "assessment_status": "NO_ACTION_REQUIRED",
            "target_reduction_mw": 0.0,
            "proposed_total_reduction_mw": 0.0,
            "remaining_shortfall_mw": 0.0,
            "target_met": True,
            "operator_authorized": operator_authorized,
            "recommendations": [],
            "limitations": [
                "Synthetic scenario; not measured CEB performance.",
                "No curtailment is proposed because loading is at or "
                "below the effective target threshold.",
            ],
        }

    scenario_outputs = outputs.loc[
        (outputs["scenario_id"].astype(str) == str(scenario_id))
        & (outputs["transformer_id"].astype(str) == transformer_id)
        ].copy()

    if scenario_outputs.empty:
        return {
            "event_id": str(scenario_id),
            "assessment_status": "TARGET_NOT_MET",
            "target_reduction_mw": round(target_reduction_mw, 6),
            "proposed_total_reduction_mw": 0.0,
            "remaining_shortfall_mw": round(target_reduction_mw, 6),
            "target_met": False,
            "operator_authorized": operator_authorized,
            "recommendations": [],
            "limitations": [
                "No candidate plant-output records were available.",
                "Synthetic scenario; not measured CEB performance.",
            ],
        }

    plant_ids = plants["plant_id"].astype(str)
    eligible_plants = plants.loc[
        (plants["transformer_id"].astype(str) == transformer_id)
        & plants["curtailment_eligible"].astype(str).str.lower().eq("true")
        & ~plants["managed_by_nscc"].astype(str).str.lower().eq("true")
        ].copy()

    # Join outputs to the plant register so eligibility is verified
    # independently of the output file.
    candidates = scenario_outputs.merge(
        eligible_plants[
            [
                "plant_id",
                "plant_name",
                "transformer_id",
                "feeder_id",
                "installed_capacity_mw",
            ]
        ],
        on=["plant_id", "transformer_id", "feeder_id"],
        how="inner",
        suffixes=("_output", "_plant"),
        validate="many_to_one",
    )

    if candidates.empty:
        return {
            "event_id": str(scenario_id),
            "assessment_status": "TARGET_NOT_MET",
            "target_reduction_mw": round(target_reduction_mw, 6),
            "proposed_total_reduction_mw": 0.0,
            "remaining_shortfall_mw": round(target_reduction_mw, 6),
            "target_met": False,
            "operator_authorized": operator_authorized,
            "recommendations": [],
            "limitations": [
                "No eligible, non-NSCC-managed candidate plants were found.",
                "Synthetic scenario; not measured CEB performance.",
            ],
        }

    candidates["available_generation_mw"] = pd.to_numeric(
        candidates["available_generation_mw"], errors="coerce"
    )
    candidates["assumed_loading_contribution_pct"] = pd.to_numeric(
        candidates["assumed_loading_contribution_pct"],
        errors="coerce",
    )
    candidates["installed_capacity_mw"] = pd.to_numeric(
        candidates["installed_capacity_mw"], errors="coerce"
    )

    valid = (
            candidates["available_generation_mw"].notna()
            & candidates["assumed_loading_contribution_pct"].notna()
            & candidates["installed_capacity_mw"].notna()
            & (candidates["available_generation_mw"] >= 0)
            & (candidates["installed_capacity_mw"] > 0)
            & (
                    candidates["available_generation_mw"]
                    <= candidates["installed_capacity_mw"] + TOLERANCE_MW
            )
            & (candidates["assumed_loading_contribution_pct"] >= 0)
    )
    candidates = candidates.loc[valid].copy()

    if candidates.empty:
        return _error_result(
            scenario_id,
            "No valid candidate generation records were available.",
        )

    # Higher assumed contribution receives higher priority.
    # Plant ID is a deterministic tie-breaker.
    candidates = candidates.sort_values(
        ["assumed_loading_contribution_pct", "plant_id"],
        ascending=[False, True],
    ).reset_index(drop=True)

    recommendations = []
    proposed_total = 0.0

    for _, plant in candidates.iterrows():
        if proposed_total >= target_reduction_mw - TOLERANCE_MW:
            break

        available_mw = float(plant["available_generation_mw"])
        remaining_mw = target_reduction_mw - proposed_total
        proposed_mw = min(available_mw, remaining_mw)

        if proposed_mw <= TOLERANCE_MW:
            continue

        rank = len(recommendations) + 1
        contribution = float(
            plant["assumed_loading_contribution_pct"]
        )

        recommendations.append(
            {
                "plant_id": str(plant["plant_id"]),
                "plant_name": str(plant["plant_name"]),
                "priority_rank": rank,
                "available_generation_mw": round(available_mw, 6),
                "recommended_reduction_mw": round(proposed_mw, 6),
                "reason": (
                    f"Ranked {rank} because its assumed contribution "
                    f"score ({contribution:.3f}%) was used for priority "
                    "ordering. Proposed reduction is limited to the "
                    "remaining target and available generation."
                ),
            }
        )

        proposed_total += proposed_mw

    shortfall = max(0.0, target_reduction_mw - proposed_total)
    target_met = shortfall <= TOLERANCE_MW

    limitations = [
        "All scenario and plant-output records are synthetic.",
        "Priority uses an assumed contribution score, not measured "
        "causal contribution to transformer loading.",
        f"Power factor of {ASSUMED_POWER_FACTOR:.2f} is an explicit "
        "prototype assumption.",
        "The MW reduction calculation is simplified and does not "
        "replace an electrical power-flow or thermal model.",
        "Recommendations are decision support only; no plant control "
        "command is issued.",
    ]

    if not operator_authorized:
        limitations.append(
            "Operator authorisation has not been recorded. "
            "Recommendations are not permission to execute curtailment."
        )

    return {
        "event_id": str(scenario_id),
        "assessment_status": "TARGET_MET" if target_met else "TARGET_NOT_MET",
        "target_reduction_mw": round(target_reduction_mw, 6),
        "proposed_total_reduction_mw": round(proposed_total, 6),
        "remaining_shortfall_mw": round(shortfall, 6),
        "target_met": target_met,
        "operator_authorized": operator_authorized,
        "recommendations": recommendations,
        "limitations": limitations,
    }


def _error_result(scenario_id: str, message: str) -> dict:
    return {
        "event_id": str(scenario_id),
        "assessment_status": "INSUFFICIENT_DATA",
        "target_reduction_mw": 0.0,
        "proposed_total_reduction_mw": 0.0,
        "remaining_shortfall_mw": 0.0,
        "target_met": False,
        "operator_authorized": False,
        "recommendations": [],
        "limitations": [message],
    }


if __name__ == "__main__":
    result = assess_scenario("S0001")

    import json

    print(json.dumps(result, indent=2))
