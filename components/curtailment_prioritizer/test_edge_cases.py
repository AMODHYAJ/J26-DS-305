
import shutil
import tempfile
from pathlib import Path

import pandas as pd

from components.curtailment_prioritizer.engine import assess_scenario

SOURCE_DIR = (
        Path(__file__).parent / "data" / "synthetic"
)


def main():
    scenarios = pd.read_csv(SOURCE_DIR / "scenarios.csv")

    # Find one scenario above the safe target and one below it.
    action_rows = scenarios[
        scenarios["observed_loading_pct"]
        > scenarios["target_loading_pct"]
        ]
    no_action_rows = scenarios[
        scenarios["observed_loading_pct"]
        <= scenarios["target_loading_pct"]
        ]

    assert not action_rows.empty
    assert not no_action_rows.empty

    action_id = str(action_rows.iloc[0]["scenario_id"])
    no_action_id = str(no_action_rows.iloc[0]["scenario_id"])

    # 1. Normal assessment: check allocation consistency.
    normal = assess_scenario(action_id)
    assert normal["assessment_status"] in {
        "TARGET_MET",
        "TARGET_NOT_MET",
    }
    assert abs(
        normal["proposed_total_reduction_mw"]
        + normal["remaining_shortfall_mw"]
        - normal["target_reduction_mw"]
    ) <= 1e-5

    print("PASS: Normal assessment and reduction balance")

    # 2. No-action scenario.
    no_action = assess_scenario(no_action_id)
    assert no_action["assessment_status"] == "NO_ACTION_REQUIRED"
    assert not no_action["recommendations"]

    print("PASS: No-action scenario")

    # 3. Simulate no eligible plants for the affected transformer.
    # Use temporary copies so the original dataset stays unchanged.
    with tempfile.TemporaryDirectory() as temp_name:
        temp_dir = Path(temp_name)

        for filename in [
            "scenarios.csv",
            "transformers.csv",
            "plants.csv",
            "plant_outputs.csv",
        ]:
            shutil.copy2(SOURCE_DIR / filename, temp_dir / filename)

        selected = scenarios.loc[
            scenarios["scenario_id"].astype(str) == action_id
            ].iloc[0]
        transformer_id = str(selected["transformer_id"])

        plants_path = temp_dir / "plants.csv"
        plants = pd.read_csv(plants_path)

        mask = plants["transformer_id"].astype(str) == transformer_id
        plants.loc[mask, "curtailment_eligible"] = False
        plants.loc[mask, "managed_by_nscc"] = True
        plants.to_csv(plants_path, index=False)

        insufficient = assess_scenario(
            action_id,
            data_dir=temp_dir,
        )

        assert insufficient["assessment_status"] == "TARGET_NOT_MET"
        assert not insufficient["recommendations"]
        assert insufficient["remaining_shortfall_mw"] > 0

        print("PASS: Insufficient eligible capacity")

    print("\nAll edge-case checks passed.")


if __name__ == "__main__":
    main()
