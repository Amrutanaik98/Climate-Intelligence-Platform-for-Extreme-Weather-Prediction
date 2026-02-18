"""
LSTM Temperature Forecasting
==============================
Uses PyTorch LSTM to predict future temperature based on
a sequence of past weather readings.

What LSTM does:
1. Takes a window of past readings (e.g., last 7 readings)
2. Learns patterns in the sequence
3. Predicts the next temperature value
"""

import os
import logging
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import mlflow
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LSTMTrainer")


# ============================================================
# LSTM MODEL DEFINITION
# ============================================================

class WeatherLSTM(nn.Module):
    """
    LSTM Neural Network for temperature prediction.
    
    Architecture:
    - Input layer: takes sequence of weather features
    - LSTM layers: learn temporal patterns (what came before matters)
    - Dropout: prevents overfitting (randomly disables neurons during training)
    - Linear output: produces single temperature prediction
    """
    def __init__(self, input_size, hidden_size=64, num_layers=2, dropout=0.2):
        super(WeatherLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, 1)  # Output: 1 temperature value

    def forward(self, x):
        # x shape: (batch_size, sequence_length, input_size)
        lstm_out, _ = self.lstm(x)
        # Take the output of the LAST time step
        last_output = lstm_out[:, -1, :]
        out = self.dropout(last_output)
        out = self.fc(out)
        return out


# ============================================================
# DATA PREPARATION
# ============================================================

def load_and_prepare_data(sequence_length=7):
    """
    Load Gold data and create sequences for LSTM.
    
    WHAT IS A SEQUENCE?
    Instead of feeding one row at a time, LSTM needs a WINDOW of rows.
    
    If sequence_length=7, we create:
    Input:  [reading_1, reading_2, reading_3, reading_4, reading_5, reading_6, reading_7]
    Target: temperature at reading_8
    
    Then slide the window:
    Input:  [reading_2, reading_3, reading_4, reading_5, reading_6, reading_7, reading_8]
    Target: temperature at reading_9
    
    And so on. This teaches the model: "Given this history, what comes next?"
    """
    logger.info("📥 Loading data for LSTM...")

    from pyspark.sql import SparkSession
    spark = SparkSession.builder.appName("LSTM").master("local[*]").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    df = spark.read.parquet("data/gold/weather_features").toPandas()
    spark.stop()

    # Features to use for LSTM
    feature_cols = [
        'temperature_fahrenheit', 'humidity_percent', 'pressure_hpa',
        'wind_speed_mph', 'heat_index', 'wind_chill',
    ]

    available = [c for c in feature_cols if c in df.columns]
    data = df[available].fillna(method='ffill').fillna(0).values

    # Scale data to 0-1 range (neural networks work better with normalized data)
    scaler = MinMaxScaler()
    scaled_data = scaler.fit_transform(data)

    # Create sequences
    X_sequences = []
    y_targets = []

    for i in range(len(scaled_data) - sequence_length):
        X_sequences.append(scaled_data[i:i + sequence_length])
        # Target: temperature (first column) of the NEXT reading
        y_targets.append(scaled_data[i + sequence_length, 0])

    X = np.array(X_sequences)
    y = np.array(y_targets)

    logger.info(f"   Created {len(X)} sequences of length {sequence_length}")
    logger.info(f"   Features per timestep: {len(available)}")

    return X, y, scaler, available


