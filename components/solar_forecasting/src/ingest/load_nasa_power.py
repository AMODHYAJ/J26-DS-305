"""
NASA POWER Weather & Irradiance Data Ingestion Script
Target Region: Embilipitiya (6.33°N, 80.85°E)
"""

import os
import numpy as np
import pandas as pd

def ingest_nasa_power(raw_file_path, output_dir='data/processed'):
    print(f"Loading raw NASA POWER file: {raw_file_path}")

    # Read CSV, skipping the 17 header metadata rows
    df = pd.read_csv(raw_file_path, skiprows=17)
    df.columns = df.columns.str.strip()

    # Replace NASA POWER missing data flag (-999) with NaN
    df_clean = df.replace(-999, np.nan)

    # Construct a proper UTC datetime index
    df_clean['datetime'] = pd.to_datetime(
        df_clean[['YEAR', 'MO', 'DY', 'HR']].rename(
            columns={'YEAR': 'year', 'MO': 'month', 'DY': 'day', 'HR': 'hour'}
        )
    )
    df_clean.set_index('datetime', inplace=True)

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Save as processed CSV (or Parquet)
    output_path = os.path.join(output_dir, 'nasa_power_embilipitiya_hourly.csv')
    df_clean.to_csv(output_path)

    print(f"Ingestion complete! Cleaned data saved to: {output_path}")
    print(f"Total records processed: {len(df_clean)}")
    print("\nDataFrame Preview:")
    print(df_clean[['ALLSKY_SFC_SW_DWN', 'CLRSKY_SFC_SW_DWN', 'T2M', 'RH2M']].head())

if __name__ == "__main__":
    raw_path = 'data/raw/POWER_Point_Hourly_20251001_20261016_006d33N_080d85E_UTC.csv'
    ingest_nasa_power(raw_path)