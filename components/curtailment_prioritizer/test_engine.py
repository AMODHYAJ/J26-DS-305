
from pathlib import Path

import pandas as pd

from components.curtailment_prioritizer.engine import assess_scenario
from components.curtailment_prioritizer.schemas import (
    CurtailmentAssessmentOutput,
)

DATA_DIR = Path(__file__).parent / "data" / "synthetic"


def main():
    scenarios = pd.read_csv(DATA_DIR / "scenarios.csv")
    plants = pd.read_csv(DATA_DIR / "plants.csv")

    checked = 0
    status_counts = {}

    for scenario_id in scenarios["scenario_id"].astype(str):
        result = assess_scenario(scenario_id)

        # Every result must satisfy the defined API output schema.
        validated = CurtailmentAssessmentOutput.model_validate(result)

        assert validated.event_id == scenario_id
        assert validated.target_reduction_mw >= 0
        assert validated.proposed_total_reduction_mw >= 0
        assert validated.remaining_shortfall_mw >= 0

        # Proposed reductions must never exceed available generation.
        for recommendation in validated.recommendations:
            assert (
                    recommendation.recommended_reduction_mw
                    <= recommendation.available_generation_mw + 1e-6
            )

            # Recommended plants must be eligible and not NSCC-managed.
            plant = plants.loc[
                plants["plant_id"].astype(str)
                == recommendation.plant_id
                ]

            assert len(plant) == 1
            assert str(
                plant.iloc[0]["curtailment_eligible"]
            ).lower() == "true"
            assert str(
                plant.iloc[0]["managed_by_nscc"]
            ).lower() == "false"

        # Check that allocated reduction and reported shortfall agree.
        assert abs(
            validated.proposed_total_reduction_mw
            + validated.remaining_shortfall_mw
            - validated.target_reduction_mw
        ) <= 1e-5, (
            f"Reduction balance failed for {scenario_id}"
        )

        # Check status consistency.
        if validated.assessment_status == "NO_ACTION_REQUIRED":
            assert validated.target_reduction_mw == 0
            assert not validated.recommendations

        if validated.assessment_status == "TARGET_MET":
            assert validated.target_met
            assert validated.remaining_shortfall_mw <= 1e-6

        if validated.assessment_status == "TARGET_NOT_MET":
            assert not validated.target_met
            assert validated.remaining_shortfall_mw > 1e-6

        # Priority ranks must be sequential and unique.
        ranks = [
            item.priority_rank for item in validated.recommendations
        ]
        assert ranks == list(range(1, len(ranks) + 1))

        status_counts[validated.assessment_status] = (
                status_counts.get(validated.assessment_status, 0) + 1
        )
        checked += 1

    # A scenario below the target should require no action.
    no_action = assess_scenario("S0002")
    assert no_action["assessment_status"] == "NO_ACTION_REQUIRED"

    print(f"Scenarios checked: {checked}")
    print("All scenario outputs passed schema and invariant checks.")
    print("\nStatus distribution:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
