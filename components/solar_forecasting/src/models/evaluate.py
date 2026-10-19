"""
Model Evaluation and Visualization Script
Plots actual vs predicted clear-sky index for the test set.
"""

import pandas as pd
import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np

def evaluate_and_plot(input_path='data/processed/features_synthetic_1min.csv'):
    print("Loading features for evaluation plot...")
    df = pd.read_csv(input_path, parse_dates=['datetime'], index_col='datetime')
    df_day = df[df['is_daytime'] == True].copy()

    feature_cols = [
        'csi_lag_1', 'csi_lag_5', 'csi_lag_15', 'csi_lag_30',
        'csi_roll_std_15', 'csi_roll_std_60',
        'sin_time', 'cos_time'
    ]
    target_col = 'clear_sky_index'

    X = df_day[feature_cols]
    y = df_day[target_col]

    split_idx = int(len(df_day) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    # Train model to get predictions
    model = lgb.LGBMRegressor(n_estimators=100, learning_rate=0.05, max_depth=6, random_state=42)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    # Plot a sample of 300 test points for clear visualization
    plt.figure(figsize=(12, 5))
    plt.plot(y_test.index[:300], y_test.values[:300], label='Actual Clear-Sky Index', color='blue', alpha=0.7)
    plt.plot(y_test.index[:300], preds[:300], label='Predicted Clear-Sky Index', color='orange', linestyle='--', alpha=0.9)
    plt.title('Solar Forecasting: Actual vs Predicted Clear-Sky Index (Synthetic Test Data)')
    plt.xlabel('Datetime')
    plt.ylabel('Clear-Sky Index')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    output_plot = 'data/processed/forecast_comparison.png'
    plt.savefig(output_plot)
    print(f"Evaluation plot saved successfully to {output_plot}")
    plt.show()

if __name__ == '__main__':
    evaluate_and_plot()