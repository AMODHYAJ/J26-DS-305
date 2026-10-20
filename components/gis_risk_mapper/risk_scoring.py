from pathlib import Path
from datetime import datetime

import pandas as pd


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

C3_DIR = Path(__file__).resolve().parent

INPUT_FILE = (
        C3_DIR
        / "output"
        / "solar_loads_matched.csv"
)

OUTPUT_FILE = (
        C3_DIR
        / "output"
        / "transformer_risk_profile.csv"
)

SUMMARY_FILE = (
        C3_DIR
        / "output"
        / "risk_scoring_summary.txt"
)


# ---------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------

# Central screening assumption
CENTRAL_PV_FACTOR = 0.95

# Used only to test robustness around the central estimate
PV_FACTORS = [0.90, 0.95, 1.00]


# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

df = pd.read_csv(INPUT_FILE)


# Support both old and updated load column names
if "model_load_kw" in df.columns:
    LOAD_COL = "model_load_kw"

elif "load_kw" in df.columns:
    LOAD_COL = "load_kw"

else:
    raise ValueError(
        "No modelled load column found in input data."
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
    "load_matched"
]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Missing required columns: {missing_columns}"
    )


# ---------------------------------------------------------
# INITIALISE OUTPUT FIELDS
# ---------------------------------------------------------

df["assessment_method"] = ""
df["data_confidence"] = ""

df["estimated_pv_kw_95"] = pd.NA
df["exposure_score"] = pd.NA

df["reverse_condition_90"] = pd.NA
df["reverse_condition_95"] = pd.NA
df["reverse_condition_100"] = pd.NA

df["scenario_status"] = ""

df["priority_rank"] = pd.NA
df["fallback_rank"] = pd.NA

df["fallback_indicator"] = df["solar_to_kva"]


# ---------------------------------------------------------
# IDENTIFY TRANSFORMERS WITH USABLE MODELLED LOAD
# ---------------------------------------------------------

usable_load = (
        (df["load_matched"] == True)
        & (df[LOAD_COL].notna())
        & (df[LOAD_COL] >= 0)
        & (df["kva"] > 0)
)


# ---------------------------------------------------------
# PRIMARY LOAD-ADJUSTED ASSESSMENT
# ---------------------------------------------------------

df.loc[
    usable_load,
    "assessment_method"
] = "Load-adjusted exposure"

df.loc[
    usable_load,
    "data_confidence"
] = "Modelled-load supported"


# Central PV estimate
df.loc[
    usable_load,
    "estimated_pv_kw_95"
] = (
        df.loc[
            usable_load,
            "solar_kw"
        ]
        * CENTRAL_PV_FACTOR
)


# Continuous exposure score
df.loc[
    usable_load,
    "exposure_score"
] = (
            (
                    df.loc[
                        usable_load,
                        "solar_kw"
                    ]
                    * CENTRAL_PV_FACTOR
            )
            -
            df.loc[
                usable_load,
                LOAD_COL
            ]
    ) / df.loc[
        usable_load,
        "kva"
    ]


# ---------------------------------------------------------
# SCENARIO ROBUSTNESS
# ---------------------------------------------------------

for pv_factor, column_name in [
    (0.90, "reverse_condition_90"),
    (0.95, "reverse_condition_95"),
    (1.00, "reverse_condition_100")
]:

    estimated_pv = (
            df.loc[
                usable_load,
                "solar_kw"
            ]
            * pv_factor
    )

    modelled_load = df.loc[
        usable_load,
        LOAD_COL
    ]

    df.loc[
        usable_load,
        column_name
    ] = (
            estimated_pv
            > modelled_load
    )


# ---------------------------------------------------------
# SCENARIO STATUS
# ---------------------------------------------------------

def classify_scenario_status(row):

    values = [
        row["reverse_condition_90"],
        row["reverse_condition_95"],
        row["reverse_condition_100"]
    ]

    if any(pd.isna(value) for value in values):
        return "Load unavailable"

    true_count = sum(
        bool(value)
        for value in values
    )

    if true_count == 3:
        return "Persistent reverse condition"

    elif true_count == 0:
        return "No reverse condition"

    else:
        return "PV-factor dependent"


df["scenario_status"] = df.apply(
    classify_scenario_status,
    axis=1
)


