# 🌍 Climate Intelligence Platform for Extreme Weather Prediction

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Apache Kafka](https://img.shields.io/badge/Apache%20Kafka-7.5-red.svg)](https://kafka.apache.org)
[![Apache Spark](https://img.shields.io/badge/Apache%20Spark-3.5.1-orange.svg)](https://spark.apache.org)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED.svg)](https://docker.com)
[![Groq](https://img.shields.io/badge/Groq%20LLM-Gen%20AI-green.svg)](https://groq.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> A production-grade, end-to-end climate intelligence platform that ingests real-time weather data from OpenWeatherMap, processes it through a medallion data lake using Apache Spark, predicts extreme weather events using XGBoost & LSTM, and provides Gen AI-powered natural language insights via Groq LLM — orchestrated with Apache Airflow and containerized with Docker.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Features](#-features)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Pipeline Deep Dive](#-pipeline-deep-dive)
- [ML Models](#-ml-models)
- [Gen AI Integration](#-gen-ai-integration)
- [API Documentation](#-api-documentation)
- [Implementation Roadmap](#-implementation-roadmap)
- [License](#-license)

---

## 🎯 Overview

### The Problem
Extreme weather events (heatwaves, floods, hurricanes, storms) are increasing in frequency and severity. Early prediction can save lives, reduce economic damage, and help communities prepare. Current systems often lack real-time processing, explainability, and accessible interfaces for non-technical users.

### The Solution
This platform combines **real-time data engineering**, **machine learning**, and **generative AI** to:
- Ingest live weather streams from 20 US cities via Apache Kafka with Avro schema validation
- Process data using Apache Spark (batch + streaming) through a Medallion Architecture
- Predict extreme weather events using an ensemble of XGBoost + LSTM models
- Generate human-readable weather intelligence reports using Groq LLM (Llama 3.1)
- Allow users to query climate data in natural language via a RAG-powered chatbot
- Orchestrate the entire pipeline with Apache Airflow

### Who Is This For?
- Emergency response agencies needing early warning systems
- Insurance companies assessing climate risk
- Researchers studying extreme weather patterns
- City planners building climate-resilient infrastructure

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          DATA SOURCES                                     │
│          OpenWeatherMap API (20 US Cities, Real-Time)                     │
│  New York │ LA │ Chicago │ Houston │ Phoenix │ Miami │ Seattle │ ...     │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                 INGESTION LAYER (Real-Time Streaming)                     │
│                                                                           │
│   Python Kafka Producer (Avro Serialization)                             │
│     └──→ Apache Kafka Broker                                             │
│            ├── Topic: raw-weather-data (3 partitions)                    │
│            ├── Topic: weather-alerts (2 partitions)                      │
│            └── Topic: weather-events                                     │
│                                                                           │
│   Confluent Schema Registry (Avro) ── Data contract enforcement          │
│   Kafka UI (http://localhost:8888) ── Visual topic monitoring            │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│              PROCESSING LAYER (Batch + Stream)                            │
│                                                                           │
│   Spark Structured Streaming (with fastavro deserialization)             │
│     └── Kafka (Avro) → Bronze Layer (real-time, 30s trigger)            │
│                                                                           │
│   Spark Batch Jobs (Medallion Architecture)                              │
│     ├── Bronze → Silver : Deduplication, null handling, validation       │
│     ├── Silver → Gold   : Heat index, wind chill, anomaly scores,       │
│     │                     extreme weather flags, time features (49 cols) │
│     └── Gold  → PostgreSQL: Star schema dimensional warehouse            │
│                                                                           │
│   Apache Airflow ── DAG orchestration (http://localhost:8085)            │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       STORAGE LAYER                                       │
│                                                                           │
│   Local Data Lake (Parquet, Medallion Architecture)                      │
│     ├── data/bronze/  → Raw Parquet (as received from Kafka)             │
│     ├── data/silver/  → Cleaned, validated, deduplicated                 │
│     └── data/gold/    → 49 features, ML-ready                           │
│                                                                           │
│   PostgreSQL Data Warehouse (Star Schema)                                │
│     ├── Fact: fact_weather_readings (660+ records)                       │
│     ├── Dim:  dim_location (20 cities with regions)                      │
│     ├── Dim:  dim_time (hourly for 2 years)                              │
│     └── Dim:  dim_weather_type (15 weather conditions)                   │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        ML / AI LAYER                                      │
│                                                                           │
│   XGBoost Classifier                                                     │
│     ├── Extreme weather classification (F1: 1.0)                         │
│     ├── SHAP explainability (feature importance plots)                   │
│     └── Optuna hyperparameter tuning (50 trials)                         │
│                                                                           │
│   PyTorch LSTM                                                           │
│     ├── Temperature time-series forecasting (MAE: 0.039)                 │
│     ├── 7-step sequence window, 2-layer architecture                     │
│     └── Training/validation loss tracking                                │
│                                                                           │
│   MLflow (http://localhost:5555)                                         │
│     ├── Experiment tracking (parameters, metrics, artifacts)             │
│     ├── Model versioning & comparison                                    │
│     └── SHAP plots, confusion matrix, loss curves logged                 │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      GEN AI LAYER (Groq LLM - Llama 3.1)                │
│                                                                           │
│   Weather Report Generator                                               │
│     └── ML predictions → Groq LLM → Natural language reports            │
│                                                                           │
│   Anomaly Explanation Engine                                             │
│     └── High anomaly scores → LLM explains WHY in plain English         │
│                                                                           │
│   RAG Climate Chatbot (ChromaDB + Groq)                                  │
│     └── User question → Vector search → LLM generates grounded answer   │
│                                                                           │
│   Text-to-SQL Engine                                                     │
│     └── Natural language → SQL → PostgreSQL → Natural language answer    │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Category | Technologies | Purpose |
|----------|-------------|---------|
| **Data Ingestion** | Apache Kafka, Confluent Schema Registry (Avro), Kafka UI | Real-time streaming with schema validation |
| **Stream Processing** | Spark Structured Streaming, fastavro | Avro deserialization, Kafka → Bronze in real-time |
| **Batch Processing** | Apache Spark (PySpark) | Medallion transformations (Bronze → Silver → Gold) |
| **Orchestration** | Apache Airflow (CeleryExecutor) | DAG-based pipeline scheduling & monitoring |
| **Data Lake** | Local Parquet files (Medallion Architecture) | Partitioned by ingestion_date |
| **Data Warehouse** | PostgreSQL (Star Schema) | Fact + dimension tables for SQL analytics |
| **Traditional ML** | XGBoost, Scikit-learn, SHAP, Optuna | Classification, explainability, hyperparameter tuning |
| **Deep Learning** | PyTorch (LSTM) | Time-series temperature forecasting |
| **ML Ops** | MLflow | Experiment tracking, model versioning, artifact logging |
| **Gen AI / LLM** | Groq API (Llama 3.1), ChromaDB, LangChain | RAG chatbot, report generation, text-to-SQL |
| **Backend API** | FastAPI | REST API for predictions and chatbot |
| **Frontend** | Streamlit | Interactive dashboard |
| **Containerization** | Docker, Docker Compose | 8+ services orchestrated locally |
| **Cloud Platform** | GCP (GCS, BigQuery, GKE, Vertex AI, Cloud Run) | Production deployment |
| **Infrastructure as Code** | Terraform | Automated GCP resource provisioning |
| **CI/CD** | GitHub Actions | Automated testing, building, deployment |
| **Monitoring** | Prometheus, Grafana | Infrastructure metrics & alerting |
| **Languages** | Python 3.11, SQL, YAML, HCL | Core development |

---

## ✨ Features

### Data Engineering
- **Real-time ingestion** from OpenWeatherMap API for 20 US cities via Kafka
- **Avro schema enforcement** with Confluent Schema Registry
- **Medallion data lake** (Bronze → Silver → Gold) with Parquet partitioning
- **Star schema warehouse** in PostgreSQL (fact + 3 dimension tables)
- **Data quality validation** — range checks, null handling, deduplication
- **Airflow DAGs** orchestrating the full pipeline on schedule

### Machine Learning
- **Extreme weather classification** with XGBoost (F1 Score: 1.0)
- **Temperature forecasting** with LSTM (MAE: 0.039, RMSE: 0.064)
- **49 engineered features** including heat index, wind chill, anomaly scores
- **SHAP explainability** — understand WHY the model predicted extreme weather
- **Optuna hyperparameter tuning** — 50 automated trials
- **MLflow experiment tracking** — all metrics, parameters, and plots logged

### Generative AI
- **Natural language weather reports** from raw ML predictions via Groq LLM
- **Anomaly explanation engine** — LLM explains unusual weather patterns
- **RAG chatbot** — ask climate questions grounded in your actual data (ChromaDB)
- **Text-to-SQL** — query the warehouse in plain English

### Infrastructure
- **8+ Docker containers** managed via Docker Compose
- **Kafka + Zookeeper + Schema Registry** for streaming infrastructure
- **Spark Master + Worker** for distributed processing
- **Airflow (Webserver + Scheduler + Worker)** for orchestration
- **PostgreSQL + Redis** for metadata and task queuing

### Google Cloud Platform (Production Deployment)
- **Google Cloud Storage (GCS)** — Cloud data lake replacing local Parquet (Bronze/Silver/Gold buckets)
- **Google BigQuery** — Cloud data warehouse replacing local PostgreSQL
- **Google Kubernetes Engine (GKE)** — Container orchestration for all 12+ services
- **Vertex AI** — ML model serving with auto-scaling endpoints
- **Cloud Run** — Serverless FastAPI + Streamlit deployment
- **Artifact Registry** — Docker image storage
- **Terraform** — Infrastructure as Code for all GCP resources
- **GitHub Actions** — CI/CD pipeline (lint → test → build → deploy)

---

## 📁 Project Structure

```
Climate-Intelligence-Platform-for-Extreme-Weather-Prediction/
│
├── README.md                              # This file
├── docker-compose.yml                     # All 8+ services (one command startup)
├── .env                                   # API keys & configuration (git-ignored)
├── .env.example                           # Environment template
├── .gitignore                             # Git ignore rules
│
├── data_ingestion/                        # === KAFKA PRODUCERS ===
│   ├── Dockerfile                         # Container for producer service
│   ├── requirements.txt                   # confluent-kafka, requests, etc.
│   ├── kafka_producer_openweather.py      # Production Avro producer (20 cities)
│   ├── kafka_producer.py                  # Simple test producer (mock data)
│   ├── kafka_consumer.py                  # Simple test consumer
│   ├── kafka_consumer_test.py             # Avro consumer for verification
│   ├── real_kafka_producer.py             # NOAA-based producer
│   ├── noaa_weather_client.py             # NOAA API client
│   ├── avro_schemas/
│   │   ├── weather_reading.avsc           # Avro schema (16 fields)
│   │   └── weather_alert.avsc            # Alert schema (10 fields)
│   └── kafka_connect/
│       └── gcs_sink_connector.json        # GCS sink config (for cloud deploy)
│
├── data_processing/                       # === SPARK JOBS ===
│   ├── spark_streaming_bronze.py          # Kafka → Bronze (Avro → Parquet)
│   ├── spark_batch_silver.py              # Bronze → Silver (cleaning)
│   ├── spark_batch_gold.py                # Silver → Gold (49 features)
│   ├── data_processor.py                  # Utility processor
│   ├── init_database.py                   # Database initialization
│   └── view_data.py                       # Data inspection utility
│
├── orchestration/                         # === AIRFLOW ===
│   ├── dags/
│   │   ├── climate_pipeline_dag.py        # Main pipeline DAG
│   │   └── load_warehouse.py              # Gold → PostgreSQL loader
│   └── sql/
│       └── create_warehouse.sql           # Star schema DDL
│
├── ml/                                    # === MACHINE LEARNING ===
│   ├── train_xgboost.py                   # XGBoost classifier + SHAP + MLflow
│   ├── train_lstm.py                      # PyTorch LSTM forecaster + MLflow
│   ├── hyperparameter_tuning.py           # Optuna (50 trials) + MLflow
│   ├── models/
│   │   └── lstm_model.pth                 # Saved LSTM weights
│   └── plots/
│       ├── confusion_matrix.png           # XGBoost confusion matrix
│       ├── shap_summary.png               # SHAP feature importance (dots)
│       ├── shap_importance.png            # SHAP feature importance (bars)
│       ├── lstm_training_loss.png         # LSTM train/val loss curves
│       └── lstm_predictions.png           # Predicted vs actual temperature
│
├── genai/                                 # === GEN AI (Groq LLM) ===
│   ├── report_generator.py                # Predictions → natural language reports
│   ├── anomaly_explainer.py               # Anomaly → LLM explanation
│   ├── rag_pipeline.py                    # ChromaDB + Groq RAG chatbot
│   ├── text_to_sql.py                     # English → SQL → PostgreSQL → answer
│   ├── embeddings/                        # Vector store data
│   └── prompts/                           # Prompt templates
│
├── data/                                  # === DATA LAKE (git-ignored) ===
│   ├── bronze/                            # Raw Parquet from Kafka
│   │   └── weather_readings/
│   │       └── ingestion_date=2026-02-17/
│   ├── silver/                            # Cleaned Parquet
│   │   └── weather_readings/
│   │       └── reading_date=2026-02-17/
│   ├── gold/                              # Feature-engineered (49 columns)
│   │   └── weather_features/
│   │       └── reading_date=2026-02-17/
│   └── checkpoints/                       # Spark streaming checkpoints
│       └── bronze/
│
├── mlruns/                                # === MLFLOW (git-ignored) ===
│   └── (experiment tracking data)
│
├── infrastructure/                        # === DEPLOYMENT (Week 8) ===
│   ├── terraform/
│   └── kubernetes/
│
├── tests/                                 # === TESTS ===
│   ├── test_ingestion/
│   ├── test_processing/
│   ├── test_ml/
│   ├── test_genai/
│   └── test_api/
│
├── scripts/                               # === UTILITY SCRIPTS ===
│   ├── setup_local.sh
│   └── create_kafka_topics.sh
│
└── docs/                                  # === DOCUMENTATION ===
    ├── ARCHITECTURE.md
    └── DEPLOYMENT.md
```

---

## 🚀 Getting Started

### Prerequisites

| Tool | Version | Installation |
|------|---------|-------------|
| Python | 3.11+ | [python.org](https://python.org) |
| Java | 17 (Temurin) | [adoptium.net](https://adoptium.net) |
| Docker Desktop | Latest | [docker.com](https://docker.com/products/docker-desktop) |
| Git | Latest | [git-scm.com](https://git-scm.com) |

### Quick Start (Windows)

```powershell
# 1. Clone the repository
git clone https://github.com/yourusername/Climate-Intelligence-Platform-for-Extreme-Weather-Prediction.git
cd Climate-Intelligence-Platform-for-Extreme-Weather-Prediction

# 2. Create virtual environment
python -m venv venv
.\venv\Scripts\Activate

# 3. Install dependencies
python -m pip install confluent-kafka httpx requests python-dotenv fastavro
python -m pip install pyspark==3.5.1 psycopg2-binary
python -m pip install xgboost scikit-learn mlflow shap optuna torch matplotlib seaborn
python -m pip install groq chromadb langchain langchain-community sentence-transformers

# 4. Copy environment template and add your API keys
copy .env.example .env
# Edit .env with your OPENWEATHER_API_KEY, GROQ_API_KEY

# 5. Set environment variables (required every PowerShell session)
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
$env:HADOOP_HOME = "C:\hadoop"
$env:PYSPARK_PYTHON = "python"
$env:PYSPARK_DRIVER_PYTHON = "python"

# 6. Start all Docker services
docker-compose up -d

# 7. Verify services are running
docker-compose ps
```

### Access Points (Local)

| Service | URL | Description |
|---------|-----|-------------|
| **Kafka UI** | http://localhost:8888 | Topic monitoring, message browser |
| **Schema Registry** | http://localhost:8081 | Avro schema management |
| **Spark Master** | http://localhost:8090 | Spark job monitoring |
| **Airflow** | http://localhost:8085 | Pipeline orchestration (admin/admin) |
| **MLflow** | http://localhost:5555 | ML experiment tracking |
| **PostgreSQL** | localhost:5432 | Data warehouse (airflow/airflow) |

### Run the Full Pipeline

```powershell
# Terminal 1: Start Kafka producer (sends real weather data)
cd data_ingestion
python kafka_producer_openweather.py

# Terminal 2: Start Spark streaming (Kafka → Bronze)
python data_processing/spark_streaming_bronze.py

# Terminal 3: Run batch processing (after streaming has data)
python data_processing/spark_batch_silver.py
python data_processing/spark_batch_gold.py

# Load into warehouse
python orchestration/dags/load_warehouse.py

# Train ML models
python ml/train_xgboost.py
python ml/hyperparameter_tuning.py
python ml/train_lstm.py

# Run Gen AI features
python genai/report_generator.py
python genai/anomaly_explainer.py
python genai/rag_pipeline.py
python genai/text_to_sql.py
```

---

## 🔄 Pipeline Deep Dive

### Data Flow

```
OpenWeatherMap API (20 cities, every 30 seconds)
       ↓
Kafka Producer (Avro serialization, Schema Registry validation)
       ↓
Apache Kafka (Topic: raw-weather-data, 3 partitions)
       ↓
Spark Structured Streaming (fastavro deserialization)
       ↓
Bronze Layer (Raw Parquet, partitioned by ingestion_date)
       ↓
Spark Batch: Bronze → Silver (dedup, null handling, range validation)
       ↓
Spark Batch: Silver → Gold (heat index, wind chill, anomaly scores, 49 features)
       ↓
PostgreSQL Star Schema (fact_weather_readings + 3 dimension tables)
       ↓
ML Models (XGBoost classification + LSTM forecasting)
       ↓
Gen AI (Groq LLM reports, anomaly explanations, RAG chatbot, text-to-SQL)
```

### Medallion Architecture

| Layer | Records | Columns | Purpose | Partitioning |
|-------|---------|---------|---------|-------------|
| **Bronze** | 660+ | 22 | Raw data from Kafka (untouched) | `ingestion_date` |
| **Silver** | 660 | 28 | Cleaned, validated, quality flagged | `reading_date` |
| **Gold** | 660 | 49 | Feature-engineered, ML-ready | `reading_date` |

### Star Schema (PostgreSQL)

```
              ┌────────────────┐
              │   dim_time      │
              │   17,544 rows   │
              │   (hourly 2yr)  │
              └───────┬────────┘
                      │
┌──────────────┐      │      ┌───────────────────────┐
│ dim_location  ├──────┼──────┤ fact_weather_readings  │
│ 20 cities     │      │      │ 660+ records            │
│ 6 regions     │      │      │ 24 measurements         │
└──────────────┘      │      └───────────────────────┘
              ┌───────┴────────┐
              │dim_weather_type │
              │ 15 conditions   │
              └────────────────┘
```

---

## 🤖 ML Models

### Model Performance

| Model | Task | Key Metric | Value |
|-------|------|-----------|-------|
| **XGBoost** | Extreme weather classification | F1 Score | 1.0000 |
| **XGBoost (Optuna-tuned)** | Same, with optimized hyperparameters | F1 Score | 1.0000 |
| **LSTM** | Temperature forecasting | MAE | 0.0393 |
| **LSTM** | Temperature forecasting | RMSE | 0.0638 |

### Features Used (24 for XGBoost)

Temperature (°F, °C), humidity, pressure, wind speed/direction, precipitation, visibility, cloud cover, heat index, wind chill, temperature anomaly, anomaly score, city statistics (avg, min, max, stddev), hour of day, day of week, month, is_daytime, latitude, longitude.

### Explainability (SHAP)

SHAP values generated for every prediction, showing which features contributed most to the extreme weather classification. Plots saved to `ml/plots/`.

---

## 🧠 Gen AI Integration

| Feature | Technology | What It Does |
|---------|-----------|-------------|
| **Weather Reports** | Groq (Llama 3.1) | ML predictions → Natural language weather intelligence reports |
| **Anomaly Explainer** | Groq (Llama 3.1) | Detects anomalies → Explains WHY in plain English with risks |
| **RAG Chatbot** | ChromaDB + Groq | User asks questions → Retrieves from vector DB → Grounded answer |
| **Text-to-SQL** | Groq + PostgreSQL | English question → SQL query → Execute → Natural language answer |

### Example Interactions

**Report Generator:**
> "Current conditions in Phoenix, AZ show mild weather with a temperature of 71.4°F and low humidity at 32%. No extreme weather conditions detected. Conditions are favorable for outdoor activities."

**RAG Chatbot:**
> ❓ "Which city has the highest temperature?"
> 🤖 "Based on available data, Honolulu, HI has the highest temperature at 77.99°F, followed by Miami, FL at 73.49°F."

**Text-to-SQL:**
> ❓ "What is the average temperature for each city?"
> 📝 SQL: `SELECT l.city, ROUND(AVG(f.temperature_fahrenheit)::numeric, 1) FROM climate_warehouse.fact_weather_readings f JOIN climate_warehouse.dim_location l ON f.location_key = l.location_key GROUP BY l.city ORDER BY avg DESC LIMIT 20`

---

## 📊 Docker Services

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| zookeeper | confluentinc/cp-zookeeper:7.5.0 | 2181 | Kafka cluster management |
| kafka | confluentinc/cp-kafka:7.5.0 | 9092 | Message broker |
| schema-registry | confluentinc/cp-schema-registry:7.5.0 | 8081 | Avro schema enforcement |
| kafka-ui | provectuslabs/kafka-ui:latest | 8888 | Web dashboard for Kafka |
| spark-master | bitnamilegacy/spark:3.5.1 | 8090, 7077 | Spark job coordinator |
| spark-worker | bitnamilegacy/spark:3.5.1 | — | Spark processing |
| postgres | postgres:15 | 5432 | Airflow DB + Data warehouse |
| redis | redis:7-alpine | 6379 | Airflow task broker |
| airflow-webserver | apache/airflow:2.8.1 | 8085 | Pipeline monitoring UI |
| airflow-scheduler | apache/airflow:2.8.1 | — | DAG scheduling |
| airflow-worker | apache/airflow:2.8.1 | — | Task execution |

---

## 📅 Implementation Roadmap

| Week | Focus | Status | Key Deliverables |
|------|-------|--------|-----------------|
| **1** | Foundation & Kafka | ✅ Done | Docker Compose, Kafka cluster, topics, producer/consumer |
| **2** | Data Ingestion | ✅ Done | Avro schemas, Schema Registry, production Kafka producer |
| **3** | Spark Processing | ✅ Done | Structured Streaming, Medallion Architecture (Bronze/Silver/Gold) |
| **4** | Warehouse & Airflow | ✅ Done | PostgreSQL star schema, Airflow DAGs, warehouse loader |
| **5** | ML Models & MLflow | ✅ Done | XGBoost, LSTM, Optuna, SHAP, MLflow tracking |
| **6** | Gen AI Integration | ✅ Done | Report generator, anomaly explainer, RAG chatbot, text-to-SQL |
| **7** | API & Dashboard | 🔲 Next | FastAPI endpoints, Streamlit dashboard |
| **8** | GCP Deployment & CI/CD | 🔲 Planned | GCS, BigQuery, GKE, Terraform, GitHub Actions, Grafana |

---

## ☁️ GCP Production Architecture (Week 8)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    GOOGLE CLOUD PLATFORM                                  │
│                                                                           │
│   Data Lake: Google Cloud Storage (GCS)                                  │
│     ├── gs://climate-bronze/  → Raw Parquet from Kafka Connect           │
│     ├── gs://climate-silver/  → Cleaned & validated                      │
│     └── gs://climate-gold/    → Feature-engineered, ML-ready             │
│                                                                           │
│   Data Warehouse: Google BigQuery                                        │
│     ├── climate_warehouse.fact_weather_readings                          │
│     ├── climate_warehouse.dim_location                                   │
│     ├── climate_warehouse.dim_time                                       │
│     └── climate_warehouse.dim_weather_type                               │
│                                                                           │
│   ML Serving: Vertex AI Endpoints (auto-scaling)                         │
│     ├── XGBoost model endpoint                                           │
│     └── LSTM model endpoint                                              │
│                                                                           │
│   Container Orchestration: Google Kubernetes Engine (GKE)                 │
│     ├── Kafka + Zookeeper + Schema Registry pods                         │
│     ├── Spark Master + Worker pods                                       │
│     ├── Airflow pods                                                     │
│     ├── FastAPI + Streamlit pods                                         │
│     └── Monitoring (Prometheus + Grafana) pods                           │
│                                                                           │
│   CI/CD: GitHub Actions → Artifact Registry → GKE                        │
│   IaC: Terraform (main.tf, variables.tf, outputs.tf)                    │
│   Monitoring: Prometheus + Grafana dashboards                            │
└──────────────────────────────────────────────────────────────────────────┘
```

### GCP Deployment Commands (Week 8)

```bash
# 1. Set up GCP infrastructure with Terraform
cd infrastructure/terraform
terraform init
terraform plan
terraform apply

# 2. Build & push Docker images to Artifact Registry
bash scripts/build_and_push.sh

# 3. Deploy to GKE
kubectl apply -f infrastructure/kubernetes/

# 4. Verify deployment
kubectl get pods -n climate-platform
```

---

## 🎓 Why This Project Stands Out

- **End-to-end pipeline**: From raw API data → Kafka → Spark → ML → Gen AI → SQL analytics
- **Production-grade**: Avro schemas, dead letter queues, data quality validation, MLflow tracking
- **Real data**: 20 US cities with real OpenWeatherMap data, not synthetic/mock data
- **Modern stack**: Kafka streaming + Spark + XGBoost/LSTM + Groq LLM + ChromaDB RAG
- **Explainable AI**: SHAP values show WHY the model predicted extreme weather
- **Gen AI powered**: Natural language reports, anomaly explanations, chatbot, text-to-SQL
- **Orchestrated**: Airflow DAGs automate the entire pipeline
- **49 ML features**: Heat index, wind chill, anomaly scores, time features, city statistics
- **Cloud-ready**: Designed for GCP deployment (GCS, BigQuery, GKE, Vertex AI, Terraform)

---

## 🔑 Environment Variables

```env
# Weather API
OPENWEATHER_API_KEY=your_key_here

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
SCHEMA_REGISTRY_URL=http://localhost:8081

# Gen AI
GROQ_API_KEY=your_groq_key_here

# MLflow
MLFLOW_TRACKING_URI=file:./mlruns

# PostgreSQL (local warehouse)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow
POSTGRES_DB=airflow

# GCP Configuration (for Week 8 deployment)
GCP_PROJECT_ID=your_gcp_project_id
GCP_REGION=us-central1
GCS_BUCKET_BRONZE=climate-bronze
GCS_BUCKET_SILVER=climate-silver
GCS_BUCKET_GOLD=climate-gold
BIGQUERY_DATASET=climate_warehouse
```

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

*Built with ❤️ for climate resilience*
