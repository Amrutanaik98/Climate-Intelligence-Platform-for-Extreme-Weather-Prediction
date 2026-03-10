"""
XGBoost Classifier for Extreme Weather Prediction
===================================================
Reads Gold layer data, trains an XGBoost model to predict
whether weather conditions are extreme (heatwave, storm, etc.)

Run: python ml/train_xgboost.py
"""

import os
import logging
import numpy as np
import pandas as pd
import xgboost as xgb
import mlflow
import mlflow.xgboost
import shap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    classification_report, confusion_matrix
)
from sklearn.preprocessing import LabelEncoder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("XGBoostTrainer")


def load_gold_data():
    """Load Gold layer data using pandas (fast, no Spark needed)."""
    logger.info("📥 Loading Gold layer data...")

    gold_path = "data/gold/weather_features"
    if not os.path.exists(gold_path):
        logger.error("❌ Gold layer not found!")
        return None

    df = pd.read_parquet(gold_path)
    logger.info(f"   Loaded {len(df)} records with {len(df.columns)} features")
    logger.info(f"   Cities: {df['city'].nunique()}")
    return df


def prepare_features(df):
    """
    Prepare features (X) and target (y) for ML training.

    FEATURE SELECTION: We pick the columns that the model will use to
    make predictions. We EXCLUDE:
    - Target variable (is_extreme_weather) — that's what we're predicting!
    - IDs and timestamps — not predictive
    - Derived extreme flags — they're calculated FROM the target
    - Text columns — ML models need numbers
    
    TARGET: is_extreme_weather (0 = normal, 1 = extreme)
    """
    logger.info("🔧 Preparing features...")

    feature_columns = [
        'temperature_fahrenheit',
        'temperature_celsius',
        'humidity_percent',
        'pressure_hpa',
        'wind_speed_mph',
        'wind_direction_degrees',
        'precipitation_mm',
        'visibility_miles',
        'cloud_cover_percent',
        'heat_index',
        'wind_chill',
        'temperature_anomaly',
        'temp_anomaly_score',
        'city_avg_temp',
        'city_min_temp',
        'city_max_temp',
        'city_stddev_temp',
        'city_avg_humidity',
        'hour_of_day',
        'day_of_week',
        'month_of_year',
        'is_daytime',
        'latitude',
        'longitude',
    ]

    # Only keep columns that exist in the data
    available_features = [col for col in feature_columns if col in df.columns]
    logger.info(f"   Using {len(available_features)} features: {available_features}")

    X = df[available_features].copy()
    y = df['is_extreme_weather'].copy()

    # Handle any remaining nulls
    X = X.fillna(-1)

    # Convert any non-numeric columns
    for col in X.columns:
        if X[col].dtype == 'object':
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col].astype(str))

    logger.info(f"   Features shape: {X.shape}")
    logger.info(f"   Target distribution: {y.value_counts().to_dict()}")

    return X, y, available_features


def train_xgboost(X_train, y_train, X_test, y_test):
    """
    Train XGBoost classifier.

    HYPERPARAMETERS:
    - n_estimators: How many trees to build (more = better but slower)
    - max_depth: How deep each tree can be (deeper = more complex)
    - learning_rate: How much each tree contributes (smaller = more careful)
    - scale_pos_weight: Handles imbalanced data (few extreme events vs many normal)
    """
    logger.info("🏋️ Training XGBoost model...")

    n_normal = sum(y_train == 0)
    n_extreme = max(sum(y_train == 1), 1)
    scale_weight = n_normal / n_extreme

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=scale_weight,
        random_state=42,
        eval_metric='logloss',
        use_label_encoder=False,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )

    logger.info("✅ XGBoost model trained!")
    return model


def evaluate_model(model, X_test, y_test):
    """Evaluate model performance with multiple metrics."""
    logger.info("📊 Evaluating model...")

    y_pred = model.predict(X_test)

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1_score": f1_score(y_test, y_pred, zero_division=0),
    }

    logger.info(f"   Accuracy:  {metrics['accuracy']:.4f}")
    logger.info(f"   Precision: {metrics['precision']:.4f}")
    logger.info(f"   Recall:    {metrics['recall']:.4f}")
    logger.info(f"   F1 Score:  {metrics['f1_score']:.4f}")

    print("\n" + classification_report(y_test, y_pred,
          target_names=["Normal", "Extreme Weather"]))

    return metrics, y_pred


