"""
Transformer-Level Weather Ingestion Pipeline using Open-Meteo Archive API.
Fetches hourly solar radiation parameters for all 66 unique spatial nodes.
Location: src/ingest/fetch_transformer_weather.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parents[2]
MAPPING_PATH = BASE_DIR / "data" / "processed" / "transformer_spatial_mapping.csv"
OUTPUT_DIR = BASE_DIR / "data" / "processed" / "weather_cache"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_unique_transformer_coordinates() -> pd.DataFrame:
    """Loads spatial mapping and extracts unique coordinate pairs."""
    if not MAPPING_PATH.exists():
        raise FileNotFoundError(f"Spatial mapping file not found at {MAPPING_PATH}.")
    df_mapped = pd.read_csv(MAPPING_PATH)
    return df_mapped[['mapped_lat', 'mapped_lon', 'location_id', 'coord_source']].drop_duplicates().reset_index(drop=True)


def fetch_openmeteo_for_node(lat: float, lon: float, node_id: str) -> bool:
    """Queries Open-Meteo historical archive API for hourly solar radiation."""
    output_file = OUTPUT_DIR / f"openmeteo_{node_id}_{lat:.4f}_{lon:.4f}.csv"
    if output_file.exists():
        print(f"  [Cache Hit] Data already exists for ({lat:.4f}, {lon:.4f})")
        return True

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "hourly": "shortwave_radiation,direct_radiation,diffuse_radiation,direct_normal_irradiance",
        "timezone": "Asia/Colombo"
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if "hourly" in data:
                df = pd.DataFrame(data["hourly"])
                df.to_csv(output_file, index=False)
                print(f"  [Success] Saved weather cache to {output_file.name}")
                return True
        print(f"  [API Error] Status {response.status_code}: {response.text}")
        return False
    except Exception as e:
        print(f"  [Connection Error] {e}")
        return False


def fetch_weather_features():
    print("=======================================================")
    print("Stage 2: Transformer-Level Weather Ingestion (Open-Meteo)")
    print("=======================================================")

    unique_nodes = load_unique_transformer_coordinates()
    print(f"Loaded {len(unique_nodes):,} unique spatial nodes for ingestion.")

    for idx, row in unique_nodes.iterrows():
        lat, lon = row['mapped_lat'], row['mapped_lon']
        loc_id = row['location_id']
        print(f"\n[{idx+1}/{len(unique_nodes)}] Node {loc_id} | Lat: {lat:.4f}, Lon: {lon:.4f}")
        fetch_openmeteo_for_node(lat, lon, f"{loc_id}_{idx}")

    print("\nWeather feature ingestion cycle completed successfully.")


if __name__ == "__main__":
    fetch_weather_features()