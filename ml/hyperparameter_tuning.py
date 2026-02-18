"""
Optuna Hyperparameter Tuning for XGBoost
==========================================
Automatically finds the BEST model settings by testing
many combinations intelligently.

What Optuna does:
1. Picks random hyperparameters to start
2. Trains a model, measures performance
3. Uses Bayesian optimization to pick BETTER hyperparameters
4. Repeats 50 times (50 "trials")
5. Returns the best combination found
"""

import os
import logging
import numpy as np
import pandas as pd
import xgboost as xgb
import optuna
import mlflow
import mlflow.xgboost

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import f1_score
from sklearn.preprocessing import LabelEncoder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OptunaHPT")

# Silence Optuna's verbose output
optuna.logging.set_verbosity(optuna.logging.WARNING)


def load_and_prepare_data():
    """Load Gold data and prepare features."""
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.appName("Optuna").master("local[*]").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    df = spark.read.parquet("data/gold/weather_features").toPandas()
    spark.stop()

    feature_columns = [
        'temperature_fahrenheit', 'temperature_celsius', 'humidity_percent',
        'pressure_hpa', 'wind_speed_mph', 'wind_direction_degrees',
        'precipitation_mm', 'visibility_km', 'cloud_cover_percent',
        'heat_index', 'wind_chill', 'temp_anomaly', 'temp_anomaly_score',
        'city_avg_temp', 'city_min_temp', 'city_max_temp',
        'city_stddev_temp', 'city_avg_humidity',
        'hour_of_day', 'day_of_week', 'month_of_year', 'is_daytime',
        'latitude', 'longitude',
    ]

    available = [c for c in feature_columns if c in df.columns]
    X = df[available].fillna(-1)
    y = df['is_extreme_weather']

    for col in X.columns:
        if X[col].dtype == 'object':
            X[col] = LabelEncoder().fit_transform(X[col].astype(str))

    return X, y, available


def objective(trial, X, y):
    """
    Optuna objective function — called once per trial.
    
    Optuna SUGGESTS hyperparameters, we train a model with them,
    and return the score. Optuna uses this score to decide what
    to try next.
    """
    # Optuna suggests hyperparameters from these ranges
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 50, 500),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
        'gamma': trial.suggest_float('gamma', 0, 5),
        'reg_alpha': trial.suggest_float('reg_alpha', 0, 2),
        'reg_lambda': trial.suggest_float('reg_lambda', 0, 2),
    }

    n_normal = sum(y == 0)
    n_extreme = max(sum(y == 1), 1)

    model = xgb.XGBClassifier(
        **params,
        scale_pos_weight=n_normal / n_extreme,
        random_state=42,
        eval_metric='logloss',
        use_label_encoder=False,
    )

    # Use cross-validation (more reliable than single train/test split)
    # It splits data into 5 parts, trains on 4, tests on 1, repeats 5 times
    scores = cross_val_score(model, X, y, cv=5, scoring='f1')

    return scores.mean()


def main():
    print("=" * 60)
    print("🔍 OPTUNA - Hyperparameter Tuning for XGBoost")
    print("=" * 60)

    # Load data
    logger.info("📥 Loading data...")
    X, y, features = load_and_prepare_data()
    logger.info(f"   {len(X)} samples, {len(features)} features")

    # Create Optuna study
    # "maximize" because higher F1 score = better model
    study = optuna.create_study(direction='maximize')

    logger.info("🔄 Starting 50 trials (this may take a few minutes)...")

    # Run 50 trials
    study.optimize(lambda trial: objective(trial, X, y), n_trials=50)

    # Results
    best = study.best_trial
    logger.info(f"\n{'='*60}")
    logger.info(f"🏆 BEST TRIAL: #{best.number}")
    logger.info(f"   F1 Score: {best.value:.4f}")
    logger.info(f"   Best hyperparameters:")
    for key, value in best.params.items():
        logger.info(f"     {key}: {value}")

    # Train final model with best params
    logger.info("\n🏋️ Training final model with best parameters...")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    n_normal = sum(y_train == 0)
    n_extreme = max(sum(y_train == 1), 1)

    best_model = xgb.XGBClassifier(
        **best.params,
        scale_pos_weight=n_normal / n_extreme,
        random_state=42,
        eval_metric='logloss',
        use_label_encoder=False,
    )
    best_model.fit(X_train, y_train, verbose=False)

    y_pred = best_model.predict(X_test)
    final_f1 = f1_score(y_test, y_pred, zero_division=0)
    logger.info(f"   Final F1 Score on test set: {final_f1:.4f}")

    # Log to MLflow
    mlflow.set_tracking_uri("file:./mlruns")
    mlflow.set_experiment("climate-extreme-weather-classification")

    with mlflow.start_run(run_name="xgboost-optuna-tuned"):
        mlflow.log_params(best.params)
        mlflow.log_metric("f1_score", final_f1)
        mlflow.log_metric("optuna_best_trial", best.number)
        mlflow.log_metric("optuna_n_trials", 50)
        mlflow.xgboost.log_model(best_model, "xgboost-tuned-model")

    logger.info(f"\n✅ Optuna tuning complete! Best F1: {best.value:.4f}")
    logger.info(f"   Compare with baseline in MLflow UI: mlflow ui --port 5555")


if __name__ == "__main__":
    main()