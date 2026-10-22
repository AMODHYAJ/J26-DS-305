"""
Stage 1: Model Training and Evaluation with Full Weather Feature Integration.
Location: src/models/train_telemetry.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import joblib

BASE_DIR = Path(__file__).resolve().parents[2]
# Adjust this path to wherever your full weather-inclusive dataset is located (e.g., data/processed/ or root)
DATA_PATH = BASE_DIR / "data" / "processed" / "features_embilipitiya_plants_15min.csv"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "best_telemetry_model.pkl"


def train_telemetry_model():
    print("=======================================================")
    print("Stage 1: Training Operational Digital Twin Model (Weather-Inclusive)")
    print("=======================================================")

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}.")

    df = pd.read_csv(DATA_PATH)
    print(f"Loaded dataset: {len(df):,} rows")

    # Comprehensive weather & plant feature set
    candidate_features = [
        'lat', 'lon', 'capacity_mw', 'cloud_cover', 'cloud_cover_low',
        'cloud_cover_mid', 'cloud_cover_high', 'shortwave_radiation_instant',
        'direct_normal_irradiance_instant', 'diffuse_radiation_instant',
        'temperature_2m', 'relative_humidity_2m', 'wind_speed_10m',
        'clear_sky_ghi_est', 'kt', 'hour', 'minute', 'month', 'dayofyear'
    ]

    feature_cols = [col for col in candidate_features if col in df.columns]
    target_col = 'generation_kw'

    df_model = df.dropna(subset=feature_cols + [target_col]).copy()
    print(f"Training samples after feature alignment: {len(df_model):,}")

    X = df_model[feature_cols]
    y = df_model[target_col]

    # Train-test split (80% train, 20% test)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print(f"Training set: {len(X_train):,} rows | Test set: {len(X_test):,} rows")

    # Train Random Forest Digital Twin Regressor
    print("Training Random Forest Regressor...")
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=20,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)

    # Evaluate performance
    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)

    print("\n--- Digital Twin Validation Metrics ---")
    print(f"  R² Score:  {r2:.4f}")
    print(f"  RMSE:      {rmse:.4f} kW")
    print(f"  MAE:       {mae:.4f} kW")

    # Save trained model artifact
    joblib.dump(model, MODEL_PATH)
    print(f"\n[Success] Digital Twin model successfully saved to {MODEL_PATH}")


if __name__ == "__main__":
    train_telemetry_model()