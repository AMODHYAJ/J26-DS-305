
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


# --------------------------------------------------
# PATHS
# --------------------------------------------------

C3_DIR = Path(__file__).resolve().parent
DATA_FILE = C3_DIR / "output" / "synthetic_transformer_days.csv"

MODEL_DIR = C3_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

MODEL_FILE = MODEL_DIR / "rf_synthetic_export.joblib"
REPORT_FILE = MODEL_DIR / "synthetic_model_report.txt"


# --------------------------------------------------
# LOAD AND VALIDATE
# --------------------------------------------------

df = pd.read_csv(DATA_FILE)

target = "target_export_11_14"

numeric_features = [
    "kva",
    "solar_kw",
    "solar_to_kva",
    "is_weekend",
    "morning_net_h06",
    "morning_net_h07",
    "morning_net_h08",
    "morning_net_h09",
    "morning_net_h10",
    "morning_net_mean",
    "morning_net_trend",
    "prev_day_export_event",
    "prev_day_peak_export_ratio",
    "prev3day_export_rate",
]

categorical_features = [
    "csc",
    "day_of_week",
]

features = numeric_features + categorical_features

required = features + [
    "sin",
    "day_index",
    target,
]

missing = set(required) - set(df.columns)
if missing:
    raise ValueError(f"Missing columns: {sorted(missing)}")

if df[required].isna().any().any():
    raise ValueError("Missing values in required ML fields.")

if not set(df[target].unique()).issubset({0, 1}):
    raise ValueError("Target must be binary.")

if df.duplicated(["csc", "sin", "day_index"]).any():
    raise ValueError("Duplicate transformer-day observations.")

df["day_of_week"] = df["day_of_week"].astype(str)

# Combined identifier prevents collisions across CSCs.
df["_transformer_id"] = (
        df["csc"].astype(str)
        + "::"
        + df["sin"].astype(str)
)


# --------------------------------------------------
# TRANSFORMER AND TIME SPLITS
# --------------------------------------------------

rng = np.random.default_rng(42)

transformer_ids = (
    df["_transformer_id"]
    .drop_duplicates()
    .astype(str)
    .to_numpy(dtype=str, copy=True)
)

rng.shuffle(transformer_ids)

n_holdout = max(1, int(len(transformer_ids) * 0.20))

heldout_ids = set(transformer_ids[:n_holdout])
training_ids = set(transformer_ids[n_holdout:])

days = sorted(df["day_index"].unique())

train_end = int(len(days) * 0.70)
val_end = int(len(days) * 0.85)

train_days = set(days[:train_end])
val_days = set(days[train_end:val_end])
test_days = set(days[val_end:])

train = df[
    df["_transformer_id"].isin(training_ids)
    & df["day_index"].isin(train_days)
    ].copy()

validation = df[
    df["_transformer_id"].isin(training_ids)
    & df["day_index"].isin(val_days)
    ].copy()

temporal_test = df[
    df["_transformer_id"].isin(training_ids)
    & df["day_index"].isin(test_days)
    ].copy()

unseen_test = df[
    df["_transformer_id"].isin(heldout_ids)
    & df["day_index"].isin(test_days)
    ].copy()


print("Training rows:", len(train))
print("Validation rows:", len(validation))
print("Future-day test rows:", len(temporal_test))
print("Unseen-transformer test rows:", len(unseen_test))

# Verify transformer groups are genuinely separated

train_ids = set(train["_transformer_id"])
unseen_ids = set(unseen_test["_transformer_id"])

assert train_ids.isdisjoint(unseen_ids), (
    "Transformer leakage detected!"
)

# Verify temporal separation

assert train["day_index"].max() < validation["day_index"].min()
assert validation["day_index"].max() < temporal_test["day_index"].min()

assert temporal_test["day_index"].min() == unseen_test["day_index"].min()

# Verify duplicate transformer-day records do not exist

for split in [train, validation, temporal_test, unseen_test]:
    assert not split.duplicated(
        ["_transformer_id", "day_index"]
    ).any()

print("Split integrity checks passed.")

print("\nTraining target positive:",
      f"{train[target].mean():.1%}")


# --------------------------------------------------
# RANDOM FOREST PIPELINE
# --------------------------------------------------

preprocessor = ColumnTransformer(
    transformers=[
        (
            "numeric",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
            ]),
            numeric_features,
        ),
        (
            "categorical",
            OneHotEncoder(handle_unknown="ignore"),
            categorical_features,
        ),
    ]
)

rf = Pipeline([
    ("preprocessor", preprocessor),
    (
        "classifier",
        RandomForestClassifier(
            n_estimators=250,
            min_samples_leaf=4,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        ),
    ),
])

rf.fit(train[features], train[target])


# --------------------------------------------------
# SOLAR-ONLY BASELINE
# --------------------------------------------------

solar_baseline = LogisticRegression(
    max_iter=1000
)

solar_baseline.fit(
    train[["solar_to_kva"]],
    train[target],
)


# --------------------------------------------------
# EVALUATION
# --------------------------------------------------

report_lines = []


def evaluate(name, dataset):
    y_true = dataset[target]

    rf_pred = rf.predict(dataset[features])
    rf_prob = rf.predict_proba(dataset[features])[:, 1]

    solar_pred = solar_baseline.predict(
        dataset[["solar_to_kva"]]
    )

    persistence_pred = (
        dataset["prev_day_export_event"].astype(int)
    )

    results = []

    for model_name, predicted in [
        ("Random Forest", rf_pred),
        ("Solar-only logistic baseline", solar_pred),
        ("Previous-day persistence", persistence_pred),
    ]:
        results.append(
            f"{model_name}: "
            f"Accuracy={accuracy_score(y_true, predicted):.3f}, "
            f"Precision={precision_score(y_true, predicted, zero_division=0):.3f}, "
            f"Recall={recall_score(y_true, predicted, zero_division=0):.3f}, "
            f"F1={f1_score(y_true, predicted, zero_division=0):.3f}"
        )

    if y_true.nunique() == 2:
        results.append(
            f"Random Forest ROC-AUC: "
            f"{roc_auc_score(y_true, rf_prob):.3f}"
        )

    results.append(
        f"RF confusion matrix [[TN, FP], [FN, TP]]:\n"
        f"{confusion_matrix(y_true, rf_pred, labels=[0, 1])}"
    )

    header = (
        f"\n{name}\n"
        f"Records: {len(dataset)}\n"
        f"Positive target rate: {y_true.mean():.1%}"
    )

    section = header + "\n" + "\n".join(results)

    print(section)
    report_lines.append(section)


evaluate("VALIDATION", validation)

evaluate("FUTURE-DAY TEST", temporal_test)

evaluate("UNSEEN-TRANSFORMER TEST", unseen_test)


# --------------------------------------------------
# SAVE MODEL AND REPORT
# --------------------------------------------------

joblib.dump(
    {
        "model": rf,
        "features": features,
        "target": target,
        "data_basis": "SYNTHETIC",
        "prediction_window": "11:00-14:00",
    },
    MODEL_FILE,
)

REPORT_FILE.write_text(
    "\n".join(report_lines),
    encoding="utf-8",
)

print("\nModel saved:", MODEL_FILE)
print("Report saved:", REPORT_FILE)
