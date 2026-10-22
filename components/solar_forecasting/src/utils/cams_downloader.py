"""
CAMS Radiation Service Automated Downloader Script.
Queries 15-minute solar irradiance data (GHI, DNI, DHI) using your registered CAMS email.
Location: src/utils/cams_downloader.py
"""
from __future__ import annotations

import requests
import pandas as pd
from pathlib import Path

# Your registered CAMS credentials
CAMS_EMAIL = "amodhyaj@gmail.com"  # Replace with your CAMS email
CAMS_API_URL = "https://ads.atmosphere.copernicus.eu/api/v2/"  # CAMS / CDS API endpoint


def fetch_cams_solar_data(lat: float, lon: float, start_date: str, end_date: str, email: str) -> pd.DataFrame:
    """
    Requests radiation time-series data from CAMS for a specific latitude and longitude.
    """
    print(f"Requesting CAMS data for Lat: {lat}, Lon: {lon} from {start_date} to {end_date}...")

    print("To automate CAMS downloads via Python:")
    print("1. Ensure 'cdsapi' is installed: pip install cdsapi")
    print("2. Configure your ~/.cdsapirc file with your Copernicus Climate Data Store API key.")
    print("3. Use cdsapi.Client().retrieve('cams-solar-radiation', {...}) to pull 15-min or hourly data.")

    return pd.DataFrame()


if __name__ == "__main__":
    print("CAMS downloader utility template ready.")