"""
Transformer-Level Spatial Mapping & Weather Feature Ingestion Pipeline.
Maps all 357 transformers across Embilipitiya, Godakawela, Kolonna, and Udawalawa
using direct GPS coordinates where available, and CSC centroid fallbacks for un-geocoded nodes.
Location: src/data/transformer_feature_pipeline.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[2]
# Updated paths based on your project folder structure
TRANSFORMERS_PATH = BASE_DIR / "data" / "processed" / "transformers_solar.csv"
CSC_PATH = BASE_DIR / "configs" / "csc_locations.csv"
OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_transformer_spatial_index() -> pd.DataFrame:
    print("=======================================================")
    print("Building Transformer-Level Spatial & Weather Index")
    print("=======================================================")

    if not TRANSFORMERS_PATH.exists():
        raise FileNotFoundError(f"Transformer file not found at: {TRANSFORMERS_PATH}")
    if not CSC_PATH.exists():
        raise FileNotFoundError(f"CSC locations file not found at: {CSC_PATH}")

    df_trans = pd.read_csv(TRANSFORMERS_PATH)
    df_csc = pd.read_csv(CSC_PATH).set_index('location_id')

    csc_mapping = {
        'Embilipitiya': 'emb',
        'Godakawela': 'god',
        'Kolonna': 'kol',
        'Udawalawa': 'uda'
    }

    assigned_records = []

    for idx, row in df_trans.iterrows():
        csc_name = row.get('csc', '')
        location_id = csc_mapping.get(csc_name, csc_name.lower()[:3])

        lat = row.get('lat')
        lon = row.get('lon')
        has_coord = bool(row.get('has_coord', False)) and pd.notnull(lat) and pd.notnull(lon)

        if not has_coord:
            if location_id in df_csc.index:
                lat = df_csc.loc[location_id, 'lat']
                lon = df_csc.loc[location_id, 'lon']
                coord_source = f"CSC_Fallback_{location_id}"
            else:
                coord_source = "Unknown"
        else:
            coord_source = "Direct_GPS"

        record = row.to_dict()
        record['mapped_lat'] = lat
        record['mapped_lon'] = lon
        record['coord_source'] = coord_source
        record['location_id'] = location_id
        assigned_records.append(record)

    df_mapped = pd.DataFrame(assigned_records)
    print(f"Successfully mapped {len(df_mapped):,} transformers.")
    print("Coordinate Source Breakdown:")
    print(df_mapped['coord_source'].value_counts())

    output_path = OUTPUT_DIR / "transformer_spatial_mapping.csv"
    df_mapped.to_csv(output_path, index=False)
    print(f"Saved transformer spatial mapping to: {output_path}")
    return df_mapped


if __name__ == "__main__":
    build_transformer_spatial_index()