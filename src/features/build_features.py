"""
Feature Engineering Pipeline for Solar Forecasting
Computes clear-sky index, lagged features, rolling variability, and time encodings.
"""

import os
import numpy as np
import pandas as pd

def build_features(input_path='data/raw/synthetic_plant_1min.csv',
                   output_path='data/processed/features_synthetic_1min.csv'):
    print("Loading synthetic plant data...")
    df = pd.read_csv(input_path, parse_dates=['datetime'], index_col='datetime')

    # 1. Normalize power by capacity
    df['normalized_power'] = df['power_kw'] / df['capacity_kw']

    # 2. Approximate clear-sky curve for synthetic data
    hour = (df.index.hour + df.index.minute / 60.0).to_numpy()
    clear_sky_curve = np.sin(np.pi * (hour - 6) / 12).clip(0, 1)
    df['clear_sky_power'] = clear_sky_curve * df['capacity_kw']

    # 3. Clear-sky index = measured power / clear-sky power (handles night division by zero)
    df['clear_sky_index'] = np.where(df['clear_sky_power'] > 10, df['power_kw'] / df['clear_sky_power'], 0.0)
    df['clear_sky_index'] = df['clear_sky_index'].clip(0, 1.5)  # clip extreme over-irradiance artifacts

    # 4. Create lagged clear-sky index features (t-1, t-5, t-15, t-30 minutes)
    for lag in [1, 5, 15, 30]:
        df[f'csi_lag_{lag}'] = df['clear_sky_index'].shift(lag)

    # 5. Rolling variability features (rolling standard deviation over 15 min and 60 min)
    df['csi_roll_std_15'] = df['clear_sky_index'].rolling(window=15).std()
    df['csi_roll_std_60'] = df['clear_sky_index'].rolling(window=60).std()

    # 6. Time of day encodings
    df['sin_time'] = np.sin(2 * np.pi * (df.index.hour * 60 + df.index.minute) / 1440)
    df['cos_time'] = np.cos(2 * np.pi * (df.index.hour * 60 + df.index.minute) / 1440)

    # 7. Day/night mask (sun up when clear_sky_power > 10 kW)
    df['is_daytime'] = df['clear_sky_power'] > 10

    # Drop initial NaNs created by rolling and lagging
    df_clean = df.dropna().copy()

    # Ensure output directory exists and save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_clean.to_csv(output_path)

    print(f"Feature engineering complete! Saved to {output_path}")
    print(f"Total processed records: {len(df_clean)}")
    print("\nFeature Preview:")
    print(df_clean[['power_kw', 'clear_sky_index', 'csi_lag_1', 'csi_roll_std_15', 'is_daytime']].head())

if __name__ == '__main__':
    build_features()