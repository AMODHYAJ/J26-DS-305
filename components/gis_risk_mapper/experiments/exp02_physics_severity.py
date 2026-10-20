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

INPUT_FILE = C3_DIR / "output" / "solar_by_transformer.csv"

OUTPUT_DIR = (
        EXPERIMENT_DIR
        / "evidence"
        / "exp02_physics_severity"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# DATA COLUMNS
# ---------------------------------------------------------

SIN_COL = "sin"
SOLAR_COL = "solar_kw"
KVA_COL = "kva"
RATIO_COL = "solar_to_kva"


# ---------------------------------------------------------
# SCENARIO SETTINGS
# ---------------------------------------------------------

LOAD_FRACTIONS = [
    0.05,
    0.10,
    0.15,
    0.20,
    0.25,
    0.30,
    0.35
]

PV_FACTORS = [
    0.90,
    0.95,
    1.00
]


# Baseline from EXP01 - comparison only
BASELINE_LOW = 0.50
BASELINE_HIGH = 1.00


def baseline_label(ratio):
    if ratio < BASELINE_LOW:
        return "Low"
    elif ratio < BASELINE_HIGH:
        return "Medium"
    else:
        return "High"


def file_sha256(path):
    sha = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            sha.update(chunk)

    return sha.hexdigest()


# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

df = pd.read_csv(INPUT_FILE)

required_columns = [
    "csc",
    "gss",
    "feeder",
    "section",
    SIN_COL,
    KVA_COL,
    SOLAR_COL,
    RATIO_COL
]

missing = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing:
    raise ValueError(
        f"Missing required columns: {missing}"
    )


df = df.dropna(
    subset=[
        SIN_COL,
        KVA_COL,
        SOLAR_COL,
        RATIO_COL
    ]
).copy()

df = df[df[KVA_COL] > 0].copy()


# ---------------------------------------------------------
# VERIFY EXISTING RATIO
# ---------------------------------------------------------

df["recalculated_ratio"] = (
        df[SOLAR_COL] / df[KVA_COL]
)

df["ratio_difference"] = (
        df[RATIO_COL] - df["recalculated_ratio"]
).abs()

max_ratio_difference = float(
    df["ratio_difference"].max()
)


# ---------------------------------------------------------
# BASELINE LABEL FOR COMPARISON
# ---------------------------------------------------------

df["baseline_label"] = (
    df[RATIO_COL]
    .apply(baseline_label)
)


# ---------------------------------------------------------
# RUN PHYSICS-BASED SCENARIOS
# ---------------------------------------------------------

scenario_records = []

scenario_number = 0

for load_fraction in LOAD_FRACTIONS:

    for pv_factor in PV_FACTORS:

        scenario_number += 1

        scenario_name = (
            f"L{load_fraction:.2f}_PV{pv_factor:.2f}"
        )

        for _, row in df.iterrows():

            transformer_kva = row[KVA_COL]
            installed_solar_kw = row[SOLAR_COL]

            estimated_pv_kw = (
                    installed_solar_kw
                    * pv_factor
            )

            assumed_load_kw = (
                    transformer_kva
                    * load_fraction
            )

            net_export_kw = (
                    estimated_pv_kw
                    - assumed_load_kw
            )

            reverse_export_kw = max(
                0.0,
                net_export_kw
            )

            reverse_loading_ratio = (
                    reverse_export_kw
                    / transformer_kva
            )

            reverse_flow = (
                    net_export_kw > 0
            )

            # Screening flag only:
            # active export alone is above nameplate kVA.
            above_nameplate = (
                    reverse_loading_ratio >= 1.0
            )

            scenario_records.append({
                "scenario": scenario_name,
                "load_fraction": load_fraction,
                "pv_factor": pv_factor,

                "csc": row["csc"],
                "gss": row["gss"],
                "feeder": row["feeder"],
                "section": row["section"],
                "sin": row["sin"],

                "kva": transformer_kva,
                "solar_kw": installed_solar_kw,
                "solar_to_kva": row[RATIO_COL],

                "estimated_pv_kw": round(
                    estimated_pv_kw,
                    4
                ),

                "assumed_load_kw": round(
                    assumed_load_kw,
                    4
                ),

                "net_export_kw": round(
                    net_export_kw,
                    4
                ),

                "reverse_export_kw": round(
                    reverse_export_kw,
                    4
                ),

                "reverse_loading_ratio": round(
                    reverse_loading_ratio,
                    6
                ),

                "reverse_flow": reverse_flow,
                "above_nameplate_screening": above_nameplate,

                "baseline_label": row["baseline_label"]
            })


scenario_df = pd.DataFrame(
    scenario_records
)


# ---------------------------------------------------------
# TRANSFORMER-LEVEL SEVERITY SUMMARY
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
    "baseline_label"
]


