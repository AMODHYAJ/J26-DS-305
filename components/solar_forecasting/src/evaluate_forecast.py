"""
Solar Forecast Evaluation Script (RMSE, MAE, Skill Score vs. Smart Persistence)
Location: src/evaluate_forecast.py
"""
import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error

def evaluate_solar_forecast(df: pd.DataFrame):
    """
    Evaluates forecasted clear-sky index (kt) against actual measured kt and smart persistence.
    """
    # Filter for daylight hours only
    daylight = df[(df['datetime'].dt.hour >= 6) & (df['datetime'].dt.hour <= 18)].copy()

    actual = daylight['actual_kt'].values
    predicted = daylight['forecast_kt'].values
    persistence = daylight['persistence_kt'].values

    # Calculate RMSE & MAE
    rmse_model = np.sqrt(mean_squared_error(actual, predicted))
    mae_model = mean_absolute_error(actual, predicted)

    rmse_persist = np.sqrt(mean_squared_error(actual, persistence))
    mae_persist = mean_absolute_error(actual, persistence)

    # Skill Score relative to Smart Persistence (%)
    skill_rmse = (1 - (rmse_model / rmse_persist)) * 100
    skill_mae = (1 - (mae_model / mae_persist)) * 100

    print("=== Solar Forecasting Evaluation Results ===")
    print(f"Model RMSE       : {rmse_model:.4f}")
    print(f"Persistence RMSE : {rmse_persist:.4f}")
    print(f"RMSE Skill Score : {skill_rmse:.2f}% improvement over persistence\n")

    print(f"Model MAE        : {mae_model:.4f}")
    print(f"Persistence MAE  : {mae_persist:.4f}")
    print(f"MAE Skill Score  : {skill_mae:.2f}% improvement over persistence\n")

    return {
        "rmse_model": rmse_model,
        "rmse_persist": rmse_persist,
        "skill_rmse": skill_rmse,
        "mae_model": mae_model,
        "mae_persist": mae_persist,
        "skill_mae": skill_mae
    }

if __name__ == "__main__":
    # Example usage with mock validation data
    np.random.seed(42)
    n = 1000
    dates = pd.date_range(start="2026-04-01", periods=n, freq="15min")

    mock_df = pd.DataFrame({
        'datetime': dates,
        'actual_kt': np.random.uniform(0.2, 1.0, n),
    })
    mock_df['persistence_kt'] = mock_df['actual_kt'] + np.random.normal(0, 0.15, n)
    mock_df['forecast_kt'] = mock_df['actual_kt'] + np.random.normal(0, 0.07, n)

    evaluate_solar_forecast(mock_df)