"""
Model Validation & Actual vs. Predicted Visualization Module.
Location: src/models/validate_model.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "data" / "processed" / "features_embilipitiya_plants_15min.csv"
MODEL_PATH = BASE_DIR / "models" / "best_telemetry_model.pkl"
OUTPUT_DIR = BASE_DIR / "outputs" / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def validate_and_plot():
    print("=======================================================")
    print("Stage 4C: Model Validation & Actual vs Predicted Plot")
    print("=======================================================")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Run train_telemetry.py first.")
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Feature dataset not found at {DATA_PATH}.")

    model = joblib.load(MODEL_PATH)
    df = pd.read_csv(DATA_PATH)
    df['time'] = pd.to_datetime(df['time'])

    candidate_features = [
        'lat', 'lon', 'capacity_mw', 'direct_radiation', 'diffuse_radiation',
        'direct_normal_irradiance', 'shortwave_radiation', 'ghi', 'clear_sky_ghi_est',
        'kt', 'ramp_rate', 'hour', 'minute', 'month', 'dayofyear', 'temperature_2m'
    ]
    feature_cols = [col for col in candidate_features if col in df.columns]
    target_col = 'generation_kw'

    df_clean = df.dropna(subset=feature_cols + [target_col]).copy()
    X = df_clean[feature_cols]
    y_true = df_clean[target_col]

    # Generate predictions
    print("Running inference across validation samples...")
    y_pred = model.predict(X)
    df_clean['predicted_generation_kw'] = y_pred

    # Plot a sample time-series slice (e.g., first 5 days for the first plant)
    sample_plant = df_clean['plant_id'].iloc[0]
    df_plant = df_clean[df_clean['plant_id'] == sample_plant].sort_values('time').iloc[:480] # ~5 days at 15-min

    plt.figure(figsize=(12, 6))
    plt.plot(df_plant['time'], df_plant['generation_kw'], label='Actual Generation (kW)', color='blue', alpha=0.8)
    plt.plot(df_plant['time'], df_plant['predicted_generation_kw'], label='Model Forecast (kW)', color='orange', linestyle='--', alpha=0.9)
    plt.title(f"15-Minute Power Forecast vs Actual Telemetry - Plant: {sample_plant}", fontsize=12, fontweight='bold')
    plt.xlabel("Timestamp (UTC)", fontsize=10)
    plt.ylabel("Generation (kW)", fontsize=10)
    plt.legend(loc='upper right')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()

    plot_path = OUTPUT_DIR / "actual_vs_predicted_power.png"
    plt.savefig(plot_path, dpi=300)
    print(f"[Success] Saved validation plot to {plot_path}")
    plt.close()


if __name__ == "__main__":
    validate_and_plot()