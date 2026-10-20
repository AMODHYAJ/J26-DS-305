from pathlib import Path
from datetime import datetime
import hashlib
import json

import pandas as pd


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

EXPERIMENT_DIR = Path(__file__).resolve().parent
C3_DIR = EXPERIMENT_DIR.parent

INPUT_FILE = (
        C3_DIR
        / "output"
        / "solar_loads_matched.csv"
)

OUTPUT_DIR = (
        EXPERIMENT_DIR
        / "evidence"
        / "exp04_load_adjusted_exposure"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ---------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------

PV_FACTORS = [0.90, 0.95, 1.00]


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def file_sha256(path):
    sha = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(
                lambda: file.read(8192),
                b""
        ):
            sha.update(chunk)

    return sha.hexdigest()


# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

df = pd.read_csv(INPUT_FILE)

if "model_load_kw" in df.columns:
    LOAD_COL = "model_load_kw"

elif "load_kw" in df.columns:
    LOAD_COL = "load_kw"

else:
    raise ValueError(
        "No modelled load column found."
    )


required_columns = [
    "csc",
    "gss",
    "feeder",
    "section",
    "sin",
    "kva",
    "solar_kw",
    "solar_to_kva",
    "load_matched",
    LOAD_COL
]

missing = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing:
    raise ValueError(
        f"Missing columns: {missing}"
    )


# ---------------------------------------------------------
# KEEP USABLE TRANSFORMERS
# ---------------------------------------------------------

matched = df[
    (df["load_matched"] == True)
    & (df[LOAD_COL].notna())
    & (df[LOAD_COL] >= 0)
    & (df["kva"] > 0)
    ].copy()


# ---------------------------------------------------------
# RUN PV SCENARIOS
# ---------------------------------------------------------

scenario_records = []

for pv_factor in PV_FACTORS:

    for _, row in matched.iterrows():

        estimated_pv_kw = (
                row["solar_kw"]
                * pv_factor
        )

        net_margin_kw = (
                estimated_pv_kw
                - row[LOAD_COL]
        )

        exposure_score = (
                net_margin_kw
                / row["kva"]
        )

        scenario_records.append({
            "csc": row["csc"],
            "gss": row["gss"],
            "feeder": row["feeder"],
            "section": row["section"],
            "sin": row["sin"],

            "kva": row["kva"],
            "solar_kw": row["solar_kw"],
            "solar_to_kva": row["solar_to_kva"],
            "model_load_kw": row[LOAD_COL],

            "pv_factor": pv_factor,

            "estimated_pv_kw": round(
                estimated_pv_kw,
                4
            ),

            "net_margin_kw": round(
                net_margin_kw,
                4
            ),

            "exposure_score": round(
                exposure_score,
                6
            ),

            "estimated_reverse_condition": (
                    net_margin_kw > 0
            )
        })


scenario_df = pd.DataFrame(
    scenario_records
)


# ---------------------------------------------------------
# TRANSFORMER SUMMARY
# ---------------------------------------------------------

group_columns = [
    "csc",
    "gss",
    "feeder",
    "section",
    "sin",
    "kva",
    "solar_kw",
    "solar_to_kva",
    "model_load_kw"
]


summary = (
    scenario_df
    .groupby(
        group_columns,
        dropna=False
    )
    .agg(
        min_exposure=(
            "exposure_score",
            "min"
        ),

        mean_exposure=(
            "exposure_score",
            "mean"
        ),

        median_exposure=(
            "exposure_score",
            "median"
        ),

        max_exposure=(
            "exposure_score",
            "max"
        ),

        reverse_scenarios=(
            "estimated_reverse_condition",
            "sum"
        ),

        reverse_scenario_pct=(
            "estimated_reverse_condition",
            "mean"
        )
    )
    .reset_index()
)


summary["reverse_scenario_pct"] = (
        summary["reverse_scenario_pct"]
        * 100
).round(2)


# ---------------------------------------------------------
# CONTINUOUS PRIORITY RANK
# ---------------------------------------------------------

summary["exposure_rank"] = (
    summary["median_exposure"]
    .rank(
        method="min",
        ascending=False
    )
    .astype(int)
)


summary["solar_only_rank"] = (
    summary["solar_to_kva"]
    .rank(
        method="min",
        ascending=False
    )
    .astype(int)
)


summary["rank_change"] = (
        summary["solar_only_rank"]
        - summary["exposure_rank"]
)


summary["absolute_rank_change"] = (
    summary["rank_change"].abs()
)


# ---------------------------------------------------------
# SIMPLE ROBUSTNESS DESCRIPTION
# ---------------------------------------------------------

def reverse_status(pct):

    if pct == 0:
        return "No reverse condition in tested PV scenarios"

    elif pct == 100:
        return "Reverse condition in all tested PV scenarios"

    else:
        return "PV-factor dependent"


summary["scenario_status"] = (
    summary["reverse_scenario_pct"]
    .apply(reverse_status)
)


# ---------------------------------------------------------
# RANK AGREEMENT
# ---------------------------------------------------------

rank_correlation = (
    summary["solar_only_rank"]
    .corr(
        summary["exposure_rank"]
    )
)


# ---------------------------------------------------------
# TOP-N OVERLAP
# ---------------------------------------------------------

def calculate_overlap(data, n):

    solar_top = set(
        data.nsmallest(
            n,
            "solar_only_rank"
        )["sin"]
    )

    exposure_top = set(
        data.nsmallest(
            n,
            "exposure_rank"
        )["sin"]
    )

    overlap = (
            solar_top
            & exposure_top
    )

    return {
        "top_n": n,
        "overlap_count": len(overlap),
        "overlap_pct": round(
            len(overlap)
            / n
            * 100,
            2
        )
    }


overlap_df = pd.DataFrame([
    calculate_overlap(summary, 10),
    calculate_overlap(summary, 20),
    calculate_overlap(summary, 50)
])


# ---------------------------------------------------------
# PV SCENARIO SUMMARY
# ---------------------------------------------------------

pv_summary = (
    scenario_df
    .groupby("pv_factor")
    .agg(
        transformers=(
            "sin",
            "count"
        ),

        reverse_condition_count=(
            "estimated_reverse_condition",
            "sum"
        ),

        reverse_condition_pct=(
            "estimated_reverse_condition",
            "mean"
        ),

        mean_exposure=(
            "exposure_score",
            "mean"
        ),

        median_exposure=(
            "exposure_score",
            "median"
        ),

        max_exposure=(
            "exposure_score",
            "max"
        )
    )
    .reset_index()
)


pv_summary["reverse_condition_pct"] = (
        pv_summary["reverse_condition_pct"]
        * 100
).round(2)


# ---------------------------------------------------------
# SORT FINAL TRANSFORMER TABLE
# ---------------------------------------------------------

summary = summary.sort_values(
    [
        "exposure_rank",
        "sin"
    ]
)


# ---------------------------------------------------------
# SAVE OUTPUTS
# ---------------------------------------------------------

scenario_df.to_csv(
    OUTPUT_DIR
    / "scenario_results.csv",
    index=False
)


summary.to_csv(
    OUTPUT_DIR
    / "transformer_exposure_scores.csv",
    index=False
)


pv_summary.to_csv(
    OUTPUT_DIR
    / "pv_scenario_summary.csv",
    index=False
)


overlap_df.to_csv(
    OUTPUT_DIR
    / "solar_vs_exposure_overlap.csv",
    index=False
)


summary.head(20).to_csv(
    OUTPUT_DIR
    / "top20_exposure.csv",
    index=False
)


summary.sort_values(
    "absolute_rank_change",
    ascending=False
).head(30).to_csv(
    OUTPUT_DIR
    / "largest_rank_changes.csv",
    index=False
)


# ---------------------------------------------------------
# METADATA
# ---------------------------------------------------------

metadata = {
    "experiment": (
        "EXP04 Load-Adjusted "
        "Continuous Exposure"
    ),

    "run_time": (
        datetime.now().isoformat()
    ),

    "input_file": str(
        INPUT_FILE
    ),

    "input_sha256": (
        file_sha256(INPUT_FILE)
    ),

    "input_transformers": len(df),

    "usable_transformers": len(matched),

    "pv_factors": PV_FACTORS,

    "exposure_formula": (
        "(solar_kw * pv_factor "
        "- model_load_kw) / kva"
    ),

    "final_provisional_score": (
        "median exposure across "
        "tested PV factors"
    ),

    "limitations": [
        (
            "Modelled load is not measured "
            "historical transformer demand."
        ),
        (
            "PV generation is estimated using "
            "simple PV output factors."
        ),
        (
            "The score is a screening exposure "
            "indicator and does not represent "
            "confirmed reverse power flow."
        ),
        (
            "Voltage, feeder impedance, losses, "
            "power factor and phase imbalance "
            "are not represented."
        )
    ]
}


with open(
        OUTPUT_DIR
        / "experiment_metadata.json",
        "w",
        encoding="utf-8"
) as file:

    json.dump(
        metadata,
        file,
        indent=4
    )


# ---------------------------------------------------------
# TEXT SUMMARY
# ---------------------------------------------------------

status_counts = (
    summary["scenario_status"]
    .value_counts()
)


median_rank_change = (
    summary[
        "absolute_rank_change"
    ].median()
)


large_change_25 = int(
    (
            summary[
                "absolute_rank_change"
            ] >= 25
    ).sum()
)


large_change_50 = int(
    (
            summary[
                "absolute_rank_change"
            ] >= 50
    ).sum()
)


with open(
        OUTPUT_DIR
        / "experiment_summary.txt",
        "w",
        encoding="utf-8"
) as file:

    file.write(
        "EXPERIMENT 04 - LOAD-ADJUSTED EXPOSURE\n"
    )

    file.write(
        "=" * 55 + "\n\n"
    )

    file.write(
        f"Input transformers: {len(df)}\n"
    )

    file.write(
        f"Transformers with usable "
        f"modelled load: {len(matched)}\n\n"
    )

    file.write(
        "Exposure formula:\n"
        "(solar_kw * pv_factor "
        "- model_load_kw) / kva\n\n"
    )

    file.write(
        "PV factors tested:\n"
        f"{PV_FACTORS}\n\n"
    )

    file.write(
        "Scenario status counts:\n"
    )

    file.write(
        status_counts.to_string()
    )

    file.write("\n\n")

    file.write(
        "Solar-only vs load-adjusted "
        "rank correlation: "
        f"{rank_correlation:.4f}\n\n"
    )

    file.write(
        "Top-N overlap:\n"
    )

    file.write(
        overlap_df.to_string(
            index=False
        )
    )

    file.write("\n\n")

    file.write(
        f"Median absolute rank change: "
        f"{median_rank_change:.2f}\n"
    )

    file.write(
        f"Transformers moving >=25 "
        f"positions: {large_change_25}\n"
    )

    file.write(
        f"Transformers moving >=50 "
        f"positions: {large_change_50}\n\n"
    )

    file.write(
        "IMPORTANT:\n"
        "The resulting score is a provisional "
        "screening exposure score based on "
        "CEB modelled load. It is not confirmed "
        "reverse power flow or a final risk label.\n"
    )


print("\nEXP04 completed.")

print(
    "Usable transformers:",
    len(matched)
)

print(
    "Solar-only vs exposure rank correlation:",
    round(
        rank_correlation,
        4
    )
)

print(
    f"Evidence saved to:\n{OUTPUT_DIR}"
)