"""
Stage 2.9: SHAP Explainability Analysis for Ramp Classifier.
Location: src/models/shap_explain_ramp.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
import joblib
import shap
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "data" / "processed" / "embilipitiya_ramps_classified_15min.csv"
MODEL_PATH = BASE_DIR / "models" / "best_ramp_classifier.pkl"
OUTPUT_DIR = BASE_DIR / "models" / "shap_plots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run_shap_analysis():
    print("=======================================================")
    print("Stage 2.9: SHAP Explainability Analysis")
    print("=======================================================")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Run train_ramp_classifiers.py first.")

    checkpoint = joblib.load(MODEL_PATH)
    model = checkpoint['model']
    features = checkpoint['features']

    df = pd.read_csv(DATA_PATH)
    df_eval = df.dropna(subset=features + ['ramp_class']).copy()

    # Take a representative sample (e.g., 500 rows) for fast SHAP calculation
    X_sample = df_eval[features].sample(n=500, random_state=42)

    print("Initializing TreeExplainer and calculating SHAP values...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)

    # Save summary plot for ramp classification
    plt.figure(figsize=(10, 6))
    shap.summary_plot(shap_values, X_sample, plot_type="bar", show=False)
    plt.title("SHAP Feature Importance for Embilipitiya GSS Ramp Classifier", fontsize=12, fontweight='bold')
    plt.tight_layout()

    plot_path = OUTPUT_DIR / "shap_feature_importance.png"
    plt.savefig(plot_path, dpi=300)
    plt.close()

    print(f"\n[Success] SHAP summary plot successfully saved to {plot_path}")
    print("Inspect this plot to present rigorous model explainability during your project defense!")


if __name__ == "__main__":
    run_shap_analysis()