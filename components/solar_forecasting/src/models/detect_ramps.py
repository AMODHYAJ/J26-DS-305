"""
Stage 2: Ramp Detection, Rate-of-Change Analysis, and Classification.
Location: src/models/detect_ramps.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
import joblib

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "data" / "processed" / "features_embilipitiya_plants_15min.csv"
MODEL_PATH = BASE_DIR / "models" / "best_telemetry_model.pkl"
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def detect_and_classify_ramps():
    print("=======================================================")
    print("Stage 2: Ramp Detection & Classification Module")
    print("=======================================================")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Run train_telemetry.py first.")

    model = joblib.load(MODEL_PATH)
    df = pd.read_csv(DATA_PATH)

    feature_cols = [
        'lat', 'lon', 'capacity_mw', 'cloud_cover', 'cloud_cover_low',
        'cloud_cover_mid', 'cloud_cover_high', 'shortwave_radiation_instant',
        'direct_normal_irradiance_instant', 'diffuse_radiation_instant',
        'temperature_2m', 'relative_humidity_2m', 'wind_speed_10m',
        'clear_sky_ghi_est', 'kt', 'hour', 'minute', 'month', 'dayofyear'
    ]

    # 1. Generate Digital Twin power predictions
    print("Generating digital twin power profiles for ramp analysis...")
    df['prediction_kw'] = model.predict(df[feature_cols])
    df['datetime'] = pd.to_datetime(df['datetime_utc'])

    # Sort chronologically per plant
    df = df.sort_values(['plant_id', 'datetime']).reset_index(drop=True)

    # 2. Calculate generation delta per 15-minute interval (Delta P / Delta t)
    df['delta_p_kw'] = df.groupby('plant_id')['prediction_kw'].diff()

    # 3. Classify ramps based on statistical thresholds (~95th percentile volatility)
    def classify_ramp(row):
        delta = row['delta_p_kw']
        if pd.isna(delta):
            return 'Stable'
        if delta >= 0.03:
            return 'Ramp-Up'
        elif delta <= -0.03:
            return 'Ramp-Down'
        else:
            return 'Stable'

    df['ramp_class'] = df.apply(classify_ramp, axis=1)

    # Print summary statistics
    print("\n--- Embilipitiya GSS Cluster Ramp Summary ---")
    counts = df['ramp_class'].value_counts()
    for category, count in counts.items():
        print(f"  {category:<12}: {count:,} intervals ({count / len(df) * 100:.1f}%)")

    # Save ramp-classified dataset for grid operator logging
    output_path = PROCESSED_DIR / "embilipitiya_ramps_classified_15min.csv"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"\n[Success] Ramp-classified dataset saved to {output_path}")


if __name__ == "__main__":
    detect_and_classify_ramps()