def generate_shap_explanations(model, X_test, feature_names):
    """
    Generate SHAP (SHapley Additive exPlanations) values.

    SHAP tells you WHY the model made each prediction.
    The summary plot shows which features matter MOST across all predictions.
    """
    logger.info("🔍 Generating SHAP explanations...")

    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_test)

        # SHAP summary plot (dot plot)
        plt.figure(figsize=(12, 8))
        shap.summary_plot(shap_values, X_test, feature_names=feature_names,
                         show=False, max_display=15)
        plt.tight_layout()
        plt.savefig("ml/plots/shap_summary.png", dpi=150, bbox_inches='tight')
        plt.close()
        logger.info("   SHAP summary plot saved to ml/plots/shap_summary.png")

        # SHAP feature importance (bar plot)
        plt.figure(figsize=(12, 8))
        shap.summary_plot(shap_values, X_test, feature_names=feature_names,
                         plot_type="bar", show=False, max_display=15)
        plt.tight_layout()
        plt.savefig("ml/plots/shap_importance.png", dpi=150, bbox_inches='tight')
        plt.close()
        logger.info("   SHAP importance plot saved to ml/plots/shap_importance.png")

        return shap_values

    except Exception as e:
        logger.warning(f"   SHAP generation failed: {e}")
        return None


def save_confusion_matrix(y_test, y_pred):
    """Save confusion matrix as an image."""
    plt.figure(figsize=(8, 6))
    cm = confusion_matrix(y_test, y_pred)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=["Normal", "Extreme"],
                yticklabels=["Normal", "Extreme"])
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.title("XGBoost - Confusion Matrix")
    plt.tight_layout()
    plt.savefig("ml/plots/confusion_matrix.png", dpi=150)
    plt.close()
    logger.info("   Confusion matrix saved to ml/plots/confusion_matrix.png")


def main():
    print("=" * 60)
    print("🤖 XGBOOST - Extreme Weather Classification")
    print("=" * 60)

    # Create plots directory
    os.makedirs("ml/plots", exist_ok=True)
    os.makedirs("ml/models", exist_ok=True)

    # Step 1: Load data
    df = load_gold_data()
    if df is None:
        return

    # Step 2: Prepare features
    X, y, feature_names = prepare_features(df)

    # Step 3: Split into train (80%) and test (20%)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    logger.info(f"📊 Train: {len(X_train)} samples | Test: {len(X_test)} samples")

    # Step 4: MLflow experiment tracking
    mlflow.set_tracking_uri("file:./mlruns")
    mlflow.set_experiment("climate-extreme-weather-classification")

    with mlflow.start_run(run_name="xgboost-baseline"):
        mlflow.log_param("model_type", "XGBoost")
        mlflow.log_param("n_estimators", 200)
        mlflow.log_param("max_depth", 6)
        mlflow.log_param("learning_rate", 0.1)
        mlflow.log_param("train_size", len(X_train))
        mlflow.log_param("test_size", len(X_test))
        mlflow.log_param("n_features", len(feature_names))
        mlflow.log_param("n_cities", df['city'].nunique())

        # Step 5: Train
        model = train_xgboost(X_train, y_train, X_test, y_test)

        # Step 6: Evaluate
        metrics, y_pred = evaluate_model(model, X_test, y_test)

        for metric_name, metric_value in metrics.items():
            mlflow.log_metric(metric_name, metric_value)

        # Step 7: SHAP explanations
        shap_values = generate_shap_explanations(model, X_test, feature_names)

        # Step 8: Confusion matrix
        save_confusion_matrix(y_test, y_pred)

        # Step 9: Save model
        model.save_model("ml/models/xgboost_model.json")
        mlflow.xgboost.log_model(model, "xgboost-model")

        # Log plots
        for plot in ["shap_summary.png", "shap_importance.png", "confusion_matrix.png"]:
            path = f"ml/plots/{plot}"
            if os.path.exists(path):
                mlflow.log_artifact(path)

        logger.info(f"\n✅ XGBoost training complete!")
        logger.info(f"   Model saved to: ml/models/xgboost_model.json")
        logger.info(f"   View in MLflow: mlflow ui --port 5555")


if __name__ == "__main__":
    main()