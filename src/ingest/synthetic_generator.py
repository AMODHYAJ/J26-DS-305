"""
Synthetic Plant Dataset Generator
Generates minute-level mock solar generation data for testing the forecasting pipeline.
NOTE: For pipeline development and code testing only. Never use for final reporting.
"""

import os
import numpy as np
import pandas as pd

def generate_synthetic_plant(output_path='data/raw/synthetic_plant_1min.csv'):
    print("Generating 1-minute synthetic solar plant data...")

    # 1. Create 1-minute datetime index for 30 days
    date_rng = pd.date_range(start='2026-04-01 00:00:00', end='2026-05-01 00:00:00', freq='1min')
    df = pd.DataFrame(index=date_rng)
    df.index.name = 'datetime'

    # 2. Simulate clear-sky diurnal curve based on hour of day
    hour = (df.index.hour + df.index.minute / 60.0).to_numpy()
    # Bell curve peaking at solar noon (12:00)
    base_solar = np.sin(np.pi * (hour - 6) / 12).clip(0, 1) * 1000  # 1000 kW capacity peak

    # 3. Add random cloud attenuation (stochastic dropouts)
    np.random.seed(42)
    cloud_mask = np.random.beta(a=2, b=0.5, size=len(df))
    # Nighttime zero power
    cloud_mask[hour < 6] = 0
    cloud_mask[hour > 18] = 0

    df['power_kw'] = base_solar * cloud_mask
    df['capacity_kw'] = 1000.0

    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path)

    print(f"Synthetic plant data generated and saved to {output_path}")
    print(df.head(10))

if __name__ == '__main__':
    generate_synthetic_plant()