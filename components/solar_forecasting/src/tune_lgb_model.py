"""
Advanced LightGBM Hyperparameter Tuning & Feature Engineering for Solar Forecasting
Location: src/tune_lgb_model.py
"""
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import mean_squared_error, mean_absolute_error
import joblib

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adds multi-step lag features, rolling variance, and solar interaction terms."""
    df = df.sort_values('datetime').copy()

    # Target clear-sky index kt
    if 'kt' not in df.columns:
        df['kt'] = df['generation_kw'] / (df['capacity_mw'] * 1000 * 0.85 + 1e-5)
        df['kt'] = df['kt'].clip(0.0, 1.0)

    # Multi-step lag features (15min, 30min, 60min)
    df['kt_lag_1'] = df['kt'].shift(1)
    df['kt_lag_2'] = df['kt'].shift(2)
    df['kt_lag_4'] = df['kt'].shift(4)
    df['kt_lag_8'] = df['kt'].shift(8)

    # Rolling statistics (captures atmospheric stability vs volatility)
    df['kt_rolling_mean_4'] = df['kt'].rolling(window=4).mean()
    df['kt_rolling_std_4'] = df['kt'].rolling(window=4).std()
    df['kt_rolling_mean_12'] = df['kt'].rolling(window=12).mean()

    # Weather interaction terms
    if 'cloud_cover' in df.columns and 'solar_elevation' in df.columns:
        df['cloud_solar_interaction'] = df['cloud_cover'] * np.sin(np.radians(df['solar_elevation'].clip(lower=0)))

    return df.dropna()

def train_tuned_lightgbm(train_df: pd.DataFrame, val_df: pd.DataFrame):
    """Trains LightGBM with optimized hyperparameters for solar forecasting."""
    features = [
        'kt_lag_1', 'kt_lag_2', 'kt_lag_4', 'kt_lag_8',
        'kt_rolling_mean_4', 'kt_rolling_std_4', 'kt_rolling_mean_12',
        'cloud_cover', 'solar_elevation', 'cloud_solar_interaction',
        'wind_speed_10m', 'temperature_2m'
    ]

    # Filter available features
    active_features = [f for f in features if f in train_df.columns]

    X_train, y_train = train_df[active_features], train_df['kt']
    X_val, y_val = val_df[active_features], val_df['kt']

    # Optimized hyperparameters designed to push skill score toward 70%
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

    # Train with early stopping
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)]
    )

    # Predict on validation set
    preds = val_df['kt_lag_1'].values # Smart persistence baseline
    model_preds = model.predict(X_val)
    model_preds = np.clip(model_preds, 0.0, 1.0)

    actuals = y_val.values

    rmse_persist = np.sqrt(mean_squared_error(actuals, preds))
    rmse_model = np.sqrt(mean_squared_error(actuals, model_preds))
    skill_score = (1 - (rmse_model / rmse_persist)) * 100

    print("=== Optimized LightGBM Results ===")
    print(f"Persistence RMSE : {rmse_persist:.4f}")
    print(f"Tuned Model RMSE : {rmse_model:.4f}")
    print(f"New Skill Score  : {skill_score:.2f}% improvement over persistence\n")

    return model

if __name__ == "__main__":
    print("Run this script in your local environment with your processed parquet/CSV data loaded.")