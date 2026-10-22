"""
Time-Series Split Validation Pipeline for 15-Minute Solar Power Forecasting.
Trains on past chronological data and tests on future unseen chronological periods.
Location: src/models/train_timeseries_split.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
import joblib

from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.ensemble import RandomForestRegressor

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "data" / "processed" / "features_embilipitiya_plants_15min.csv"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def run_time_series_validation():
    print("=======================================================")
    print("Stage 4D: Chronological Time-Series Split Validation")
    print("=======================================================")

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Processed feature dataset not found at {DATA_PATH}. Run train_telemetry.py first.")

    df = pd.read_csv(DATA_PATH)
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').reset_index(drop=True)

    candidate_features = [
        'lat', 'lon', 'capacity_mw', 'direct_radiation', 'diffuse_radiation',
        'direct_normal_irradiance', 'shortwave_radiation', 'ghi', 'clear_sky_ghi_est',
        'kt', 'ramp_rate', 'hour', 'minute', 'month', 'dayofyear', 'temperature_2m'
    ]
    feature_cols = [col for col in candidate_features if col in df.columns]
    target_col = 'generation_kw'

    df_clean = df.dropna(subset=feature_cols + [target_col])

    # Chronological Split: 70% past for training, 30% future for testing
    split_idx = int(len(df_clean) * 0.7)
    train_df = df_clean.iloc[:split_idx]
    test_df = df_clean.iloc[split_idx:]

    X_train = train_df[feature_cols]
    y_train = train_df[target_col]
    X_test = test_df[feature_cols]
    y_test = test_df[target_col]

    print(f"Training Timeline (Past): {train_df['time'].min()} to {train_df['time'].max()} ({len(train_df):,} samples)")
    print(f"Testing Timeline (Future): {test_df['time'].min()} to {test_df['time'].max()} ({len(test_df):,} samples)")

    print("\nTraining Random Forest on chronological past...")
    model = RandomForestRegressor(n_estimators=100, max_depth=15, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print("\n=======================================================")
    print("Time-Series Validation Performance (Future Unseen Data):")
    print("=======================================================")
    print(f"  RMSE: {rmse:.4f} kW")
    print(f"  MAE:  {mae:.4f} kW")
    print(f"  R2:   {r2:.4f}")

    model_path = MODEL_DIR / "best_ts_split_model.pkl"
    joblib.dump(model, model_path)
    print(f"\n[Success] Serialized time-series validated model to {model_path}")


if __name__ == "__main__":
    run_time_series_validation()