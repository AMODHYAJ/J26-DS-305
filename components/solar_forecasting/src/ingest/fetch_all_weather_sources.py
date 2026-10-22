"""
Unified Recursive CEB Plant Data & Weather Ingestion Pipeline.
Filters strictly by verified Embilipitiya Account Numbers.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, Any, List
import requests
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

CEB_DATA_DIR = Path(r"C:\Users\USER\Downloads\CEB_data")


def load_csc_locations() -> pd.DataFrame:
    """Loads CSC master locations from csc_locations.csv."""
    path = BASE_DIR / "configs" / "csc_locations.csv"
    if not path.exists():
        path = Path("csc_locations.csv")
    if not path.exists():
        raise FileNotFoundError("Missing csc_locations.csv file.")
    return pd.read_csv(path)


def build_capacity_lookup(ceb_dir: Path) -> Dict[str, float]:
    """Builds an Account Number -> Capacity dictionary from the Oct 18 file."""
    capacity_map = {}
    oct_18_files = list(ceb_dir.rglob("*10_18_2026*.csv"))
    if not oct_18_files:
        oct_18_files = list(ceb_dir.rglob("*Capacity_Filled*.csv"))

    if oct_18_files:
        fpath = oct_18_files[0]
        print(f"Building master plant capacity lookup from: {fpath.name}")
        df_cap = pd.read_csv(fpath)
        if "Account Number" in df_cap.columns and "Plant Capacity" in df_cap.columns:
            for _, row in df_cap.iterrows():
                capacity_map[str(row["Account Number"])] = float(row["Plant Capacity"])

    # Manual capacity mapping for verified accounts
    capacity_map["9986400001"] = 5.0  # Parakumpura 5MW Solar Power Project

    print(f"Loaded capacities for {len(capacity_map)} plants into master lookup.")
    return capacity_map


def load_all_ceb_plant_generation(ceb_dir: Path = CEB_DATA_DIR) -> pd.DataFrame:
    """
    Recursively scans CEB CSV files and extracts ONLY the verified Embilipitiya plants
    based strictly on exact Account Numbers.
    """
    if not ceb_dir.exists():
        raise FileNotFoundError(f"CEB data directory not found: {ceb_dir}")

    capacity_map = build_capacity_lookup(ceb_dir)
    csv_files = list(ceb_dir.rglob("*.csv"))
    ncre_files = [f for f in csv_files if "ncre" in f.name.lower() or "generation" in f.name.lower()]
    if not ncre_files:
        ncre_files = csv_files

    print(f"Processing {len(ncre_files)} matching NCRE/generation files...")

    frames: List[pd.DataFrame] = []

    # Strict Verified Embilipitiya Account Numbers
    verified_accounts = {
        "6470900542",  # Laugfs Solar (1 MW)
        "6470900534",  # Irish & Eco Solar (1 MW)
        "6470900607",  # Dimo Solar / Thunkama (1 MW)
        "6470900828",  # Chandrikawewa Floating Solar (1 MW)
        "6470900836",  # Kiriibbanwewa Floating Solar (1 MW)
        "9986400001"   # Parakumpura 5MW Solar Power Project
    }

    for fpath in ncre_files:
        try:
            df_raw = pd.read_csv(fpath, low_memory=False)
            if "Plant Name" not in df_raw.columns or "Account Number" not in df_raw.columns:
                continue

            df_raw["str_acct"] = df_raw["Account Number"].astype(str)
            df_sub = df_raw[df_raw["str_acct"].isin(verified_accounts)].copy()

            if not df_sub.empty:
                if "Plant Capacity" not in df_sub.columns:
                    df_sub["Plant Capacity"] = df_sub["str_acct"].map(capacity_map).fillna(1.0)

                id_cols = [c for c in ["Account Number", "Plant Name", "Plant Capacity"] if c in df_sub.columns]
                time_cols = [c for c in df_sub.columns if c not in id_cols and c != "str_acct"]

                df_melted = df_sub.melt(
                    id_vars=id_cols,
                    value_vars=time_cols,
                    var_name="timestamp_str",
                    value_name="generation_kw"
                )
                frames.append(df_melted)
        except Exception as e:
            print(f"Warning: Could not process {fpath.name}: {e}")

    if not frames:
        raise ValueError("No matching Embilipitiya plant data found in scanned CSVs.")

    df_all = pd.concat(frames, ignore_index=True)
    df_all["datetime_utc"] = pd.to_datetime(df_all["timestamp_str"], errors="coerce", utc=True)
    df_all.dropna(subset=["datetime_utc"], inplace=True)
    df_all.sort_values(["Plant Name", "datetime_utc"], inplace=True)
    df_all.drop_duplicates(subset=["Account Number", "datetime_utc"], keep="last", inplace=True)

    out_csv = RAW_DIR / "ceb_embilipitiya_plants_15min.csv"
    df_all.to_csv(out_csv, index=False)
    print(f"Successfully aggregated verified Embilipitiya plants: {out_csv} ({len(df_all):,} records)")
    return df_all


def fetch_open_meteo(lat: float, lon: float, start: str = "2026-01-01", end: str = "2026-10-18") -> pd.DataFrame:
    """Fetches hourly weather from Open-Meteo Archive API matching CEB date range."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    vars_list = [
        "cloud_cover", "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high",
        "shortwave_radiation_instant", "direct_normal_irradiance_instant",
        "diffuse_radiation_instant", "temperature_2m", "relative_humidity_2m",
        "wind_speed_10m", "wind_direction_10m"
    ]
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(vars_list),
        "timezone": "UTC"
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    payload = r.json().get("hourly", {})
    df = pd.DataFrame(payload)
    df["datetime_utc"] = pd.to_datetime(df["time"], format="%Y-%m-%dT%H:%M", utc=True)
    df.drop(columns=["time"], inplace=True)
    df.set_index("datetime_utc", inplace=True)
    return df


