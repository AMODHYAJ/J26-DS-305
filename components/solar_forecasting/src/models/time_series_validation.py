"""
Time-Series Rolling Horizon Validation Script.
Location: src/models/time_series_validation.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "data" / "processed" /  "features_embilipitiya_plants_15min.csv"
MODEL_PATH = BASE_DIR / "models" / "best_telemetry_model.pkl"


def run_timeseries_validation():
    print("=======================================================")
    print("Stage 2: Time-Series Rolling Horizon Validation")
    print("=======================================================")

    if not MODEL_PATH.exists():
        raise FileNotFoundError("Trained model not found. Run train_telemetry.py first.")

    model = joblib.load(MODEL_PATH)
    df = pd.read_csv(DATA_PATH)
    df['datetime'] = pd.to_datetime(df['datetime_utc'])
    df = df.sort_values('datetime').reset_index(drop=True)

    feature_cols = [
        'lat', 'lon', 'capacity_mw', 'cloud_cover', 'cloud_cover_low',
        'cloud_cover_mid', 'cloud_cover_high', 'shortwave_radiation_instant',
        'direct_normal_irradiance_instant', 'diffuse_radiation_instant',
        'temperature_2m', 'relative_humidity_2m', 'wind_speed_10m',
        'clear_sky_ghi_est', 'kt', 'hour', 'minute', 'month', 'dayofyear'
    ]

    df_eval = df.dropna(subset=feature_cols + ['generation_kw']).copy()

    # Simulate a rolling 7-day test window
    test_window = df_eval.tail(672) # Last 7 days (672 intervals of 15 mins)
    X_test = test_window[feature_cols]
    y_true = test_window['generation_kw']

    y_pred = model.predict(X_test)

    r2 = r2_score(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)

    print(f"\n--- 7-Day Rolling Horizon Validation Metrics ---")
    print(f"  R² Score:  {r2:.4f}")
    print(f"  RMSE:      {rmse:.4f} kW")
    print(f"  MAE:       {mae:.4f} kW")


if __name__ == "__main__":
    run_timeseries_validation()