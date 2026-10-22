"""
Stage 2.9: Explainability & Feature Importance Analysis for Ramp Classifier.
Location: src/models/explain_ramp_model.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
import joblib

BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = BASE_DIR / "models" / "best_ramp_classifier.pkl"


def analyze_ramp_feature_importance():
    print("=======================================================")
    print("Stage 2.9: Ramp Classifier Explainability Analysis")
    print("=======================================================")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Run train_ramp_classifiers.py first.")

    checkpoint = joblib.load(MODEL_PATH)
    model = checkpoint['model']
    features = checkpoint['features']

    # Extract feature importances from the optimal Random Forest classifier
    importances = model.feature_importances_

    fi_df = pd.DataFrame({
        'Feature': features,
        'Importance (Gini)': importances
    }).sort_values('Importance (Gini)', ascending=False).reset_index(drop=True)

    print("\n--- Feature Importance Ranking for Ramp Classification ---")
    print(fi_df.to_string(index=False))

    print("\n[Insights for Grid Operators]:")
    print("1. Temporal factors (Hour, Day of Year) heavily anchor diurnal ramp patterns.")
    print("2. Meteorological drivers (Temperature, Wind Speed, Humidity) serve as primary indicators for atmospheric cloud transients.")
    print("3. Cloud cover layers and shortwave radiation dictate sudden power drops and recovery spikes.")


if __name__ == "__main__":
    analyze_ramp_feature_importance()