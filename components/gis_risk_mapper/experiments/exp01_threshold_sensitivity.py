from pathlib import Path
from datetime import datetime
import hashlib
import json

import pandas as pd
import matplotlib.pyplot as plt


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

EXPERIMENT_DIR = Path(__file__).resolve().parent
C3_DIR = EXPERIMENT_DIR.parent

INPUT_FILE = C3_DIR / "output" / "solar_by_transformer.csv"

OUTPUT_DIR = (
    EXPERIMENT_DIR
    / "evidence"
    / "exp01_threshold_sensitivity"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SIN_COL = "sin"
SOLAR_COL = "solar_kw"
KVA_COL = "kva"


# ---------------------------------------------------------
# EXPERIMENT SETTINGS
# ---------------------------------------------------------

# Original labelling rule
BASELINE_LOW = 0.50
BASELINE_HIGH = 1.00

# Thresholds to test
LOW_THRESHOLDS = [0.30, 0.40, 0.50, 0.60]
HIGH_THRESHOLDS = [0.80, 1.00, 1.20, 1.50]


def label_ratio(ratio, low_threshold, high_threshold):
    """Assign Low / Medium / High using only solar-to-kVA ratio."""

    if ratio < low_threshold:
        return "Low"
    elif ratio < high_threshold:
        return "Medium"
    else:
        return "High"


def file_sha256(path):
    """Create a hash so we know exactly which input file produced the results."""

    sha = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            sha.update(chunk)

    return sha.hexdigest()


# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

df = pd.read_csv(INPUT_FILE)

print("\nAvailable columns:")
print(df.columns.tolist())


required_columns = [SIN_COL, SOLAR_COL, KVA_COL]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise ValueError(
        f"\nMissing columns: {missing_columns}\n"
        f"Available columns are: {df.columns.tolist()}\n\n"
        "Update SIN_COL, SOLAR_COL and KVA_COL at the top of this file."
    )


# Remove invalid transformer records
df = df.dropna(
    subset=[SIN_COL, SOLAR_COL, KVA_COL]
).copy()

df = df[df[KVA_COL] > 0].copy()


# ---------------------------------------------------------
# CALCULATE SOLAR PENETRATION RATIO
# ---------------------------------------------------------

df["solar_to_kva_ratio"] = df["solar_to_kva"]


# ---------------------------------------------------------
# BASELINE LABELS
# ---------------------------------------------------------

df["baseline_label"] = df["solar_to_kva_ratio"].apply(
    lambda x: label_ratio(
        x,
        BASELINE_LOW,
        BASELINE_HIGH
    )
)


baseline_counts = (
    df["baseline_label"]
    .value_counts()
    .reindex(
        ["Low", "Medium", "High"],
        fill_value=0
    )
)

print("\nBaseline labels:")
print(baseline_counts)


# ---------------------------------------------------------
# RUN THRESHOLD EXPERIMENT
# ---------------------------------------------------------

summary_records = []

all_scenario_labels = pd.DataFrame({
    SIN_COL: df[SIN_COL],
    "solar_to_kva_ratio": df["solar_to_kva_ratio"],
    "baseline_label": df["baseline_label"]
})


scenario_number = 0

for low_threshold in LOW_THRESHOLDS:

    for high_threshold in HIGH_THRESHOLDS:

        if high_threshold <= low_threshold:
            continue

        scenario_number += 1

        scenario_name = (
            f"L{low_threshold:.2f}_H{high_threshold:.2f}"
        )

        scenario_labels = df["solar_to_kva_ratio"].apply(
            lambda x: label_ratio(
                x,
                low_threshold,
                high_threshold
            )
        )

        all_scenario_labels[scenario_name] = scenario_labels

        counts = (
            scenario_labels
            .value_counts()
            .reindex(
                ["Low", "Medium", "High"],
                fill_value=0
            )
        )

        changed = (
            scenario_labels
            != df["baseline_label"]
        )

        changed_count = int(changed.sum())

        changed_pct = (
            changed_count / len(df) * 100
        )

        summary_records.append({
            "scenario": scenario_name,
            "low_threshold": low_threshold,
            "high_threshold": high_threshold,
            "low_count": int(counts["Low"]),
            "medium_count": int(counts["Medium"]),
            "high_count": int(counts["High"]),
            "changed_from_baseline": changed_count,
            "changed_pct": round(changed_pct, 2)
        })


summary_df = pd.DataFrame(summary_records)


# ---------------------------------------------------------
# TRANSFORMER STABILITY
# ---------------------------------------------------------

scenario_columns = [
    column
    for column in all_scenario_labels.columns
    if column.startswith("L")
]


def calculate_stability(row):

    labels = row[scenario_columns]

    low_count = int((labels == "Low").sum())
    medium_count = int((labels == "Medium").sum())
    high_count = int((labels == "High").sum())

    counts = {
        "Low": low_count,
        "Medium": medium_count,
        "High": high_count
    }

    dominant_label = max(
        counts,
        key=counts.get
    )

    stability_pct = (
        counts[dominant_label]
        / len(scenario_columns)
        * 100
    )

    return pd.Series({
        "low_scenarios": low_count,
        "medium_scenarios": medium_count,
        "high_scenarios": high_count,
        "dominant_label": dominant_label,
        "stability_pct": round(stability_pct, 2)
    })


stability = all_scenario_labels.apply(
    calculate_stability,
    axis=1
)

stability_df = pd.concat(
    [
        all_scenario_labels[
            [
                SIN_COL,
                "solar_to_kva_ratio",
                "baseline_label"
            ]
        ],
        stability
    ],
    axis=1
)


# ---------------------------------------------------------
# TEST CURRENT SMALL-TRANSFORMER RULE
# ---------------------------------------------------------

df["label_with_small_transformer_rule"] = (
    df["baseline_label"]
)

small_transformer_condition = (
    (df[KVA_COL] <= 100)
    & (df["solar_to_kva_ratio"] >= 0.80)
)

df.loc[
    small_transformer_condition,
    "label_with_small_transformer_rule"
] = "High"


small_rule_changed = (
    df["label_with_small_transformer_rule"]
    != df["baseline_label"]
)

small_rule_summary = pd.DataFrame([{
    "transformers_total": len(df),
    "transformers_changed_by_rule": int(
        small_rule_changed.sum()
    ),
    "changed_pct": round(
        small_rule_changed.mean() * 100,
        2
    )
}])


small_rule_details = df.loc[
    small_rule_changed,
    [
        SIN_COL,
        KVA_COL,
        SOLAR_COL,
        "solar_to_kva_ratio",
        "baseline_label",
        "label_with_small_transformer_rule"
    ]
].copy()


# ---------------------------------------------------------
# SAVE RESULTS
# ---------------------------------------------------------

summary_df.to_csv(
    OUTPUT_DIR / "threshold_summary.csv",
    index=False
)

stability_df.to_csv(
    OUTPUT_DIR / "transformer_stability.csv",
    index=False
)

all_scenario_labels.to_csv(
    OUTPUT_DIR / "scenario_labels.csv",
    index=False
)

small_rule_summary.to_csv(
    OUTPUT_DIR / "small_transformer_rule_summary.csv",
    index=False
)

small_rule_details.to_csv(
    OUTPUT_DIR / "small_transformer_rule_changed_transformers.csv",
    index=False
)


# ---------------------------------------------------------
# PLOT 1 — LABEL COUNTS
# ---------------------------------------------------------

plot_df = summary_df.copy()

x_positions = range(len(plot_df))

plt.figure(figsize=(12, 6))

plt.plot(
    x_positions,
    plot_df["low_count"],
    marker="o",
    label="Low"
)

plt.plot(
    x_positions,
    plot_df["medium_count"],
    marker="o",
    label="Medium"
)

plt.plot(
    x_positions,
    plot_df["high_count"],
    marker="o",
    label="High"
)

plt.xticks(
    x_positions,
    plot_df["scenario"],
    rotation=90
)

plt.xlabel("Threshold scenario")
plt.ylabel("Number of transformers")
plt.title(
    "Risk Label Counts Under Different Ratio Thresholds"
)

plt.legend()
plt.tight_layout()

plt.savefig(
    OUTPUT_DIR / "label_counts_by_threshold.png",
    dpi=300
)

plt.close()


# ---------------------------------------------------------
# PLOT 2 — CHANGE FROM BASELINE
# ---------------------------------------------------------

plt.figure(figsize=(12, 6))

plt.bar(
    plot_df["scenario"],
    plot_df["changed_pct"]
)

plt.xticks(rotation=90)

plt.xlabel("Threshold scenario")
plt.ylabel(
    "Transformers changed from baseline (%)"
)

plt.title(
    "Sensitivity of Risk Labels to Threshold Selection"
)

plt.tight_layout()

plt.savefig(
    OUTPUT_DIR / "label_change_from_baseline.png",
    dpi=300
)

plt.close()


# ---------------------------------------------------------
# EXPERIMENT METADATA
# ---------------------------------------------------------

metadata = {
    "experiment": "EXP01 Threshold Sensitivity",
    "run_time": datetime.now().isoformat(),
    "input_file": str(INPUT_FILE),
    "input_sha256": file_sha256(INPUT_FILE),
    "transformer_count": len(df),

    "baseline": {
        "low_threshold": BASELINE_LOW,
        "high_threshold": BASELINE_HIGH
    },

    "tested_low_thresholds": LOW_THRESHOLDS,
    "tested_high_thresholds": HIGH_THRESHOLDS,

    "purpose": (
        "Evaluate how sensitive Low/Medium/High "
        "transformer classifications are to "
        "solar-to-kVA ratio threshold selection."
    )
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

most_stable = (
    stability_df["stability_pct"] == 100
).sum()

scenario_dependent = (
    stability_df["stability_pct"] < 75
).sum()

with open(
    OUTPUT_DIR / "experiment_summary.txt",
    "w",
    encoding="utf-8"
) as file:

    file.write(
        "EXPERIMENT 01 - THRESHOLD SENSITIVITY\n"
    )

    file.write("=" * 50 + "\n\n")

    file.write(
        f"Transformers analysed: {len(df)}\n"
    )

    file.write(
        f"Scenarios tested: {len(summary_df)}\n\n"
    )

    file.write(
        "Baseline thresholds:\n"
    )

    file.write(
        f"Low < {BASELINE_LOW}\n"
    )

    file.write(
        f"Medium {BASELINE_LOW} to < {BASELINE_HIGH}\n"
    )

    file.write(
        f"High >= {BASELINE_HIGH}\n\n"
    )

    file.write(
        "Baseline label counts:\n"
    )

    file.write(
        baseline_counts.to_string()
    )

    file.write("\n\n")

    file.write(
        f"Transformers classified identically "
        f"in every scenario: {most_stable}\n"
    )

    file.write(
        f"Strongly scenario-dependent transformers "
        f"(stability < 75%): {scenario_dependent}\n\n"
    )

    file.write(
        "Small-transformer escalation rule:\n"
    )

    file.write(
        small_rule_summary.to_string(
            index=False
        )
    )


print("\nExperiment completed.")

print(
    f"Evidence saved to:\n{OUTPUT_DIR}"
)