# ---------------------------------------------------------
# PRIMARY PRIORITY RANK
# ---------------------------------------------------------

primary_scores = df.loc[
    usable_load,
    "exposure_score"
].astype(float)


df.loc[
    usable_load,
    "priority_rank"
] = (
    primary_scores
    .rank(
        method="min",
        ascending=False
    )
    .astype(int)
)


# ---------------------------------------------------------
# FALLBACK ASSESSMENT
# ---------------------------------------------------------

fallback_mask = ~usable_load


df.loc[
    fallback_mask,
    "assessment_method"
] = "Solar-only fallback"


df.loc[
    fallback_mask,
    "data_confidence"
] = "Limited - modelled load unavailable"


# Rank fallback records separately.
# Do NOT mix this ranking with the primary load-adjusted ranking.
fallback_scores = df.loc[
    fallback_mask,
    "solar_to_kva"
]


df.loc[
    fallback_mask,
    "fallback_rank"
] = (
    fallback_scores
    .rank(
        method="min",
        ascending=False
    )
    .astype(int)
)


# ---------------------------------------------------------
# ADD EXPLANATION FIELD
# ---------------------------------------------------------

def build_explanation(row):

    if row["assessment_method"] == "Load-adjusted exposure":

        return (
            f"Solar={row['solar_kw']:.2f} kW, "
            f"rating={row['kva']:.0f} kVA, "
            f"modelled load={row[LOAD_COL]:.2f} kW. "
            f"Exposure score uses 95% estimated PV output. "
            f"Scenario result: {row['scenario_status']}."
        )

    return (
        f"Solar={row['solar_kw']:.2f} kW, "
        f"rating={row['kva']:.0f} kVA. "
        f"Modelled load is unavailable, so this transformer "
        f"uses solar-to-kVA as a fallback screening indicator."
    )


df["assessment_explanation"] = df.apply(
    build_explanation,
    axis=1
)


# ---------------------------------------------------------
# SORT OUTPUT
# ---------------------------------------------------------

# Primary assessed transformers first, ranked highest priority first.
# Fallback transformers follow separately.

df["_sort_group"] = (
    df["assessment_method"]
    .map({
        "Load-adjusted exposure": 0,
        "Solar-only fallback": 1
    })
)


df = df.sort_values(
    [
        "_sort_group",
        "priority_rank",
        "fallback_rank",
        "sin"
    ],
    na_position="last"
)


df = df.drop(
    columns=["_sort_group"]
)


# ---------------------------------------------------------
# SAVE OUTPUT
# ---------------------------------------------------------

df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ---------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------

primary_count = int(
    usable_load.sum()
)

fallback_count = int(
    fallback_mask.sum()
)


status_counts = (
    df.loc[
        usable_load,
        "scenario_status"
    ]
    .value_counts()
)


with open(
        SUMMARY_FILE,
        "w",
        encoding="utf-8"
) as file:

    file.write(
        "C3 TRANSFORMER RISK / EXPOSURE PROFILE\n"
    )

    file.write(
        "=" * 55 + "\n\n"
    )

    file.write(
        f"Generated: {datetime.now().isoformat()}\n\n"
    )

    file.write(
        f"Total transformers: {len(df)}\n"
    )

    file.write(
        f"Load-adjusted assessment: {primary_count}\n"
    )

    file.write(
        f"Solar-only fallback: {fallback_count}\n\n"
    )

    file.write(
        "Primary exposure formula:\n"
    )

    file.write(
        "(solar_kw * 0.95 - model_load_kw) / kva\n\n"
    )

    file.write(
        "Scenario status counts:\n"
    )

    file.write(
        status_counts.to_string()
    )

    file.write("\n\n")

    file.write(
        "IMPORTANT:\n"
    )

    file.write(
        "The exposure score is a screening indicator "
        "based on CEB modelled load and estimated PV output. "
        "It is not confirmed measured reverse power flow.\n"
    )


# ---------------------------------------------------------
# CONSOLE OUTPUT
# ---------------------------------------------------------

print("\nC3 risk scoring completed.")

print(
    "Total transformers:",
    len(df)
)

print(
    "Load-adjusted:",
    primary_count
)

print(
    "Fallback:",
    fallback_count
)

print("\nScenario status:")

print(
    status_counts.to_string()
)

print(
    f"\nOutput saved to:\n{OUTPUT_FILE}"
)