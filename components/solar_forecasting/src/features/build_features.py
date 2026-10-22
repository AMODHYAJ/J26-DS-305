"""
Transformer-Level Feature Engineering Pipeline.
Merges transformer spatial mapping with cached Open-Meteo weather data,
computes Clear-Sky Index (Kt), and prepares the modeling dataset.
Location: src/features/build_features.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[2]
MAPPING_PATH = BASE_DIR / "data" / "processed" / "transformer_spatial_mapping.csv"
WEATHER_CACHE_DIR = BASE_DIR / "data" / "processed" / "weather_cache"
OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_spatial_mapping() -> pd.DataFrame:
    """Loads the transformer spatial mapping table."""
    if not MAPPING_PATH.exists():
        raise FileNotFoundError(f"Spatial mapping not found at {MAPPING_PATH}.")
    return pd.read_csv(MAPPING_PATH)


def compute_clear_sky_index(df_weather: pd.DataFrame) -> pd.DataFrame:
    """
    Computes Clear-Sky Index (Kt) and solar geometry features.
    """
    ghi = df_weather.get('shortwave_radiation', pd.Series(0, index=df_weather.index))

    # Simple clear-sky envelope approximation using rolling 90th percentile over 168 hours (7 days)
    rolling_max = ghi.rolling(window=168, min_periods=24, center=True).max().bfill().ffill()
    rolling_max = np.where(rolling_max < 1.0, 1.0, rolling_max)

    df_weather['clear_sky_ghi_est'] = rolling_max
    df_weather['kt'] = np.clip(ghi / rolling_max, 0.0, 1.5)

    # Ramp detection features (hourly differences)
    df_weather['ghi_diff_1h'] = ghi.diff(1).fillna(0)
    df_weather['ramp_rate'] = df_weather['ghi_diff_1h'].abs()

    return df_weather


def build_features():
    print("=======================================================")
    print("Stage 3: Feature Engineering & Weather-Telemetry Merge")
    print("=======================================================")

    df_mapping = load_spatial_mapping()
    print(f"Loaded spatial mapping for {len(df_mapping):,} transformers.")

    if not WEATHER_CACHE_DIR.exists():
        raise FileNotFoundError(f"Weather cache directory not found at {WEATHER_CACHE_DIR}.")

    processed_transformers = []

    for _, row in df_mapping.iterrows():
        transformer_id = row.get('transformer_id', row.get('location_id', 'unknown'))
        lat, lon = row['mapped_lat'], row['mapped_lon']
        loc_id = row['location_id']

        # Find matching cached weather file
        match_files = list(WEATHER_CACHE_DIR.glob(f"openmeteo_{loc_id}_*_{lat:.4f}_{lon:.4f}.csv"))
        if not match_files:
            match_files = list(WEATHER_CACHE_DIR.glob(f"openmeteo_*_{lat:.4f}_{lon:.4f}.csv"))

        if match_files:
            weather_file = match_files[0]
            df_w = pd.read_csv(weather_file)
            df_w = compute_clear_sky_index(df_w)

            df_w['transformer_id'] = transformer_id
            df_w['location_id'] = loc_id
            df_w['latitude'] = lat
            df_w['longitude'] = lon

            processed_transformers.append(df_w)

    if processed_transformers:
        df_features = pd.concat(processed_transformers, ignore_index=True)
        output_path = OUTPUT_DIR / "features_embilipitiya_solar.csv"
        df_features.to_csv(output_path, index=False)
        print(f"\n[Success] Feature engineering complete! Saved dataset to {output_path}")
        print(f"Total feature rows generated: {len(df_features):,}")
    else:
        print("[Error] No weather caches matched the spatial mapping nodes.")


if __name__ == "__main__":
    build_features()