"""
LightGBM Model Training Script for Solar Forecasting
Trains a gradient boosting model to predict the clear-sky index using lagged features.
"""

import os
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np

def train_solar_model(input_path='data/processed/features_synthetic_1min.csv'):
    print("Loading processed features...")
    df = pd.read_csv(input_path, parse_dates=['datetime'], index_col='datetime')

    # Filter for daytime records only
    df_day = df[df['is_daytime'] == True].copy()

    # Define features and target
    feature_cols = [
        'csi_lag_1', 'csi_lag_5', 'csi_lag_15', 'csi_lag_30',
        'csi_roll_std_15', 'csi_roll_std_60',
        'sin_time', 'cos_time'
    ]
    target_col = 'clear_sky_index'

    X = df_day[feature_cols]
    y = df_day[target_col]

    # Time-series train/test split (e.g., first 80% for training, last 20% for testing)
    split_idx = int(len(df_day) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    print(f"Training set size: {len(X_train)} rows")
    print(f"Testing set size: {len(X_test)} rows")

    # Initialize and train LightGBM Regressor
    print("Training LightGBM model...")
    model = lgb.LGBMRegressor(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=6,
        random_state=42
    )

    model.fit(X_train, y_train)

    # Predict and evaluate
    preds = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    mae = mean_absolute_error(y_test, preds)

    print("\n--- Model Evaluation Results ---")
    print(f"RMSE: {rmse:.4f}")
    print(f"MAE:  {mae:.4f}")

    # Save model feature importances preview
    importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print("\nFeature Importances:")
    print(importances)

if __name__ == '__main__':
    train_solar_model()