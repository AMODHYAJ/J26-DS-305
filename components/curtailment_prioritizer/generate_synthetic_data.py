
from pathlib import Path
import argparse

import numpy as np
import pandas as pd


DATA_DIR = Path(__file__).parent / "data" / "synthetic"


def generate_data(
        n_transformers=20,
        feeders_per_transformer=2,
        plants_per_transformer=5,
        n_scenarios=1000,
        seed=42,
):
    """Generate reproducible synthetic data for C4 prototype testing.

    This is a simplified rule-testing dataset, not an electrical
    power-flow simulation or measured CEB operational data.
    """

    if min(
            n_transformers,
            feeders_per_transformer,
            plants_per_transformer,
            n_scenarios,
    ) < 1:
        raise ValueError("All generation counts must be at least 1.")

    rng = np.random.default_rng(seed)

    transformers = []
    feeders = []
    plants = []
    scenarios = []
    outputs = []
    expected = []

    # ---------------------------------------------------------
    # 1. Generate assumed primary transformers
    # ---------------------------------------------------------
    transformer_capacity_kva = 10000.0
    safe_loading_pct = 90.0

    for t in range(1, n_transformers + 1):
        tid = f"T{t:04d}"

        transformers.append({
            "transformer_id": tid,
            "transformer_name": f"Assumed Primary Transformer {t}",
            "rated_capacity_kva": transformer_capacity_kva,
            "safe_loading_pct": safe_loading_pct,
            "voltage_level": "PRIMARY",
            "provenance": "synthetic",
            "source_reference": "Synthetic prototype assumption",
        })

        # Create feeders belonging to this transformer.
        for f in range(1, feeders_per_transformer + 1):
            fid = f"F{(t - 1) * feeders_per_transformer + f:04d}"

            feeders.append({
                "feeder_id": fid,
                "feeder_name": f"Assumed Feeder {fid}",
                "transformer_id": tid,
                "provenance": "synthetic",
                "source_reference": "Synthetic prototype assumption",
            })

    # ---------------------------------------------------------
    # 2. Generate plants with consistent feeder assignments
    # ---------------------------------------------------------
    for t in range(1, n_transformers + 1):
        tid = f"T{t:04d}"

        transformer_feeders = [
            feeder["feeder_id"]
            for feeder in feeders
            if feeder["transformer_id"] == tid
        ]

        for p in range(1, plants_per_transformer + 1):
            plant_number = (t - 1) * plants_per_transformer + p
            pid = f"P{plant_number:04d}"
            fid = transformer_feeders[(p - 1) % len(transformer_feeders)]

            installed_capacity = round(
                float(rng.uniform(0.5, 5.0)), 3
            )

            # Some plants are deliberately managed by NSCC.
            managed = bool(rng.random() < 0.10)

            plants.append({
                "plant_id": pid,
                "plant_name": f"Synthetic Solar Plant {pid}",
                "transformer_id": tid,
                "feeder_id": fid,
                "installed_capacity_mw": installed_capacity,
                "curtailment_eligible": not managed,
                "managed_by_nscc": managed,
                "provenance": "synthetic",
                "source_reference": "Generated prototype data",
            })

    plant_lookup = {plant["plant_id"]: plant for plant in plants}
    transformer_lookup = {
        transformer["transformer_id"]: transformer
        for transformer in transformers
    }

    # ---------------------------------------------------------
    # 3. Generate scenarios and eligible plant outputs
    # ---------------------------------------------------------
    loading_options = [75.0, 85.0, 92.0, 95.0, 100.0, 105.0]

    for s in range(1, n_scenarios + 1):
        sid = f"S{s:04d}"

        tid = f"T{int(rng.integers(1, n_transformers + 1)):04d}"
        transformer = transformer_lookup[tid]

        observed_loading = float(rng.choice(loading_options))
        target_loading = float(transformer["safe_loading_pct"])
        excess_pct = max(0.0, observed_loading - target_loading)

        # These are contextual synthetic values. They do not
        # determine the observed loading percentage.
        background_demand = round(
            float(rng.uniform(2.0, 8.0)), 3
        )
        background_solar = round(
            float(rng.uniform(0.0, 1.5)), 3
        )

        scenarios.append({
            "scenario_id": sid,
            "transformer_id": tid,
            "background_demand_mw": background_demand,
            "background_solar_mw": background_solar,
            "baseline_loading_pct": observed_loading,
            "observed_loading_pct": observed_loading,
            "target_loading_pct": target_loading,
            "scenario_description": (
                "Loading below threshold"
                if excess_pct == 0
                else "Synthetic loading exceedance requiring assessment"
            ),
            "provenance": "synthetic",
        })

        # Only plants connected to this transformer and eligible
        # for DCC control enter the curtailment candidate set.
        matching_plants = [
            plant for plant in plants
            if plant["transformer_id"] == tid
               and plant["curtailment_eligible"]
               and not plant["managed_by_nscc"]
        ]

        scenario_candidates = []

        for plant in matching_plants:
            available = round(
                float(
                    plant["installed_capacity_mw"]
                    * rng.uniform(0.2, 1.0)
                ),
                3,
            )

            # Simplified approximation:
            # 1 MW is treated as 10 percentage points of loading
            # on the assumed 10 MVA transformer.
            # This is a prototype assumption, not a grid calculation.
            assumed_contribution_pct = round(
                available
                / (float(transformer["rated_capacity_kva"]) / 1000.0)
                * 100.0,
                3,
                )

            scenario_candidates.append({
                "scenario_id": sid,
                "plant_id": plant["plant_id"],
                "feeder_id": plant["feeder_id"],
                "transformer_id": tid,
                "available_generation_mw": available,
                "assumed_loading_contribution_pct": (
                    assumed_contribution_pct
                ),
                "control_status": "AVAILABLE",
                "provenance": "synthetic",
            })

        # The output file records eligible candidates only.
        outputs.extend(scenario_candidates)

        # -----------------------------------------------------
        # 4. Create an independent, rule-based expected result
        # -----------------------------------------------------
        total_assumed_contribution = sum(
            row["assumed_loading_contribution_pct"]
            for row in scenario_candidates
        )

        if excess_pct <= 0:
            expected_status = "NO_ACTION_REQUIRED"
            target_met = True
            priority_plant = "NONE"
            reason = "Loading is at or below the safe threshold."

        elif not scenario_candidates:
            expected_status = "TARGET_NOT_MET"
            target_met = False
            priority_plant = "NONE"
            reason = "No eligible plants are available."

        else:
            # Rank candidates by assumed contribution, highest first.
            ranked_candidates = sorted(
                scenario_candidates,
                key=lambda row: (
                    row["assumed_loading_contribution_pct"],
                    row["available_generation_mw"],
                ),
                reverse=True,
            )

            priority_plant = ranked_candidates[0]["plant_id"]

            target_met = (
                    total_assumed_contribution + 1e-9 >= excess_pct
            )

            expected_status = (
                "ASSESSMENT_COMPLETE"
                if target_met
                else "TARGET_NOT_MET"
            )

            reason = (
                "Eligible candidate capacity is sufficient under "
                "the simplified contribution assumption."
                if target_met
                else "Eligible candidate capacity is insufficient "
                     "under the simplified contribution assumption."
            )

        expected.append({
            "scenario_id": sid,
            "expected_status": expected_status,
            "expected_target_met": target_met,
            "expected_priority_plant": priority_plant,
            "expected_reason": reason,
        })

    # ---------------------------------------------------------
    # 5. Write all six CSV files
    # ---------------------------------------------------------
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    datasets = {
        "transformers.csv": transformers,
        "feeders.csv": feeders,
        "plants.csv": plants,
        "scenarios.csv": scenarios,
        "plant_outputs.csv": outputs,
        "expected_results.csv": expected,
    }

    for filename, records in datasets.items():
        df = pd.DataFrame(records)
        df.to_csv(DATA_DIR / filename, index=False)
        print(f"Generated {filename}: {len(df)} rows")

    print(f"\nSynthetic data generated with seed={seed}.")
    print("Do not interpret this dataset as measured CEB performance.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic C4 curtailment prototype data."
    )
    parser.add_argument("--transformers", type=int, default=20)
    parser.add_argument("--feeders-per-transformer", type=int, default=2)
    parser.add_argument("--plants-per-transformer", type=int, default=5)
    parser.add_argument("--scenarios", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    generate_data(
        n_transformers=args.transformers,
        feeders_per_transformer=args.feeders_per_transformer,
        plants_per_transformer=args.plants_per_transformer,
        n_scenarios=args.scenarios,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
