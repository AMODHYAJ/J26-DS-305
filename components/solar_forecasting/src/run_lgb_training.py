"""
Integrated Training Script for Embilipitiya GSS LightGBM Solar Forecasting Model (Plant-Grouped & Daylight Filtered)
Location: src/run_lgb_training.py
"""
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import mean_squared_error
from pathlib import Path
import joblib

def main():
    base_dir = Path(__file__).resolve().parents[1]
    data_path = base_dir / "data" / "processed" / "bess_simulation" / "bess_simulation_results_15min.csv"

    if not data_path.exists():
        print(f"[Error] Dataset not found at {data_path}")
        return

    print(f"Loading dataset from {data_path}...")
    df = pd.read_csv(data_path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values(['plant_id', 'datetime']).reset_index(drop=True)

    # Filter strictly for daylight hours (06:00 to 18:00) to avoid nighttime zero-inflation
    df = df[(df['datetime'].dt.hour >= 6) & (df['datetime'].dt.hour <= 18)].copy()

    print("Engineering features grouped by plant_id (lags, rolling stats, solar interactions)...")
    if 'kt' not in df.columns:
        df['kt'] = df['generation_kw'] / (df['capacity_mw'] * 1000 * 0.85 + 1e-5)
        df['kt'] = df['kt'].clip(0.0, 1.0)

    # Group by plant_id so lags and rolling stats do not cross plant boundaries
    df['kt_lag_1'] = df.groupby('plant_id')['kt'].shift(1)
    df['kt_lag_2'] = df.groupby('plant_id')['kt'].shift(2)
    df['kt_lag_4'] = df.groupby('plant_id')['kt'].shift(4)
    df['kt_lag_8'] = df.groupby('plant_id')['kt'].shift(8)

    df['kt_rolling_mean_4'] = df.groupby('plant_id')['kt'].rolling(window=4).mean().reset_index(0, drop=True)
    df['kt_rolling_std_4'] = df.groupby('plant_id')['kt'].rolling(window=4).std().reset_index(0, drop=True)
    df['kt_rolling_mean_12'] = df.groupby('plant_id')['kt'].rolling(window=12).mean().reset_index(0, drop=True)

    if 'cloud_cover' in df.columns and 'solar_elevation' in df.columns:
        df['cloud_solar_interaction'] = df['cloud_cover'] * np.sin(np.radians(df['solar_elevation'].clip(lower=0)))

    df = df.dropna().reset_index(drop=True)

    # Chronological Split
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    val_df = df.iloc[split_idx:]

    features = [
        'kt_lag_1', 'kt_lag_2', 'kt_lag_4', 'kt_lag_8',
        'kt_rolling_mean_4', 'kt_rolling_std_4', 'kt_rolling_mean_12',
        'cloud_cover', 'solar_elevation', 'cloud_solar_interaction',
        'wind_speed_10m', 'temperature_2m'
    ]
    active_features = [f for f in features if f in train_df.columns]

    X_train, y_train = train_df[active_features], train_df['kt']
    X_val, y_val = val_df[active_features], val_df['kt']

    print("Training optimized LightGBM regressor...")
    params = {
        'objective': 'regression',
        'metric': 'rmse',
        'boosting_type': 'gbdt',
        'n_estimators': 800,
        'learning_rate': 0.02,
        'num_leaves': 63,
        'max_depth': 8,
        'subsample': 0.75,
        'colsample_bytree': 0.75,
        'min_child_samples': 20,
        'reg_alpha': 0.1,
        'reg_lambda': 0.5,
        'random_state': 42,
        'n_jobs': -1,
        'verbose': -1
    }

    model = lgb.LGBMRegressor(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)]
    )

    # Evaluation during daylight
    preds = val_df['kt_lag_1'].values
    model_preds = model.predict(X_val)
    model_preds = np.clip(model_preds, 0.0, 1.0)
    actuals = y_val.values

    rmse_persist = np.sqrt(mean_squared_error(actuals, preds))
    rmse_model = np.sqrt(mean_squared_error(actuals, model_preds))
    skill_score = (1 - (rmse_model / rmse_persist)) * 100

    print("\n=== Tuned LightGBM Evaluation Results (Daylight Only) ===")
    print(f"Validation Samples : {len(val_df)}")
    print(f"Persistence RMSE   : {rmse_persist:.4f}")
    print(f"Tuned Model RMSE   : {rmse_model:.4f}")
    print(f"New Skill Score    : {skill_score:.2f}% improvement over persistence\n")

    models_dir = base_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / "best_solar_regressor.pkl"
    joblib.dump({'model': model, 'features': active_features}, model_path)
    print(f"[Success] Saved tuned model artifact to {model_path}")

if __name__ == "__main__":
    main()