"""
Refined Telemetry Cleaning: Night-Masking (pvlib) & NCRE Curtailment Integration.
Location: src/features/clean_telemetry.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
import pvlib

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DATA_PATH = BASE_DIR / "data" / "raw" / "ceb_embilipitiya_plants_15min.csv"
PLANTS_PATH = BASE_DIR / "configs" / "plants.csv"
CURTAILMENT_DIR = Path(r"C:\Users\USER\Downloads\CEB_data")
PROCESSED_DIR = BASE_DIR / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def parse_ncre_curtailment_logs():
    curtailment_periods = []

    for folder_name in ["NCRE Control - 1", "NCRE Control - 2", "NCRE Control - 3"]:
        folder_path = CURTAILMENT_DIR / folder_name
        if not folder_path.exists():
            continue

        files = list(folder_path.glob("*.xlsx")) + list(folder_path.glob("*.csv"))
        for file_path in files:
            try:
                if file_path.suffix == '.xlsx':
                    xls = pd.ExcelFile(file_path)
                    if '2026.10.19 - Final' in xls.sheet_names:
                        df_final = pd.read_excel(xls, sheet_name='2026.10.19 - Final')
                        for col in df_final.columns:
                            if "Completely curtailed" in str(col):
                                sub_df = df_final[['MHP Name', col]].dropna()
                                for _, row in sub_df.iterrows():
                                    curtailment_periods.append({
                                        'plant_name': str(row['MHP Name']).strip(),
                                        'curtailment_info': str(row[col]),
                                        'source_file': file_path.name
                                    })
            except Exception:
                continue

    return pd.DataFrame(curtailment_periods)


def clean_and_mask_telemetry():
    print("=======================================================")
    print("Stage 1 (Refined): Telemetry Cleaning & Curtailment Integration")
    print("=======================================================")

    if not RAW_DATA_PATH.exists():
        raise FileNotFoundError(f"Telemetry data not found at {RAW_DATA_PATH}.")

    df_telemetry = pd.read_csv(RAW_DATA_PATH)
    df_plants = pd.read_csv(PLANTS_PATH)

    print(f"Loaded raw telemetry: {len(df_telemetry):,} rows")

    # 1. Parse NCRE Curtailment logs
    print("Parsing NCRE curtailment logs from control folders...")
    df_curtailment_logs = parse_ncre_curtailment_logs()
    print(f"Extracted {len(df_curtailment_logs):,} curtailment log entries.")

    # 2. Parse timestamps and compute solar elevation using pvlib
    df_telemetry['time'] = pd.to_datetime(df_telemetry['datetime_utc'])

    df_plants['ceb_sn_clean'] = df_plants['ceb_sn'].astype(str).str.split('.').str[0]
    df_telemetry['Account_clean'] = df_telemetry['Account Number'].astype(str).str.split('.').str[0]

    df_merged = pd.merge(
        df_telemetry,
        df_plants[['ceb_sn_clean', 'plant_id', 'plant_name', 'lat', 'lon', 'capacity_mw']],
        left_on='Account_clean',
        right_on='ceb_sn_clean',
        how='inner'
    )

    print("Calculating solar elevation angles using pvlib...")
    solar_positions = []
    for plant_id, group in df_merged.groupby('plant_id'):
        lat = group['lat'].iloc[0]
        lon = group['lon'].iloc[0]
        times = pd.DatetimeIndex(group['time'])

        solpos = pvlib.solarposition.get_solarposition(times, lat, lon)
        group['solar_elevation'] = solpos['apparent_elevation'].values
        solar_positions.append(group)

    df_merged = pd.concat(solar_positions).sort_values(['plant_id', 'time']).reset_index(drop=True)

    # 3. Apply Night Mask (Solar elevation > 0)
    df_merged['is_daylight'] = df_merged['solar_elevation'] > 0.0
    night_count = (~df_merged['is_daylight']).sum()
    daylight_count = df_merged['is_daylight'].sum()

    print(f"Night records masked (Solar Elevation <= 0): {night_count:,}")
    print(f"Daylight operational records retained: {daylight_count:,}")

    # 4. Refined Curtailment Masking (Midday near-zero drops where sun angle is steep > 30 deg)
    df_merged['power_kw'] = df_merged['generation_kw'].fillna(0)
    # Flag severe mid-day zero drops (solar elevation > 30 deg but generation == 0)
    potential_curtailment = (df_merged['solar_elevation'] > 30.0) & (df_merged['power_kw'] == 0.0)
    df_merged['is_curtailed'] = potential_curtailment

    print(f"Flagged {potential_curtailment.sum():,} mid-day curtailment/outage intervals.")

    # Retain daylight non-curtailed operational records
    df_final_clean = df_merged[df_merged['is_daylight'] & (~df_merged['is_curtailed'])].copy()

    cleaned_output_path = PROCESSED_DIR / "features_embilipitiya_plants_cleaned_15min.csv"

    try:
        df_final_clean.to_csv(cleaned_output_path, index=False)
        print(f"[Success] Saved cleaned dataset to {cleaned_output_path} ({len(df_final_clean):,} rows)")
    except PermissionError:
        alt_path = PROCESSED_DIR / "features_embilipitiya_plants_cleaned_15min_v2.csv"
        df_final_clean.to_csv(alt_path, index=False)
        print(f"[Notice] File was locked by another app. Saved clean dataset to: {alt_path}")


if __name__ == "__main__":
    clean_and_mask_telemetry()