transformer_summary = (
    scenario_df
    .groupby(
        group_columns,
        dropna=False
    )
    .agg(
        scenarios_tested=(
            "scenario",
            "count"
        ),

        reverse_flow_scenarios=(
            "reverse_flow",
            "sum"
        ),

        reverse_flow_pct=(
            "reverse_flow",
            "mean"
        ),

        above_nameplate_scenarios=(
            "above_nameplate_screening",
            "sum"
        ),

        above_nameplate_pct=(
            "above_nameplate_screening",
            "mean"
        ),

        min_reverse_loading_ratio=(
            "reverse_loading_ratio",
            "min"
        ),

        mean_reverse_loading_ratio=(
            "reverse_loading_ratio",
            "mean"
        ),

        median_reverse_loading_ratio=(
            "reverse_loading_ratio",
            "median"
        ),

        max_reverse_loading_ratio=(
            "reverse_loading_ratio",
            "max"
        ),

        max_reverse_export_kw=(
            "reverse_export_kw",
            "max"
        )
    )
    .reset_index()
)


transformer_summary["reverse_flow_pct"] = (
        transformer_summary["reverse_flow_pct"]
        * 100
).round(2)

transformer_summary["above_nameplate_pct"] = (
        transformer_summary["above_nameplate_pct"]
        * 100
).round(2)


# ---------------------------------------------------------
# ROBUSTNESS STATUS
# ---------------------------------------------------------

def robustness_status(reverse_flow_pct):

    if reverse_flow_pct == 0:
        return "Never reverse in tested scenarios"

    elif reverse_flow_pct == 100:
        return "Reverse in all tested scenarios"

    else:
        return "Scenario-dependent"


transformer_summary["reverse_flow_status"] = (
    transformer_summary["reverse_flow_pct"]
    .apply(robustness_status)
)


# ---------------------------------------------------------
# CONTINUOUS SEVERITY RANK
# ---------------------------------------------------------

transformer_summary[
    "severity_rank"
] = (
    transformer_summary[
        "median_reverse_loading_ratio"
    ]
    .rank(
        method="min",
        ascending=False
    )
    .astype(int)
)


transformer_summary = (
    transformer_summary
    .sort_values(
        [
            "severity_rank",
            "sin"
        ]
    )
)


# ---------------------------------------------------------
# SCENARIO-LEVEL SUMMARY
# ---------------------------------------------------------

scenario_summary = (
    scenario_df
    .groupby(
        [
            "scenario",
            "load_fraction",
            "pv_factor"
        ]
    )
    .agg(
        transformers=(
            "sin",
            "count"
        ),

        reverse_flow_count=(
            "reverse_flow",
            "sum"
        ),

        reverse_flow_pct=(
            "reverse_flow",
            "mean"
        ),

        above_nameplate_count=(
            "above_nameplate_screening",
            "sum"
        ),

        above_nameplate_pct=(
            "above_nameplate_screening",
            "mean"
        ),

        mean_reverse_loading_ratio=(
            "reverse_loading_ratio",
            "mean"
        ),

        median_reverse_loading_ratio=(
            "reverse_loading_ratio",
            "median"
        ),

        max_reverse_loading_ratio=(
            "reverse_loading_ratio",
            "max"
        )
    )
    .reset_index()
)


scenario_summary["reverse_flow_pct"] = (
        scenario_summary["reverse_flow_pct"]
        * 100
).round(2)

scenario_summary["above_nameplate_pct"] = (
        scenario_summary["above_nameplate_pct"]
        * 100
).round(2)


# ---------------------------------------------------------
# COMPARE WITH EXP01 BASELINE LABELS
# ---------------------------------------------------------

baseline_vs_physics = pd.crosstab(
    transformer_summary[
        "baseline_label"
    ],
    transformer_summary[
        "reverse_flow_status"
    ],
    margins=True
)


