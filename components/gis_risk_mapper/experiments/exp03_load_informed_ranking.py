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
        / "exp03_load_informed_ranking"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


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

print("\nAvailable columns:")
print(df.columns.tolist())


# Supports either the new name or the older output name.
if "model_load_kw" in df.columns:
    LOAD_COL = "model_load_kw"

elif "load_kw" in df.columns:
    LOAD_COL = "load_kw"

else:
    raise ValueError(
        "No model load column found."
    )


required = [
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
    col
    for col in required
    if col not in df.columns
]

if missing:
    raise ValueError(
        f"Missing columns: {missing}"
    )


# ---------------------------------------------------------
# KEEP ONLY USABLE LOAD MATCHES
# ---------------------------------------------------------

matched = df[
    (df["load_matched"] == True)
    & (df[LOAD_COL].notna())
    & (df[LOAD_COL] > 0)
    ].copy()


# ---------------------------------------------------------
# INDICATORS
# ---------------------------------------------------------

matched["solar_only_indicator"] = (
    matched["solar_to_kva"]
)

matched["load_informed_indicator"] = (
        matched["solar_kw"]
        / matched[LOAD_COL]
)

matched["solar_minus_model_load_kw"] = (
        matched["solar_kw"]
        - matched[LOAD_COL]
)


# ---------------------------------------------------------
# RANKINGS
# Rank 1 = highest screening priority
# ---------------------------------------------------------

matched["solar_only_rank"] = (
    matched["solar_only_indicator"]
    .rank(
        method="min",
        ascending=False
    )
    .astype(int)
)

matched["load_informed_rank"] = (
    matched["load_informed_indicator"]
    .rank(
        method="min",
        ascending=False
    )
    .astype(int)
)


matched["rank_change"] = (
        matched["solar_only_rank"]
        - matched["load_informed_rank"]
)

matched["absolute_rank_change"] = (
    matched["rank_change"].abs()
)


# Positive rank_change:
# transformer becomes MORE important when load is included.
#
# Negative rank_change:
# transformer becomes LESS important when load is included.


# ---------------------------------------------------------
# RANK AGREEMENT
# ---------------------------------------------------------

# Spearman rank correlation without requiring scipy:
# Pearson correlation between the two rank vectors.
rank_correlation = (
    matched["solar_only_rank"]
    .corr(
        matched["load_informed_rank"]
    )
)


# ---------------------------------------------------------
# TOP-N OVERLAP
# ---------------------------------------------------------

def top_n_overlap(data, n):

    solar_top = set(
        data.nsmallest(
            n,
            "solar_only_rank"
        )["sin"]
    )

    load_top = set(
        data.nsmallest(
            n,
            "load_informed_rank"
        )["sin"]
    )

    overlap = (
            solar_top
            & load_top
    )

    return {
        "top_n": n,
        "overlap_count": len(overlap),
        "overlap_pct": round(
            len(overlap) / n * 100,
            2
        )
    }


top_overlap = pd.DataFrame([
    top_n_overlap(matched, 10),
    top_n_overlap(matched, 20),
    top_n_overlap(matched, 50)
])


# ---------------------------------------------------------
# LARGE RANK MOVEMENTS
# ---------------------------------------------------------

largest_changes = (
    matched.sort_values(
        "absolute_rank_change",
        ascending=False
    )
    .head(30)
    .copy()
)


# ---------------------------------------------------------
# TOP 20 BY EACH METHOD
# ---------------------------------------------------------

top20_solar = (
    matched.sort_values(
        "solar_only_rank"
    )
    .head(20)
    .copy()
)

top20_load = (
    matched.sort_values(
        "load_informed_rank"
    )
    .head(20)
    .copy()
)


# ---------------------------------------------------------
# CSC SUMMARY
# ---------------------------------------------------------

csc_summary = (
    matched.groupby("csc")
    .agg(
        transformers=("sin", "count"),

        mean_solar_to_kva=(
            "solar_only_indicator",
            "mean"
        ),

        mean_solar_to_load=(
            "load_informed_indicator",
            "mean"
        ),

        median_absolute_rank_change=(
            "absolute_rank_change",
            "median"
        )
    )
    .reset_index()
)