def train_lstm(X_train, y_train, X_val, y_val, input_size, epochs=50):
    """Train the LSTM model."""
    logger.info(f"🏋️ Training LSTM for {epochs} epochs...")

    # Convert to PyTorch tensors
    X_train_t = torch.FloatTensor(X_train)
    y_train_t = torch.FloatTensor(y_train).unsqueeze(1)
    X_val_t = torch.FloatTensor(X_val)
    y_val_t = torch.FloatTensor(y_val).unsqueeze(1)

    # Create data loaders (batches data for efficient training)
    train_dataset = TensorDataset(X_train_t, y_train_t)
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)

    # Initialize model
    model = WeatherLSTM(input_size=input_size, hidden_size=64, num_layers=2)
    criterion = nn.MSELoss()  # Mean Squared Error (for regression)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    # Training loop
    train_losses = []
    val_losses = []

    for epoch in range(epochs):
        model.train()
        epoch_loss = 0

        for batch_X, batch_y in train_loader:
            optimizer.zero_grad()
            output = model(batch_X)
            loss = criterion(output, batch_y)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()

        avg_train_loss = epoch_loss / len(train_loader)
        train_losses.append(avg_train_loss)

        # Validation loss
        model.eval()
        with torch.no_grad():
            val_output = model(X_val_t)
            val_loss = criterion(val_output, y_val_t).item()
            val_losses.append(val_loss)

        if (epoch + 1) % 10 == 0:
            logger.info(f"   Epoch {epoch+1}/{epochs} | Train Loss: {avg_train_loss:.6f} | Val Loss: {val_loss:.6f}")

    return model, train_losses, val_losses


def main():
    print("=" * 60)
    print("🧠 LSTM - Temperature Forecasting")
    print("=" * 60)

    SEQUENCE_LENGTH = 7

    # Step 1: Load and prepare data
    X, y, scaler, features = load_and_prepare_data(SEQUENCE_LENGTH)

    # Step 2: Train/test split (keep time order! Don't shuffle time-series)
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    logger.info(f"📊 Train: {len(X_train)} | Test: {len(X_test)}")

    # Step 3: Train with MLflow tracking
    mlflow.set_tracking_uri("file:./mlruns")
    mlflow.set_experiment("climate-temperature-forecasting")

    with mlflow.start_run(run_name="lstm-baseline"):
        mlflow.log_param("model_type", "LSTM")
        mlflow.log_param("sequence_length", SEQUENCE_LENGTH)
        mlflow.log_param("hidden_size", 64)
        mlflow.log_param("num_layers", 2)
        mlflow.log_param("epochs", 50)
        mlflow.log_param("learning_rate", 0.001)

        # Train
        model, train_losses, val_losses = train_lstm(
            X_train, y_train, X_test, y_test,
            input_size=len(features), epochs=50
        )

        # Evaluate
        model.eval()
        with torch.no_grad():
            predictions = model(torch.FloatTensor(X_test)).numpy().flatten()

        mae = mean_absolute_error(y_test, predictions)
        rmse = np.sqrt(mean_squared_error(y_test, predictions))

        mlflow.log_metric("mae", mae)
        mlflow.log_metric("rmse", rmse)

        logger.info(f"\n📊 Results:")
        logger.info(f"   MAE (Mean Absolute Error): {mae:.4f}")
        logger.info(f"   RMSE (Root Mean Squared Error): {rmse:.4f}")

        # Save training loss plot
        plt.figure(figsize=(10, 5))
        plt.plot(train_losses, label='Train Loss')
        plt.plot(val_losses, label='Validation Loss')
        plt.xlabel('Epoch')
        plt.ylabel('Loss')
        plt.title('LSTM Training Progress')
        plt.legend()
        plt.tight_layout()
        plt.savefig("ml/plots/lstm_training_loss.png", dpi=150)
        plt.close()
        mlflow.log_artifact("ml/plots/lstm_training_loss.png")

        # Save predictions vs actual plot
        plt.figure(figsize=(12, 5))
        plt.plot(y_test[:100], label='Actual', alpha=0.7)
        plt.plot(predictions[:100], label='Predicted', alpha=0.7)
        plt.xlabel('Time Step')
        plt.ylabel('Temperature (scaled)')
        plt.title('LSTM: Predicted vs Actual Temperature')
        plt.legend()
        plt.tight_layout()
        plt.savefig("ml/plots/lstm_predictions.png", dpi=150)
        plt.close()
        mlflow.log_artifact("ml/plots/lstm_predictions.png")

        # Save model
        torch.save(model.state_dict(), "ml/models/lstm_model.pth")
        mlflow.log_artifact("ml/models/lstm_model.pth")

        logger.info(f"\n✅ LSTM training complete!")
        logger.info(f"   View in MLflow: mlflow ui --port 5555")


if __name__ == "__main__":
    main()