# ---------------------------------------------------------
# TOP TRANSFORMERS
# ---------------------------------------------------------

top_20 = (
    transformer_summary
    .head(20)
    .copy()
)


# ---------------------------------------------------------
# SAVE EVIDENCE
# ---------------------------------------------------------

scenario_df.to_csv(
    OUTPUT_DIR / "scenario_results.csv",
    index=False
)

transformer_summary.to_csv(
    OUTPUT_DIR / "transformer_severity.csv",
    index=False
)

scenario_summary.to_csv(
    OUTPUT_DIR / "scenario_summary.csv",
    index=False
)

baseline_vs_physics.to_csv(
    OUTPUT_DIR / "baseline_vs_physics.csv"
)

top_20.to_csv(
    OUTPUT_DIR / "top20_severity.csv",
    index=False
)


# ---------------------------------------------------------
# METADATA
# ---------------------------------------------------------

metadata = {
    "experiment": (
        "EXP02 Physics-Based Continuous Severity"
    ),

    "run_time": datetime.now().isoformat(),

    "input_file": str(INPUT_FILE),

    "input_sha256": file_sha256(
        INPUT_FILE
    ),

    "transformers": len(df),

    "load_fractions": LOAD_FRACTIONS,

    "pv_factors": PV_FACTORS,

    "scenario_count": (
            len(LOAD_FRACTIONS)
            * len(PV_FACTORS)
    ),

    "formula": (
        "reverse_loading_ratio = "
        "max(0, solar_kw * pv_factor "
        "- kva * load_fraction) / kva"
    ),

    "important_limitations": [
        "Load fractions are scenario assumptions, not measured transformer demand.",
        "PV factors are scenario assumptions, not measured PV output.",
        "The calculation is a screening approximation and not an AC power-flow study.",
        "kW is compared with transformer kVA only as an approximate screening indicator.",
        "Voltage, losses, phase imbalance, power factor and feeder impedance are not modelled."
    ]
}


with open(
        OUTPUT_DIR / "experiment_metadata.json",
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
    transformer_summary[
        "reverse_flow_status"
    ]
    .value_counts()
)


above_nameplate_any = int(
    (
            transformer_summary[
                "above_nameplate_pct"
            ] > 0
    ).sum()
)

above_nameplate_all = int(
    (
            transformer_summary[
                "above_nameplate_pct"
            ] == 100
    ).sum()
)


with open(
        OUTPUT_DIR / "experiment_summary.txt",
        "w",
        encoding="utf-8"
) as file:

    file.write(
        "EXPERIMENT 02 - PHYSICS-BASED CONTINUOUS SEVERITY\n"
    )

    file.write("=" * 60 + "\n\n")

    file.write(
        f"Transformers analysed: {len(df)}\n"
    )

    file.write(
        f"Scenarios tested per transformer: "
        f"{len(LOAD_FRACTIONS) * len(PV_FACTORS)}\n"
    )

    file.write(
        f"Total transformer-scenario observations: "
        f"{len(scenario_df)}\n\n"
    )

    file.write(
        "Reverse-flow robustness status:\n"
    )

    file.write(
        status_counts.to_string()
    )

    file.write("\n\n")

    file.write(
        "Transformers above nameplate screening "
        "level in at least one scenario: "
        f"{above_nameplate_any}\n"
    )

    file.write(
        "Transformers above nameplate screening "
        "level in every scenario: "
        f"{above_nameplate_all}\n\n"
    )

    file.write(
        "Maximum difference between stored "
        "solar_to_kva and recalculated ratio: "
        f"{max_ratio_difference:.10f}\n\n"
    )

    file.write(
        "Baseline labels vs physics robustness:\n"
    )

    file.write(
        baseline_vs_physics.to_string()
    )

    file.write("\n\n")

    file.write(
        "IMPORTANT:\n"
        "This experiment does not claim actual measured "
        "reverse power flow. It tests transformer exposure "
        "under a defined grid of plausible operating "
        "assumptions.\n"
    )


print("\nEXP02 completed.")
print(
    f"Transformers analysed: {len(df)}"
)
print(
    f"Scenarios per transformer: "
    f"{len(LOAD_FRACTIONS) * len(PV_FACTORS)}"
)
print(
    f"Evidence saved to:\n{OUTPUT_DIR}"
)