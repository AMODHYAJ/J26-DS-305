"""
Multi-Model Training, Evaluation, and Selection Pipeline.
Trains 4 algorithms, compares metrics, and serializes the optimal model.
Location: src/models/train.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor

try:
    import lightgbm as lgb
except ImportError:
    lgb = None

try:
    import xgboost as xgb
except ImportError:
    xgb = None

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "data" / "processed" / "features_embilipitiya_solar.csv"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def load_dataset() -> pd.DataFrame:
    """Loads the engineered feature dataset."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Feature dataset not found at {DATA_PATH}. Run build_features.py first.")
    print("Loading engineered dataset (this may take a moment for 3.1M rows)...")
    df = pd.read_csv(DATA_PATH)
    return df


def prepare_features(df: pd.DataFrame):
    """Prepares features and target variable for modeling."""
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
        df['hour'] = df['time'].dt.hour
        df['month'] = df['time'].dt.month
        df['dayofyear'] = df['time'].dt.dayofyear
    else:
        df['hour'] = 12
        df['month'] = 6
        df['dayofyear'] = 180

    feature_cols = ['latitude', 'longitude', 'direct_radiation', 'diffuse_radiation',
                    'direct_normal_irradiance', 'clear_sky_ghi_est', 'kt', 'ramp_rate',
                    'hour', 'month', 'dayofyear']

    target_col = 'shortwave_radiation'

    df_clean = df.dropna(subset=feature_cols + [target_col])

    X = df_clean[feature_cols]
    y = df_clean[target_col]

    return train_test_split(X, y, test_size=0.2, random_state=42)


def train_and_evaluate_models():
    print("=======================================================")
    print("Stage 4: Multi-Model Training & Optimal Selection")
    print("=======================================================")

    df = load_dataset()
    X_train, X_test, y_train, y_test = prepare_features(df)

    print(f"Training set samples: {len(X_train):,}")
    print(f"Testing set samples: {len(X_test):,}")

    models = {
        "Random Forest": RandomForestRegressor(n_estimators=100, max_depth=15, random_state=42, n_jobs=-1),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=100, max_depth=6, random_state=42),
    }

    if lgb is not None:
        models["LightGBM"] = lgb.LGBMRegressor(n_estimators=100, learning_rate=0.05, random_state=42, n_jobs=-1)
    else:
        print("[Notice] LightGBM not installed. Skipping LightGBM.")

    if xgb is not None:
        models["XGBoost"] = xgb.XGBRegressor(n_estimators=100, learning_rate=0.05, max_depth=6, random_state=42, n_jobs=-1)
    else:
        print("[Notice] XGBoost not installed. Skipping XGBoost.")

    results = []
    trained_models = {}

    print("\nTraining models and evaluating performance...")
    for name, model in models.items():
        print(f"\n[Training] {name}...")
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        results.append({"Model": name, "RMSE": rmse, "MAE": mae, "R2": r2})
        trained_models[name] = model
        print(f"  {name} Results -> RMSE: {rmse:.4f} | MAE: {mae:.4f} | R2: {r2:.4f}")

    df_results = pd.DataFrame(results)
    print("\n=======================================================")
    print("Model Comparison Summary:")
    print("=======================================================")
    print(df_results.to_string(index=False))

    best_model_name = df_results.loc[df_results['RMSE'].idxmin()]['Model']
    best_model = trained_models[best_model_name]

    print(f"\n🏆 Optimal Model Selected: **{best_model_name}** (Lowest RMSE)")

    model_path = MODEL_DIR / "best_solar_model.pkl"
    joblib.dump(best_model, model_path)
    print(f"[Success] Serialized best model to {model_path}")


if __name__ == "__main__":
    train_and_evaluate_models()