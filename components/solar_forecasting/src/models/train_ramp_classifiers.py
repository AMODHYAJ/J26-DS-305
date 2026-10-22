"""
Stage 2.5: Multi-Model Training, Evaluation, and Optimal Ramp Classifier Selection.
Location: src/models/train_ramp_classifiers.py
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, ExtraTreesClassifier
from sklearn.metrics import classification_report, f1_score, precision_score, recall_score
import joblib

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "data" / "processed" / "embilipitiya_ramps_classified_15min.csv"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
BEST_MODEL_PATH = MODEL_DIR / "best_ramp_classifier.pkl"


def train_and_select_optimal_classifier():
    print("=======================================================")
    print("Stage 2.5: Multi-Model Ramp Classifier Training & Selection")
    print("=======================================================")

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Classified dataset not found at {DATA_PATH}. Run detect_ramps.py first.")

    df = pd.read_csv(DATA_PATH)
    print(f"Loaded classified dataset: {len(df):,} rows")

    # Feature columns for ramp prediction
    feature_cols = [
        'lat', 'lon', 'capacity_mw', 'cloud_cover', 'cloud_cover_low',
        'cloud_cover_mid', 'cloud_cover_high', 'shortwave_radiation_instant',
        'direct_normal_irradiance_instant', 'diffuse_radiation_instant',
        'temperature_2m', 'relative_humidity_2m', 'wind_speed_10m',
        'clear_sky_ghi_est', 'kt', 'hour', 'minute', 'month', 'dayofyear'
    ]

    available_features = [col for col in feature_cols if col in df.columns]
    target_col = 'ramp_class'

    df_model = df.dropna(subset=available_features + [target_col]).copy()

    # Encode target labels ('Stable', 'Ramp-Up', 'Ramp-Down')
    le = LabelEncoder()
    df_model['target'] = le.fit_transform(df_model[target_col])

    X = df_model[available_features]
    y = df_model['target']

    # Stratified split to preserve class imbalance ratios
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"Training set: {len(X_train):,} rows | Test set: {len(X_test):,} rows\n")

    # Define 4 Candidate Models
    models = {
        "Logistic Regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, random_state=42)),
        "Random Forest Classifier": RandomForestClassifier(n_estimators=100, max_depth=20, random_state=42, n_jobs=-1),
        "Gradient Boosting Classifier": GradientBoostingClassifier(n_estimators=100, max_depth=6, random_state=42),
        "Extra Trees Classifier": ExtraTreesClassifier(n_estimators=100, max_depth=20, random_state=42, n_jobs=-1)
    }

    model_performance = {}
    trained_models = {}

    # Train and evaluate all 4 models
    for name, model in models.items():
        print(f"Training [{name}]...")
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        f1_weighted = f1_score(y_test, y_pred, average='weighted')
        precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
        recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)

        model_performance[name] = {
            'f1': f1_weighted,
            'precision': precision,
            'recall': recall
        }
        trained_models[name] = model
        print(f"  -> {name} | Weighted F1: {f1_weighted:.4f} | Precision: {precision:.4f} | Recall: {recall:.4f}\n")

    # Select optimal model based on highest Weighted F1 Score
    best_model_name = max(model_performance, key=lambda k: model_performance[k]['f1'])
    best_model = trained_models[best_model_name]

    print("=======================================================")
    print(f"[Selection] Optimal Model: {best_model_name}")
    print(f"            Weighted F1: {model_performance[best_model_name]['f1']:.4f}")
    print("=======================================================")

    # Detailed classification report for the optimal model
    y_pred_best = best_model.predict(X_test)
    print("\nDetailed Classification Report for Optimal Model:")
    print(classification_report(y_test, y_pred_best, target_names=le.classes_))

    # Save the optimal model artifact
    joblib.dump({'model': best_model, 'label_encoder': le, 'features': available_features}, BEST_MODEL_PATH)
    print(f"\n[Success] Optimal ramp classifier saved to {BEST_MODEL_PATH}")


if __name__ == "__main__":
    train_and_select_optimal_classifier()