from pathlib import Path

import pandas as pd
from pyproj import Transformer


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

C3_DIR = Path(__file__).resolve().parent

INPUT_FILE = (
        C3_DIR
        / "output"
        / "transformer_risk_profile.csv"
)

OUTPUT_FILE = (
        C3_DIR
        / "output"
        / "transformer_risk_ui.csv"
)


# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

df = pd.read_csv(INPUT_FILE)


required_columns = [
    "csc",
    "gss",
    "feeder",
    "section",
    "sin",
    "kva",
    "solar_kw",
    "solar_to_kva",
    "model_load_kw",
    "assessment_method",
    "data_confidence",
    "exposure_score",
    "scenario_status",
    "priority_rank",
    "fallback_rank",
    "fallback_indicator",
    "assessment_explanation",
    "has_coord",
    "x_kandawala",
    "y_kandawala"
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


# ---------------------------------------------------------
# COORDINATE CONVERSION
# EPSG:5234 -> EPSG:4326
# ---------------------------------------------------------

transformer = Transformer.from_crs(
    5234,
    4326,
    always_xy=True
)


df["longitude"] = pd.NA
df["latitude"] = pd.NA


coord_mask = (
        df["has_coord"].fillna(False).astype(bool)
        & df["x_kandawala"].notna()
        & df["y_kandawala"].notna()
)


for index, row in df.loc[coord_mask].iterrows():

    longitude, latitude = transformer.transform(
        row["x_kandawala"],
        row["y_kandawala"]
    )

    df.at[index, "longitude"] = longitude
    df.at[index, "latitude"] = latitude


# ---------------------------------------------------------
# UI DISPLAY FIELDS
# ---------------------------------------------------------

df["display_rank"] = df["priority_rank"]

fallback_mask = (
        df["assessment_method"]
        == "Solar-only fallback"
)

df.loc[
    fallback_mask,
    "display_rank"
] = df.loc[
    fallback_mask,
    "fallback_rank"
]


df["ranking_type"] = "Primary load-adjusted ranking"

df.loc[
    fallback_mask,
    "ranking_type"
] = "Fallback solar-only ranking"


# ---------------------------------------------------------
# CLEAN COLUMN SET
# ---------------------------------------------------------

ui_columns = [
    "csc",
    "gss",
    "feeder",
    "section",
    "sin",

    "kva",
    "solar_kw",
    "solar_to_kva",
    "model_load_kw",

    "exposure_score",
    "priority_rank",

    "fallback_indicator",
    "fallback_rank",

    "display_rank",
    "ranking_type",

    "scenario_status",
    "assessment_method",
    "data_confidence",

    "has_coord",
    "x_kandawala",
    "y_kandawala",
    "latitude",
    "longitude",

    "assessment_explanation"
]


ui_df = df[ui_columns].copy()


# ---------------------------------------------------------
# SORT
# Primary assessed transformers first,
# then fallback transformers
# ---------------------------------------------------------

ui_df["_group"] = (
    ui_df["assessment_method"]
    .map({
        "Load-adjusted exposure": 0,
        "Solar-only fallback": 1
    })
)


ui_df = (
    ui_df.sort_values(
        [
            "_group",
            "display_rank",
            "sin"
        ],
        na_position="last"
    )
    .drop(columns="_group")
)


# ---------------------------------------------------------
# SAVE
# ---------------------------------------------------------

ui_df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ---------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------

coordinate_count = int(
    ui_df["latitude"].notna().sum()
)

primary_count = int(
    (
            ui_df["assessment_method"]
            == "Load-adjusted exposure"
    ).sum()
)

fallback_count = int(
    (
            ui_df["assessment_method"]
            == "Solar-only fallback"
    ).sum()
)


print("\nUI dataset prepared.")

print(
    "Total transformers:",
    len(ui_df)
)

print(
    "Primary load-adjusted:",
    primary_count
)

print(
    "Fallback solar-only:",
    fallback_count
)

print(
    "Transformers with coordinates:",
    coordinate_count
)

print(
    f"\nOutput saved to:\n{OUTPUT_FILE}"
)