# ---------------------------------------------------------
# SAVE EVIDENCE
# ---------------------------------------------------------

output_columns = [
    "csc",
    "gss",
    "feeder",
    "section",
    "sin",
    "kva",
    "solar_kw",
    LOAD_COL,
    "solar_only_indicator",
    "load_informed_indicator",
    "solar_minus_model_load_kw",
    "solar_only_rank",
    "load_informed_rank",
    "rank_change",
    "absolute_rank_change"
]


matched[
    output_columns
].sort_values(
    "load_informed_rank"
).to_csv(
    OUTPUT_DIR
    / "transformer_rank_comparison.csv",
    index=False
)


largest_changes[
    output_columns
].to_csv(
    OUTPUT_DIR
    / "largest_rank_changes.csv",
    index=False
)


top20_solar[
    output_columns
].to_csv(
    OUTPUT_DIR
    / "top20_solar_only.csv",
    index=False
)


top20_load[
    output_columns
].to_csv(
    OUTPUT_DIR
    / "top20_load_informed.csv",
    index=False
)


top_overlap.to_csv(
    OUTPUT_DIR
    / "top_n_overlap.csv",
    index=False
)


csc_summary.to_csv(
    OUTPUT_DIR
    / "csc_summary.csv",
    index=False
)


# ---------------------------------------------------------
# METADATA
# ---------------------------------------------------------

metadata = {
    "experiment": (
        "EXP03 Load-Informed "
        "Transformer Ranking"
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

    "transformers_in_file": (
        len(df)
    ),

    "usable_load_matches": (
        len(matched)
    ),

    "solar_only_indicator": (
        "solar_kw / transformer_kva"
    ),

    "load_informed_indicator": (
        "solar_kw / modelled_load_kw"
    ),

    "purpose": (
        "Test whether including modelled "
        "local load materially changes "
        "transformer prioritisation compared "
        "with solar-to-transformer-rating alone."
    ),

    "limitation": (
        "The load values are network-model "
        "loads, not measured time-series demand. "
        "The experiment therefore compares "
        "screening indicators and does not "
        "measure actual reverse power flow."
    )
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

median_shift = (
    matched[
        "absolute_rank_change"
    ].median()
)

mean_shift = (
    matched[
        "absolute_rank_change"
    ].mean()
)

large_shift_25 = int(
    (
            matched[
                "absolute_rank_change"
            ] >= 25
    ).sum()
)

large_shift_50 = int(
    (
            matched[
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
        "EXPERIMENT 03 - LOAD-INFORMED RANKING\n"
    )

    file.write(
        "=" * 55 + "\n\n"
    )

    file.write(
        f"Transformers in input: {len(df)}\n"
    )

    file.write(
        f"Transformers with usable "
        f"modelled load: {len(matched)}\n\n"
    )

    file.write(
        "Rank correlation between "
        "solar-only and load-informed "
        f"methods: {rank_correlation:.4f}\n\n"
    )

    file.write(
        "Top-N overlap:\n"
    )

    file.write(
        top_overlap.to_string(
            index=False
        )
    )

    file.write("\n\n")

    file.write(
        f"Median absolute rank change: "
        f"{median_shift:.2f}\n"
    )

    file.write(
        f"Mean absolute rank change: "
        f"{mean_shift:.2f}\n"
    )

    file.write(
        f"Transformers moving >=25 positions: "
        f"{large_shift_25}\n"
    )

    file.write(
        f"Transformers moving >=50 positions: "
        f"{large_shift_50}\n\n"
    )

    file.write(
        "IMPORTANT:\n"
        "The modelled load is not measured "
        "historical demand. This experiment "
        "tests whether load information adds "
        "useful discrimination to the screening "
        "process; it does not establish actual "
        "reverse power flow.\n"
    )


print("\nEXP03 completed.")

print(
    "Usable load matches:",
    len(matched)
)

print(
    "Rank correlation:",
    round(
        rank_correlation,
        4
    )
)

print(
    f"Evidence saved to:\n{OUTPUT_DIR}"
)