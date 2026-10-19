"""Export a local, synthetic-only C3 prediction snapshot for the React dashboard.

Uses real CEB transformer attributes and available transformer coordinates but
NO data from Loads.xlsx. Keep the resulting JSON private: it includes CEB
transformer IDs and locations.

Run from repo root:
    python components/gis_risk_mapper/predict_risk.py

After creating the Vite frontend, you can send JSON straight to its public dir:
    python components/gis_risk_mapper/predict_risk.py --output components/gis_risk_mapper/frontend/public/data/transformer_risk.json
"""

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from pyproj import Transformer


C3_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = C3_DIR / "output"
MODEL_PATH = C3_DIR / "models" / "rf_synthetic_export.joblib"


def require_columns(df, columns, name):
    missing = sorted(set(columns) - set(df.columns))
    if missing:
        raise ValueError(f"{name}: missing columns {missing}")


def require_unique_keys(df, keys, name):
    if df.duplicated(keys).any():
        examples = df.loc[df.duplicated(keys, keep=False), keys].head(5)
        raise ValueError(f"{name}: repeated transformer keys:\n{examples}")


def to_float(value):
    return None if pd.isna(value) else float(value)


def to_int(value):
    return None if pd.isna(value) else int(value)


def to_text(value):
    return None if pd.isna(value) else str(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR / "transformer_risk.json",
        help="Private output JSON path (do not commit or publicly deploy).",
    )
    args = parser.parse_args()

    source = pd.read_csv(OUTPUT_DIR / "solar_with_coords.csv")
    exposure = pd.read_csv(OUTPUT_DIR / "synthetic_exposure_summary.csv")
    days = pd.read_csv(OUTPUT_DIR / "synthetic_transformer_days.csv")
    bundle = joblib.load(MODEL_PATH)  # Only load trusted, locally trained .joblib files.

    model = bundle["model"]
    features = bundle["features"]
    if bundle.get("data_basis") != "SYNTHETIC":
        raise ValueError("Expected a model trained on the synthetic dataset.")
    if bundle.get("target") != "target_export_11_14":
        raise ValueError("Unexpected model target.")
    if any(str(feature).startswith("target_") for feature in features):
        raise ValueError("Target leakage: a target column is included as a feature.")

    keys = ["csc", "sin"]
    require_columns(
        source,
        keys + ["gss", "feeder", "section", "kva", "solar_kw", "has_coord", "x_kandawala", "y_kandawala"],
        "Real transformer inventory",
    )
    require_columns(
        exposure,
        keys + ["export_frequency", "peak_export_ratio", "exposure_score", "priority_rank", "tier", "data_basis"],
        "Synthetic exposure summary",
    )
    require_columns(
        days,
        keys + ["day_index", "date"] + features,
        "Synthetic transformer-day features",
    )

    require_unique_keys(source, keys, "Real transformer inventory")
    require_unique_keys(exposure, keys, "Synthetic exposure summary")
    if not exposure["data_basis"].eq("SYNTHETIC").all():
        raise ValueError("Exposure summary contains non-synthetic outputs.")

    # A dashboard snapshot for one simulated day, NOT an average prediction.
    last_day = days["day_index"].max()
    snapshot = days.loc[days["day_index"] == last_day].copy()
    require_unique_keys(snapshot, keys, "Latest synthetic day")
    if snapshot[features].isna().any().any():
        raise ValueError("Missing feature values on selected simulated day.")

    # Match the categorical encoding used during training.
    if "day_of_week" in features:
        snapshot["day_of_week"] = snapshot["day_of_week"].astype(str)

    classes = list(model.classes_)
    if 1 not in classes:
        raise ValueError(f"Expected positive class 1; found {classes}")
    positive_index = classes.index(1)

    snapshot["predicted_probability"] = model.predict_proba(snapshot[features])[:, positive_index]
    snapshot["predicted_event"] = model.predict(snapshot[features]).astype(int)
    snapshot = snapshot[keys + ["date", "predicted_probability", "predicted_event"]]

    merged = source.merge(
        exposure[keys + ["export_frequency", "peak_export_ratio", "exposure_score", "priority_rank", "tier"]],
        on=keys,
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if not merged["_merge"].eq("both").all():
        raise ValueError("Some transformers lack a synthetic exposure summary.")
    merged = merged.drop(columns="_merge")

    merged = merged.merge(
        snapshot,
        on=keys,
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if not merged["_merge"].eq("both").all():
        raise ValueError("Some transformers lack a latest-day ML prediction.")
    merged = merged.drop(columns="_merge")

    # Only transform actual Kandawala coordinates; never invent missing locations.
    merged["latitude"] = np.nan
    merged["longitude"] = np.nan
    has_coord = merged["has_coord"].astype(str).str.lower().eq("true")
    coord_ok = has_coord & merged["x_kandawala"].notna() & merged["y_kandawala"].notna()
    transformer = Transformer.from_crs("EPSG:5234", "EPSG:4326", always_xy=True)
    if coord_ok.any():
        longitude, latitude = transformer.transform(
            merged.loc[coord_ok, "x_kandawala"].to_numpy(dtype=float),
            merged.loc[coord_ok, "y_kandawala"].to_numpy(dtype=float),
        )
        if not (np.isfinite(latitude).all() and np.isfinite(longitude).all()):
            raise ValueError("Coordinate conversion returned invalid results.")
        merged.loc[coord_ok, "latitude"] = latitude
        merged.loc[coord_ok, "longitude"] = longitude

    merged = merged.sort_values(["priority_rank", "csc", "sin"], na_position="last")
    records = []
    for row in merged.itertuples(index=False):
        # Tuple attributes for these safe, snake_case field names are predictable.
        records.append({
            "id": f"{row.csc}::{row.sin}",
            "sin": row.sin,
            "csc": row.csc,
            "gss": to_text(row.gss),
            "feeder": to_text(row.feeder),
            "section": to_text(row.section),
            "kva": to_float(row.kva),
            "solar_kw": to_float(row.solar_kw),
            "solar_to_kva": to_float(row.solar_to_kva),
            "latitude": to_float(row.latitude),
            "longitude": to_float(row.longitude),
            "has_coordinates": bool(pd.notna(row.latitude) and pd.notna(row.longitude)),
            "synthetic_summary": {
                "exposure_score": to_float(row.exposure_score),
                "priority_rank": to_int(row.priority_rank),
                "tier": to_text(row.tier),
                "export_frequency": to_float(row.export_frequency),
                "peak_export_ratio": to_float(row.peak_export_ratio),
            },
            "synthetic_day_prediction": {
                "date": to_text(row.date),
                "predicted_export_event": to_int(row.predicted_event),
                "predicted_export_probability": round(float(row.predicted_probability), 4),
            },
        })

    dates = snapshot["date"].dropna().unique().tolist()
    if len(dates) != 1:
        raise ValueError(f"Snapshot should contain one simulated date; got {dates}")

    payload = {
        "metadata": {
            "schema_version": 1,
            "data_basis": "REAL_CEB_ATTRIBUTES_PLUS_SYNTHETIC_OPERATING_SCENARIOS",
            "simulated_day_index": int(last_day),
            "simulated_date": str(dates[0]),
            "model": "Random Forest",
            "prediction_target": "Any simulated net-export event between 11:00 and 14:00",
            "feature_cutoff": "10:00 (plus preceding simulated days)",
            "transformer_count": len(records),
            "mapped_count": sum(r["has_coordinates"] for r in records),
            "warning": (
                "All exposure tiers and predictions derive from synthetic operating scenarios; "
                "they are not observed reverse-flow events or validated real-world risk probabilities. "
                "Real CEB transformer identifiers and locations remain confidential."
            ),
        },
        "transformers": records,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, allow_nan=False)

    print("Dashboard JSON prepared successfully.")
    print("Simulated day:", int(last_day), str(dates[0]))
    print("Transformers:", len(records))
    print("With map coordinates:", payload["metadata"]["mapped_count"])
    print("ML predictions:", sum(r["synthetic_day_prediction"]["predicted_export_event"] for r in records), "positive")
    print("Output:", args.output.resolve())


if __name__ == "__main__":
    main()
