
from pathlib import Path
import pandas as pd

# Project data folder
DATA_DIR = Path(__file__).parent / "data" / "synthetic"

FILES = {
    "transformers": "transformers.csv",
    "feeders": "feeders.csv",
    "plants": "plants.csv",
    "scenarios": "scenarios.csv",
    "plant_outputs": "plant_outputs.csv",
    "expected_results": "expected_results.csv",
}


def load_csv(name, filename):
    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    df = pd.read_csv(path)

    if df.empty:
        raise ValueError(f"{filename} contains no data rows.")

    if df.columns.duplicated().any():
        raise ValueError(f"{filename} has duplicate column names.")

    print(f"Loaded {name}: {len(df)} rows")
    return df


def main():
    data = {
        name: load_csv(name, filename)
        for name, filename in FILES.items()
    }

    transformers = data["transformers"]
    feeders = data["feeders"]
    plants = data["plants"]
    scenarios = data["scenarios"]
    outputs = data["plant_outputs"]
    expected = data["expected_results"]

    errors = []
    warnings = []

    # Required columns
    required = {
        "transformers": [
            "transformer_id", "rated_capacity_kva",
            "safe_loading_pct", "provenance"
        ],
        "feeders": [
            "feeder_id", "transformer_id", "provenance"
        ],
        "plants": [
            "plant_id", "installed_capacity_mw",
            "curtailment_eligible", "managed_by_nscc", "provenance"
        ],
        "scenarios": [
            "scenario_id", "transformer_id",
            "observed_loading_pct", "target_loading_pct"
        ],
        "plant_outputs": [
            "scenario_id", "plant_id", "feeder_id",
            "transformer_id", "available_generation_mw",
            "assumed_loading_contribution_pct",
            "control_status", "provenance"
        ],
        "expected_results": [
            "scenario_id", "expected_status",
            "expected_target_met", "expected_priority_plant"
        ],
    }

    for name, columns in required.items():
        missing = set(columns) - set(data[name].columns)
        if missing:
            errors.append(f"{name}: missing columns {sorted(missing)}")

    if errors:
        for error in errors:
            print("ERROR:", error)
        raise SystemExit("Fix the missing columns and run again.")

    # Duplicate IDs
    for name, column in [
        ("transformers", "transformer_id"),
        ("feeders", "feeder_id"),
        ("plants", "plant_id"),
        ("scenarios", "scenario_id"),
    ]:
        df = data[name]
        if df[column].isna().any():
            errors.append(f"{name}: blank {column} values")
        if df[column].duplicated().any():
            errors.append(f"{name}: duplicate {column} values")

    # Reference checks
    transformer_ids = set(transformers["transformer_id"].dropna())
    feeder_ids = set(feeders["feeder_id"].dropna())
    plant_ids = set(plants["plant_id"].dropna())
    scenario_ids = set(scenarios["scenario_id"].dropna())

    for _, row in feeders.iterrows():
        if row["transformer_id"] not in transformer_ids:
            errors.append(
                f"Feeder {row['feeder_id']}: unknown transformer "
                f"{row['transformer_id']}"
            )

    for _, row in scenarios.iterrows():
        if row["transformer_id"] not in transformer_ids:
            errors.append(
                f"Scenario {row['scenario_id']}: unknown transformer "
                f"{row['transformer_id']}"
            )

    for _, row in outputs.iterrows():
        sid = row["scenario_id"]
        pid = row["plant_id"]
        fid = row["feeder_id"]
        tid = row["transformer_id"]

        if sid not in scenario_ids:
            errors.append(f"Plant output references unknown scenario {sid}")
        if pid not in plant_ids:
            errors.append(f"Plant output references unknown plant {pid}")
        if fid not in feeder_ids:
            errors.append(f"Plant output references unknown feeder {fid}")
        if tid not in transformer_ids:
            errors.append(f"Plant output references unknown transformer {tid}")

        # Check feeder-to-transformer consistency
        matching = feeders.loc[feeders["feeder_id"] == fid, "transformer_id"]
        if not matching.empty and tid not in set(matching):
            errors.append(
                f"Output {sid}/{pid}: feeder {fid} does not belong "
                f"to transformer {tid}"
            )

        # Check scenario-to-transformer consistency
        scenario_match = scenarios.loc[
            scenarios["scenario_id"] == sid, "transformer_id"
        ]
        if not scenario_match.empty and tid not in set(scenario_match):
            errors.append(
                f"Output {sid}/{pid}: transformer {tid} differs from "
                f"the scenario transformer"
            )

    for _, row in expected.iterrows():
        if row["scenario_id"] not in scenario_ids:
            errors.append(
                f"Expected results reference unknown scenario "
                f"{row['scenario_id']}"
            )

    # Basic numeric and logical checks
    numeric_checks = [
        (transformers, "rated_capacity_kva", True, "transformer capacity"),
        (transformers, "safe_loading_pct", True, "safe loading threshold"),
        (plants, "installed_capacity_mw", True, "plant capacity"),
        (scenarios, "observed_loading_pct", False, "observed loading"),
        (scenarios, "target_loading_pct", True, "target loading"),
        (outputs, "available_generation_mw", False, "available generation"),
        (
            outputs,
            "assumed_loading_contribution_pct",
            False,
            "assumed contribution",
        ),
    ]

    for df, column, must_be_positive, label in numeric_checks:
        values = pd.to_numeric(df[column], errors="coerce")

        if values.isna().any():
            errors.append(f"{label}: missing or non-numeric values in {column}")
        elif must_be_positive and (values <= 0).any():
            errors.append(f"{label}: values must be greater than zero")
        elif not must_be_positive and (values < 0).any():
            errors.append(f"{label}: negative values are not allowed")

    # Check scenario and expected-result coverage
    if set(scenarios["scenario_id"]) != set(expected["scenario_id"]):
        warnings.append(
            "Scenario IDs and expected-result IDs do not match exactly."
        )

    # Check plant output capacity and eligibility
    plant_lookup = plants.set_index("plant_id")

    for _, row in outputs.iterrows():
        pid = row["plant_id"]
        if pid not in plant_lookup.index:
            continue

        capacity = pd.to_numeric(
            pd.Series([plant_lookup.loc[pid, "installed_capacity_mw"]]),
            errors="coerce",
        ).iloc[0]
        generation = pd.to_numeric(
            pd.Series([row["available_generation_mw"]]),
            errors="coerce",
        ).iloc[0]

        if pd.notna(capacity) and pd.notna(generation) and generation > capacity:
            errors.append(
                f"Plant {pid}: available generation exceeds installed capacity"
            )

        eligible = str(
            plant_lookup.loc[pid, "curtailment_eligible"]
        ).strip().lower()
        managed = str(
            plant_lookup.loc[pid, "managed_by_nscc"]
        ).strip().lower()

        if eligible in {"false", "0", "no"}:
            warnings.append(
                f"Plant {pid} is marked not eligible but appears in outputs."
            )
        if managed in {"true", "1", "yes"}:
            warnings.append(
                f"Plant {pid} is NSCC-managed; verify it is excluded "
                "from DCC recommendations."
            )

    print("\n--- VALIDATION SUMMARY ---")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")

    for error in errors:
        print("ERROR:", error)

    for warning in warnings:
        print("WARNING:", warning)

    if errors:
        raise SystemExit("\nValidation failed. Fix errors before proceeding.")

    print("\nStructural validation passed.")
    print("Warnings still require review before algorithm evaluation.")


if __name__ == "__main__":
    main()