def fetch_nasa_power(lat: float, lon: float, start_date: str = "20260101", end_date: str = "20261018") -> pd.DataFrame:
    """Fetches hourly weather from NASA POWER API matching CEB date range."""
    url = "https://power.larc.nasa.gov/api/temporal/hourly/point"
    parameters = [
        "ALLSKY_SFC_SW_DWN", "CLRSKY_SFC_SW_DWN",
        "T2M", "RH2M", "WS2M", "WD2M"
    ]
    params = {
        "parameters": ",".join(parameters),
        "community": "re",
        "longitude": lon,
        "latitude": lat,
        "start": start_date,
        "end": end_date,
        "format": "JSON"
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()

    properties = data.get("properties", {}).get("parameter", {})
    df = pd.DataFrame(properties)
    df.index = pd.to_datetime(df.index, format="%Y%m%d%H", utc=True)
    df.index.name = "datetime_utc"
    df = df.replace(-999.0, np.nan)
    return df


def main():
    print("=======================================================")
    print("Recursive Verified Embilipitiya Account-Only Pipeline")
    print("=======================================================")

    if CEB_DATA_DIR.exists():
        try:
            load_all_ceb_plant_generation(CEB_DATA_DIR)
        except Exception as e:
            print(f"Error during CEB plant data aggregation: {e}")
    else:
        print(f"Warning: Directory {CEB_DATA_DIR} not found.")

    csc_df = load_csc_locations()
    for _, row in csc_df.iterrows():
        loc_id = row["location_id"]
        lat = float(row["lat"])
        lon = float(row["lon"])

        print(f"\n--- Processing CSC: {loc_id.upper()} ({lat}, {lon}) ---")

        try:
            om_df = fetch_open_meteo(lat, lon, start="2026-01-01", end="2026-10-18")
            om_path = RAW_DIR / f"openmeteo_{loc_id}.csv"
            om_df.to_csv(om_path)
            print(f"  -> Saved Open-Meteo: {om_path.name} ({len(om_df)} records)")
            time.sleep(1.0)
        except Exception as e:
            print(f"  -> Open-Meteo Failed for {loc_id}: {e}")

        try:
            np_df = fetch_nasa_power(lat, lon, start_date="20260101", end_date="20261018")
            np_path = RAW_DIR / f"nasa_power_{loc_id}.csv"
            np_df.to_csv(np_path)
            print(f"  -> Saved NASA POWER: {np_path.name} ({len(np_df)} records)")
            time.sleep(1.0)
        except Exception as e:
            print(f"  -> NASA POWER Failed for {loc_id}: {e}")

    print("\nPipeline execution complete!")


if __name__ == "__main__":
    main()