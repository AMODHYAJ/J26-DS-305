"""
Clear-Sky Pipeline using pvlib
Computes theoretical clear-sky GHI and solar position for Embilipitiya coordinates.
"""

import pandas as pd
import pvlib
from pvlib.location import Location

def compute_clear_sky(input_csv='data/processed/nasa_power_embilipitiya_hourly.csv',
                      lat=6.3257, lon=80.8474, altitude=316.87, tz='UTC'):
    print("Loading processed NASA POWER data...")
    df = pd.read_csv(input_csv, parse_dates=['datetime'], index_col='datetime')

    # Define location using Embilipitiya coordinates
    loc = Location(lat, lon, tz=tz, altitude=altitude, name="Embilipitiya")

    print("Calculating solar position and pvlib clear-sky GHI (Ineichen model)...")
    # Get solar position (zenith, azimuth, elevation)
    solpos = loc.get_solarposition(df.index)

    # Get clear-sky irradiance components using the Ineichen model
    clearsky = loc.get_clearsky(df.index, model='ineichen')

    # Combine into a features dataframe
    df['solar_elevation'] = solpos['apparent_elevation'].values
    df['pvlib_clearsky_ghi'] = clearsky['ghi'].values

    # Create day/night mask (Sun elevation > 0 degrees)
    df['is_daytime'] = df['solar_elevation'] > 0

    # Save updated dataset
    output_path = 'data/processed/nasa_power_with_clearsky.csv'
    df.to_csv(output_path)
    print(f"Clear-sky pipeline complete! Saved to {output_path}")
    print(df[['solar_elevation', 'pvlib_clearsky_ghi', 'is_daytime']].head(10))

if __name__ == '__main__':
    compute_clear_sky()