"""
Simulation & Curve Verification for Operational Digital Twin.
Location: src/models/simulate_digital_twin.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "data" / "processed" /"features_embilipitiya_plants_15min.csv"
MODEL_PATH = BASE_DIR / "models" / "best_telemetry_model.pkl"


def run_simulation():
    print("=======================================================")
    print("Digital Twin Simulation & Curve Verification")
    print("=======================================================")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}.")

    model = joblib.load(MODEL_PATH)
    df = pd.read_csv(DATA_PATH)

    feature_cols = [
        'lat', 'lon', 'capacity_mw', 'cloud_cover', 'cloud_cover_low',
        'cloud_cover_mid', 'cloud_cover_high', 'shortwave_radiation_instant',
        'direct_normal_irradiance_instant', 'diffuse_radiation_instant',
        'temperature_2m', 'relative_humidity_2m', 'wind_speed_10m',
        'clear_sky_ghi_est', 'kt', 'hour', 'minute', 'month', 'dayofyear'
    ]

    available_features = [col for col in feature_cols if col in df.columns]
    df_eval = df.dropna(subset=available_features + ['generation_kw']).copy()

    X = df_eval[available_features]
    y_true = df_eval['generation_kw']

    # Run predictions directly from the trained model
    y_pred = model.predict(X)

    # Calculate overall metrics
    r2 = r2_score(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)

    print(f"\n--- Simulation Accuracy Metrics ---")
    print(f"  R² Score:  {r2:.4f}")
    print(f"  RMSE:      {rmse:.4f} kW")
    print(f"  MAE:       {mae:.4f} kW")

    # Inspect Plant P081 on sample date
    df_eval['prediction_kw'] = y_pred
    df_eval['datetime'] = pd.to_datetime(df_eval['datetime_utc'])
    df_eval['date'] = df_eval['datetime'].dt.date

    sample_plant = df_eval[df_eval['plant_id'] == 'P081']
    if not sample_plant.empty:
        sample_date = sample_plant['date'].iloc[100]
        day_df = sample_plant[sample_plant['date'] == sample_date]

        print(f"\n--- Sample Day Simulation (Plant: P081, Date: {sample_date}) ---")
        print(f"{'Time (UTC)':<20} | {'Actual (kW)':<12} | {'Predicted (kW)':<14}")
        print("-" * 52)
        for _, row in day_df.iloc[::2].iterrows():
            time_str = str(row['datetime'].time())
            print(f"{time_str:<20} | {row['generation_kw']:<12.2f} | {row['prediction_kw']:<14.2f}")


if __name__ == "__main__":
    run_simulation()