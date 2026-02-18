"""
XGBoost Classifier for Extreme Weather Prediction
===================================================
Reads Gold layer data, trains an XGBoost model to predict
whether weather conditions are extreme (heatwave, storm, etc.)

What this script does:
1. Load data from Gold layer (Parquet)
2. Prepare features (X) and target (y)
3. Split into train/test sets
4. Train XGBoost classifier
5. Evaluate model performance
6. Log everything to MLflow
7. Generate SHAP explanations
8. Save model
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
matplotlib.use('Agg')  # Non-interactive backend (no window popup)
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
    """
    Load Gold layer data using PySpark, convert to Pandas DataFrame.
    
    WHY PySpark first? Because Gold data is in Parquet format (big data format).
    PySpark reads it, then we convert to Pandas for ML (scikit-learn/XGBoost
    work with Pandas, not Spark DataFrames).
    """
    logger.info("📥 Loading Gold layer data...")

    from pyspark.sql import SparkSession
    spark = (
        SparkSession.builder
        .appName("XGBoost-DataLoad")
        .master("local[*]")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    gold_path = "data/gold/weather_features"
    if not os.path.exists(gold_path):
        logger.error("❌ Gold layer not found!")
        return None

    df = spark.read.parquet(gold_path).toPandas()
    spark.stop()

    logger.info(f"   Loaded {len(df)} records with {len(df.columns)} features")
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

    # These are the features the model will use to predict
    feature_columns = [
        'temperature_fahrenheit',
        'temperature_celsius',
        'humidity_percent',
        'pressure_hpa',
        'wind_speed_mph',
        'wind_direction_degrees',
        'precipitation_mm',
        'visibility_km',
        'cloud_cover_percent',
        'heat_index',
        'wind_chill',
        'temp_anomaly',
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
    logger.info(f"   Using {len(available_features)} features")

    X = df[available_features].copy()
    y = df['is_extreme_weather'].copy()

    # Handle any remaining nulls (fill with -1 to signal "missing")
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
    
    HYPERPARAMETERS (settings that control how the model learns):
    - n_estimators: How many trees to build (more = better but slower)
    - max_depth: How deep each tree can be (deeper = more complex)
    - learning_rate: How much each tree contributes (smaller = more careful)
    - scale_pos_weight: Handles imbalanced data (few extreme events vs many normal)
    """
    logger.info("🏋️ Training XGBoost model...")

    # Calculate class imbalance ratio
    # WHY? If 98% of data is "normal" and 2% is "extreme", the model could
    # just always predict "normal" and get 98% accuracy (but miss all extremes!)
    # scale_pos_weight tells the model to pay MORE attention to extreme events.
    n_normal = sum(y_train == 0)
    n_extreme = max(sum(y_train == 1), 1)
    scale_weight = n_normal / n_extreme

    model = xgb.XGBClassifier(
        n_estimators=200,           # Build 200 trees
        max_depth=6,                # Each tree can be 6 levels deep
        learning_rate=0.1,          # Each tree contributes 10%
        scale_pos_weight=scale_weight,  # Pay more attention to rare extreme events
        random_state=42,            # Reproducible results
        eval_metric='logloss',      # Loss function for binary classification
        use_label_encoder=False,
    )

    # Train the model
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],  # Monitor performance on test set
        verbose=False
    )

    logger.info("✅ XGBoost model trained!")
    return model


def evaluate_model(model, X_test, y_test):
    """
    Evaluate model performance with multiple metrics.
    
    WHY multiple metrics?
    - Accuracy alone is misleading for imbalanced data
    - Precision: "When model says extreme, how often is it right?"
    - Recall: "Of all actual extreme events, how many did model catch?"
    - F1: Balance of precision and recall
    """
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

    # Detailed classification report
    print("\n" + classification_report(y_test, y_pred,
          target_names=["Normal", "Extreme Weather"]))

    return metrics, y_pred


def generate_shap_explanations(model, X_test, feature_names):
    """
    Generate SHAP (SHapley Additive exPlanations) values.
    
    WHAT IS SHAP?
    SHAP tells you WHY the model made each prediction.
    
    Example: Model predicts "EXTREME WEATHER" for a record.
    SHAP says: "Because temperature was +15 impact, humidity was +10 impact,
    pressure was -3 impact. Temperature and humidity drove this prediction."
    
    This is CRITICAL for trust. A doctor won't use an AI that just says
    "the patient is sick" without explaining why. Same for weather prediction.
    
    The SHAP summary plot shows which features matter MOST across all predictions.
    """
    logger.info("🔍 Generating SHAP explanations...")

    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_test)

        # Save SHAP summary plot
        plt.figure(figsize=(12, 8))
        shap.summary_plot(shap_values, X_test, feature_names=feature_names,
                         show=False, max_display=15)
        plt.tight_layout()
        plt.savefig("ml/plots/shap_summary.png", dpi=150, bbox_inches='tight')
        plt.close()
        logger.info("   SHAP summary plot saved to ml/plots/shap_summary.png")

        # Save SHAP feature importance plot
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

    # Step 1: Load data
    df = load_gold_data()
    if df is None:
        return

    # Step 2: Prepare features
    X, y, feature_names = prepare_features(df)

    # Step 3: Split into train (80%) and test (20%)
    # WHY split? We train on 80% and test on 20% the model has NEVER seen.
    # This tells us how well the model generalizes to new data.
    # If we tested on training data, the model would just memorize answers.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    logger.info(f"📊 Train: {len(X_train)} samples | Test: {len(X_test)} samples")

    # Step 4: Start MLflow experiment tracking
    # WHY MLflow? Every time you train a model, you want to record:
    # - What parameters you used
    # - What metrics you got
    # - Which model file was produced
    # So you can compare experiments and pick the best one.
    mlflow.set_tracking_uri("file:./mlruns")
    mlflow.set_experiment("climate-extreme-weather-classification")

    with mlflow.start_run(run_name="xgboost-baseline"):
        # Log parameters
        mlflow.log_param("model_type", "XGBoost")
        mlflow.log_param("n_estimators", 200)
        mlflow.log_param("max_depth", 6)
        mlflow.log_param("learning_rate", 0.1)
        mlflow.log_param("train_size", len(X_train))
        mlflow.log_param("test_size", len(X_test))
        mlflow.log_param("n_features", len(feature_names))

        # Step 5: Train
        model = train_xgboost(X_train, y_train, X_test, y_test)

        # Step 6: Evaluate
        metrics, y_pred = evaluate_model(model, X_test, y_test)

        # Log metrics to MLflow
        for metric_name, metric_value in metrics.items():
            mlflow.log_metric(metric_name, metric_value)

        # Step 7: SHAP explanations
        shap_values = generate_shap_explanations(model, X_test, feature_names)

        # Step 8: Confusion matrix
        save_confusion_matrix(y_test, y_pred)

        # Step 9: Log model to MLflow
        mlflow.xgboost.log_model(model, "xgboost-model")

        # Log plots as artifacts
        if os.path.exists("ml/plots/shap_summary.png"):
            mlflow.log_artifact("ml/plots/shap_summary.png")
        if os.path.exists("ml/plots/shap_importance.png"):
            mlflow.log_artifact("ml/plots/shap_importance.png")
        if os.path.exists("ml/plots/confusion_matrix.png"):
            mlflow.log_artifact("ml/plots/confusion_matrix.png")

        logger.info(f"\n✅ XGBoost training complete!")
        logger.info(f"   MLflow run logged. View with: mlflow ui")


if __name__ == "__main__":
    main()