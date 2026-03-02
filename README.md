# 🌍 Climate Intelligence Platform for Extreme Weather Prediction

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Apache Kafka](https://img.shields.io/badge/Apache%20Kafka-7.5-red.svg)](https://kafka.apache.org)
[![Apache Spark](https://img.shields.io/badge/Apache%20Spark-3.5.1-orange.svg)](https://spark.apache.org)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED.svg)](https://docker.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST%20API-009688.svg)](https://fastapi.tiangolo.com)
[![Groq](https://img.shields.io/badge/Groq%20LLM-Gen%20AI-green.svg)](https://groq.com)
[![GCP](https://img.shields.io/badge/GCP-Cloud%20Deploy-4285F4.svg)](https://cloud.google.com)
[![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC.svg)](https://terraform.io)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> A production-grade, end-to-end climate intelligence platform that ingests real-time weather data for **80+ cities across 6 continents**, processes it through a medallion data lake using Apache Spark, predicts extreme weather events using XGBoost & LSTM, serves predictions via FastAPI, provides Gen AI-powered insights via Groq LLM, and deploys to Google Cloud Platform with Terraform — orchestrated with Apache Airflow and containerized with Docker.

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
- [FastAPI Documentation](#-fastapi-documentation)
- [Streamlit Dashboard](#-streamlit-dashboard)
- [GCP Deployment](#-gcp-deployment)
- [CI/CD Pipeline](#-cicd-pipeline)
- [Implementation Roadmap](#-implementation-roadmap)
- [License](#-license)

---

## 🎯 Overview

### The Problem
Extreme weather events (heatwaves, floods, hurricanes, storms) are increasing in frequency and severity worldwide. Early prediction can save lives, reduce economic damage, and help communities prepare. Current systems often lack real-time processing, explainability, and accessible interfaces for non-technical users.

### The Solution
This platform combines **real-time data engineering**, **machine learning**, and **generative AI** to:
- Ingest live weather streams from **80+ global cities across 6 continents** via Apache Kafka with Avro schema validation
- Process data using Apache Spark (batch + streaming) through a **Medallion Architecture**
- Predict extreme weather events using an ensemble of **XGBoost + LSTM** models
- Serve predictions and data through a **FastAPI REST API** with 10+ endpoints
- Visualize insights on an interactive **Streamlit dashboard** with maps, charts, and AI chat
- Generate human-readable weather intelligence reports using **Groq LLM (Llama 3.1)**
- Allow users to query climate data in natural language via a **RAG-powered chatbot**
- Deploy to **Google Cloud Platform** using Terraform, Cloud Run, BigQuery, and GCS
- Automate testing and deployment with **GitHub Actions CI/CD**
- Orchestrate the entire pipeline with **Apache Airflow**

### Who Is This For?
- Emergency response agencies needing early warning systems
- Insurance companies assessing global climate risk
- Researchers studying extreme weather patterns worldwide
- City planners building climate-resilient infrastructure

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                        │
│          OpenWeatherMap API (80+ Cities, 6 Continents, Real-Time)             │
│                                                                               │
│   🌎 North America (15)  │  🌍 Europe (18)      │  🌏 Asia (20)             │
│   🌎 South America (8)   │  🌍 Africa (10)      │  🌏 Oceania (5)           │
│                           │                       │  🌏 Arctic/Extreme (4)    │
└─────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                  INGESTION LAYER (Real-Time Streaming)                         │
│                                                                               │
│   Python Kafka Producer (Avro Serialization, 80+ cities)                     │
│     └──→ Apache Kafka Broker                                                 │
│            ├── Topic: raw-weather-data (3 partitions)                        │
│            ├── Topic: weather-alerts (2 partitions)                          │
│            └── Topic: weather-events                                         │
│                                                                               │
│   Confluent Schema Registry (Avro) ── Data contract enforcement              │
│   Kafka UI (http://localhost:8888) ── Visual topic monitoring                │
└─────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│               PROCESSING LAYER (Batch + Stream)                               │
│                                                                               │
│   Spark Structured Streaming (with fastavro deserialization)                 │
│     └── Kafka (Avro) → Bronze Layer (real-time, 30s trigger)                │
│                                                                               │
│   Spark Batch Jobs (Medallion Architecture)                                  │
│     ├── Bronze → Silver : Deduplication, null handling, validation           │
│     ├── Silver → Gold   : Heat index, wind chill, anomaly scores,           │
│     │                     extreme weather flags, time features (49 cols)     │
│     └── Gold  → PostgreSQL: Star schema dimensional warehouse                │
│                                                                               │
│   Apache Airflow ── DAG orchestration (http://localhost:8085)                │
│     └── Pure pandas-based tasks (no Java/Spark dependency in Airflow)        │
└─────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        STORAGE LAYER                                          │
│                                                                               │
│   Local Data Lake (Parquet, Medallion Architecture)                          │
│     ├── data/bronze/  → Raw Parquet (as received from Kafka)                 │
│     ├── data/silver/  → Cleaned, validated, deduplicated                     │
│     └── data/gold/    → 49 features, ML-ready                               │
│                                                                               │
│   PostgreSQL Data Warehouse (Star Schema)                                    │
│     ├── Fact: fact_weather_readings (660+ records per cycle)                 │
│     ├── Dim:  dim_location (80+ cities with countries & continents)          │
│     ├── Dim:  dim_time (hourly granularity)                                  │
│     └── Dim:  dim_weather_type (15+ weather conditions)                      │
└─────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         ML / AI LAYER                                         │
│                                                                               │
│   XGBoost Classifier                                                         │
│     ├── Extreme weather classification (F1: 1.0)                             │
│     ├── SHAP explainability (feature importance plots)                       │
│     └── Optuna hyperparameter tuning (50 trials)                             │
│                                                                               │
│   PyTorch LSTM                                                               │
│     ├── Temperature time-series forecasting (MAE: 0.039)                     │
│     ├── 7-step sequence window, 2-layer architecture                         │
│     └── Training/validation loss tracking                                    │
│                                                                               │
│   MLflow (http://localhost:5555)                                             │
│     ├── Experiment tracking (parameters, metrics, artifacts)                 │
│     ├── Model versioning & comparison                                        │
│     └── SHAP plots, confusion matrix, loss curves logged                     │
└─────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                   GEN AI LAYER (Groq LLM - Llama 3.1)                        │
│                                                                               │
│   Weather Report Generator                                                   │
│     └── ML predictions → Groq LLM → Natural language reports                │
│                                                                               │
│   Anomaly Explanation Engine                                                 │
│     └── High anomaly scores → LLM explains WHY in plain English             │
│                                                                               │
│   RAG Climate Chatbot (ChromaDB + Groq)                                      │
│     └── User question → Vector search → LLM generates grounded answer       │
│                                                                               │
│   Text-to-SQL Engine                                                         │
│     └── Natural language → SQL → PostgreSQL → Natural language answer        │
└─────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                                           │
│                                                                               │
│   FastAPI REST API (http://localhost:8000)                                    │
│     ├── GET  /api/stats         → Dashboard metrics                          │
│     ├── GET  /api/cities        → All 80+ cities with weather                │
│     ├── GET  /api/weather/{city}→ Detailed city weather                      │
│     ├── GET  /api/extreme       → Extreme weather events + reasons           │
│     ├── GET  /api/predictions   → XGBoost risk levels (HIGH/MED/LOW)         │
│     ├── GET  /api/forecast/{city}→ 24-hour LSTM temperature forecast         │
│     ├── GET  /api/anomalies     → Anomalous cities above threshold           │
│     ├── GET  /api/regions       → Weather stats by continent/region          │
│     └── POST /api/chat          → AI chatbot (RAG, SQL, Report, Anomaly)     │
│                                                                               │
│   Streamlit Dashboard (http://localhost:8501)                                │
│     ├── 🗺️ Interactive Weather Map (all 80+ cities)                          │
│     ├── 🏙️ City Monitor (cards + deep dive + 24h forecast)                   │
│     ├── 🤖 ML Predictions (risk table + scatter plot + alerts)               │
│     ├── 📊 Regional Analysis (continent comparison charts)                   │
│     └── 🧠 AI Chat (RAG/SQL/Report/Anomaly modes via API)                   │
└─────────────────────────────┬────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                    GOOGLE CLOUD PLATFORM (Production)                          │
│                                                                               │
│   Data Lake: Google Cloud Storage (GCS)                                      │
│     ├── gs://climate-bronze/  → Raw Parquet                                  │
│     ├── gs://climate-silver/  → Cleaned & validated                          │
│     └── gs://climate-gold/    → Feature-engineered, ML-ready                 │
│                                                                               │
│   Data Warehouse: Google BigQuery                                            │
│     └── climate_warehouse (fact + 3 dimension tables)                        │
│                                                                               │
│   Serving: Cloud Run (auto-scaling, serverless)                              │
│     ├── climate-api (FastAPI backend)                                        │
│     └── climate-dashboard (Streamlit frontend)                               │
│                                                                               │
│   Docker Registry: Artifact Registry                                         │
│   Infrastructure: Terraform (IaC)                                            │
│   CI/CD: GitHub Actions (lint → test → build → deploy)                       │
│   Monitoring: Uptime checks + Cloud Monitoring                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Category | Technologies | Purpose |
|----------|-------------|---------|
| **Data Ingestion** | Apache Kafka, Confluent Schema Registry (Avro), Kafka UI | Real-time streaming with schema validation |
| **Stream Processing** | Spark Structured Streaming, fastavro | Avro deserialization, Kafka → Bronze in real-time |
| **Batch Processing** | Apache Spark (PySpark), Pandas | Medallion transformations (Bronze → Silver → Gold) |
| **Orchestration** | Apache Airflow (CeleryExecutor) | DAG-based pipeline scheduling & monitoring |
| **Data Lake** | Local Parquet files (Medallion Architecture) | Partitioned by ingestion_date / reading_date |
| **Data Warehouse** | PostgreSQL (Star Schema) | Fact + dimension tables for SQL analytics |
| **Traditional ML** | XGBoost, Scikit-learn, SHAP, Optuna | Classification, explainability, hyperparameter tuning |
| **Deep Learning** | PyTorch (LSTM) | Time-series temperature forecasting |
| **ML Ops** | MLflow | Experiment tracking, model versioning, artifact logging |
| **Gen AI / LLM** | Groq API (Llama 3.1), ChromaDB | RAG chatbot, report generation, text-to-SQL |
| **Backend API** | FastAPI, Uvicorn | REST API with 10+ endpoints, Swagger docs |
| **Frontend** | Streamlit, Plotly | Interactive dashboard with maps, charts, AI chat |
| **Containerization** | Docker, Docker Compose | 11+ services orchestrated locally |
| **Cloud Platform** | GCP (GCS, BigQuery, Cloud Run, Artifact Registry) | Production deployment |
| **Infrastructure as Code** | Terraform | Automated GCP resource provisioning |
| **CI/CD** | GitHub Actions | Automated lint → test → build → deploy pipeline |
| **Monitoring** | GCP Cloud Monitoring, Uptime Checks | API health monitoring & alerting |
| **Languages** | Python 3.11, SQL, YAML, HCL | Core development |

---

## ✨ Features

### Data Engineering
- **Real-time ingestion** from OpenWeatherMap API for **80+ global cities** via Kafka
- **Avro schema enforcement** with Confluent Schema Registry
- **Medallion data lake** (Bronze → Silver → Gold) with Parquet partitioning
- **Star schema warehouse** in PostgreSQL (fact + 3 dimension tables)
- **Data quality validation** — range checks, null handling, deduplication
- **Airflow DAGs** orchestrating the full pipeline with pure pandas (no Java dependency)

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
- **Smart 3-tier answer system** — Direct DataFrame → SQL → RAG fallback

### REST API (FastAPI)
- **10+ endpoints** for weather data, ML predictions, and AI chatbot
- **Interactive Swagger docs** at `/docs`
- **City detail lookup** with temperature, humidity, wind, anomaly analysis
- **Risk-level predictions** (🔴 HIGH / 🟡 MODERATE / 🟢 LOW)
- **24-hour temperature forecast** per city
- **Regional/continental analytics**
- **CORS-enabled** for cross-origin frontend access

### Interactive Dashboard (Streamlit)
- **5-tab interface**: Weather Map, City Monitor, ML Predictions, Regional Analysis, AI Chat
- **Interactive world map** with color-coded temperature dots (Plotly)
- **Temperature comparison** horizontal bar charts
- **City deep dive** with 24-hour forecast line chart
- **ML risk assessment table** with scatter plot visualization
- **Regional bar charts** comparing continents
- **AI chatbot** connected to FastAPI backend

### Infrastructure
- **11+ Docker containers** managed via Docker Compose
- **Kafka + Zookeeper + Schema Registry** for streaming infrastructure
- **Spark Master + Worker** for distributed processing
- **Airflow (Webserver + Scheduler + Worker)** for orchestration
- **PostgreSQL + Redis** for metadata and task queuing

### Google Cloud Platform (Production)
- **Google Cloud Storage (GCS)** — Cloud data lake (Bronze/Silver/Gold buckets)
- **Google BigQuery** — Cloud data warehouse with star schema
- **Cloud Run** — Serverless FastAPI + Streamlit deployment (auto-scaling)
- **Artifact Registry** — Docker image storage
- **Terraform** — Infrastructure as Code for all GCP resources
- **GitHub Actions** — CI/CD pipeline (lint → test → build → deploy)
- **Cloud Monitoring** — Uptime health checks & alerting

---

## 🌐 Global City Coverage

| Continent | Cities | Count | Examples |
|-----------|--------|-------|----------|
| **North America** | US, Canada, Mexico, Cuba | 15 | New York, Toronto, Mexico City |
| **Europe** | UK, France, Germany, + 15 more | 18 | London, Paris, Berlin, Moscow |
| **Asia** | Japan, China, India, + 17 more | 20 | Tokyo, Beijing, Mumbai, Dubai |
| **Africa** | Egypt, Nigeria, Kenya, + 7 more | 10 | Cairo, Lagos, Nairobi, Cape Town |
| **South America** | Brazil, Argentina, + 6 more | 8 | São Paulo, Buenos Aires, Lima |
| **Oceania** | Australia, New Zealand, Pacific | 5 | Sydney, Auckland, Honolulu |
| **Arctic/Extreme** | Alaska, Iceland, Siberia, Patagonia | 4 | Anchorage, Reykjavik, Ushuaia |
| **Total** | **35 countries** | **80** | **6 continents covered** |

---

## 📁 Project Structure

```
Climate-Intelligence-Platform-for-Extreme-Weather-Prediction/
│
├── README.md                              # This file
├── docker-compose.yml                     # 11+ services (one command startup)
├── Dockerfile.api                         # FastAPI container
├── Dockerfile.dashboard                   # Streamlit container
├── requirements-api.txt                   # API dependencies
├── requirements-dashboard.txt             # Dashboard dependencies
├── .env                                   # API keys (git-ignored)
├── .env.example                           # Environment template
├── .gitignore                             # Git ignore rules
│
├── data_ingestion/                        # === KAFKA PRODUCERS ===
│   ├── kafka_producer_openweather.py      # Production Avro producer (80 global cities)
│   ├── kafka_producer.py                  # Test producer (mock data)
│   ├── kafka_consumer.py                  # Test consumer
│   ├── kafka_consumer_test.py             # Avro consumer for verification
│   └── avro_schemas/
│       ├── weather_reading.avsc           # Avro schema (20 fields)
│       └── weather_alert.avsc             # Alert schema
│
├── data_processing/                       # === SPARK JOBS ===
│   ├── spark_streaming_bronze.py          # Kafka → Bronze (Avro → Parquet)
│   ├── spark_batch_silver.py              # Bronze → Silver (cleaning)
│   ├── spark_batch_gold.py                # Silver → Gold (49 features)
│   └── view_data.py                       # Data inspection utility
│
├── orchestration/                         # === AIRFLOW ===
│   ├── dags/
│   │   ├── climate_pipeline_dag.py        # Main pipeline DAG (pandas-based)
│   │   └── load_warehouse.py              # Gold → PostgreSQL loader
│   └── sql/
│       └── create_warehouse.sql           # Star schema DDL
│
├── ml/                                    # === MACHINE LEARNING ===
│   ├── train_xgboost.py                   # XGBoost + SHAP + MLflow
│   ├── train_lstm.py                      # PyTorch LSTM + MLflow
│   ├── hyperparameter_tuning.py           # Optuna (50 trials) + MLflow
│   ├── models/
│   │   └── lstm_model.pth                 # Saved LSTM weights
│   └── plots/
│       ├── confusion_matrix.png           # XGBoost confusion matrix
│       ├── shap_summary.png               # SHAP importance (dots)
│       ├── shap_importance.png            # SHAP importance (bars)
│       ├── lstm_training_loss.png         # LSTM loss curves
│       └── lstm_predictions.png           # Predicted vs actual
│
├── genai/                                 # === GEN AI (Groq LLM) ===
│   ├── chatbot_app.py                     # Streamlit chatbot (standalone)
│   ├── report_generator.py                # Predictions → natural language
│   ├── anomaly_explainer.py               # Anomaly → LLM explanation
│   ├── rag_pipeline.py                    # ChromaDB + Groq RAG
│   └── text_to_sql.py                     # English → SQL → answer
│
├── api/                                   # === FASTAPI BACKEND ===
│   ├── __init__.py
│   └── main.py                            # REST API (10+ endpoints)
│
├── dashboard/                             # === STREAMLIT DASHBOARD ===
│   └── app.py                             # 5-tab interactive dashboard
│
├── data/                                  # === DATA LAKE (git-ignored) ===
│   ├── bronze/                            # Raw Parquet from Kafka
│   ├── silver/                            # Cleaned Parquet
│   ├── gold/                              # Feature-engineered (49 columns)
│   └── checkpoints/                       # Spark streaming checkpoints
│
├── infrastructure/                        # === GCP DEPLOYMENT ===
│   └── terraform/
│       ├── main.tf                        # GCS, BigQuery, Cloud Run, Artifact Registry
│       ├── variables.tf                   # Configurable parameters
│       ├── outputs.tf                     # Resource URLs & IDs
│       └── terraform.tfvars.example       # Template for variables
│
├── .github/                               # === CI/CD ===
│   └── workflows/
│       └── ci-cd.yml                      # Lint → Test → Build → Deploy
│
├── tests/                                 # === TESTS ===
│   └── test_suite.py                      # Pipeline, ML, API, DB tests
│
├── mlruns/                                # === MLFLOW (git-ignored) ===
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

### Quick Start

```powershell
# 1. Clone the repository
git clone https://github.com/yourusername/Climate-Intelligence-Platform-for-Extreme-Weather-Prediction.git
cd Climate-Intelligence-Platform-for-Extreme-Weather-Prediction

# 2. Create virtual environment
python -m venv venv
.\venv\Scripts\Activate    # Windows
# source venv/bin/activate  # Mac/Linux

# 3. Install dependencies
pip install confluent-kafka httpx requests python-dotenv fastavro
pip install pyspark==3.5.1 psycopg2-binary
pip install xgboost scikit-learn mlflow shap optuna torch matplotlib seaborn
pip install groq chromadb sentence-transformers
pip install fastapi uvicorn streamlit plotly pandas pyarrow

# 4. Configure environment
copy .env.example .env
# Edit .env with your OPENWEATHER_API_KEY, GROQ_API_KEY

# 5. Set Java environment (Windows)
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
$env:HADOOP_HOME = "C:\hadoop"
$env:PYSPARK_PYTHON = "python"
$env:PYSPARK_DRIVER_PYTHON = "python"

# 6. Start all Docker services (11 containers)
docker-compose up -d

# 7. Verify all services
docker-compose ps
```

### Access Points (Local)

| Service | URL | Description |
|---------|-----|-------------|
| **FastAPI Docs** | http://localhost:8000/docs | Interactive API documentation (Swagger) |
| **Dashboard** | http://localhost:8501 | Streamlit interactive dashboard |
| **Kafka UI** | http://localhost:8888 | Topic monitoring, message browser |
| **Schema Registry** | http://localhost:8081 | Avro schema management |
| **Spark Master** | http://localhost:8090 | Spark job monitoring |
| **Airflow** | http://localhost:8085 | Pipeline orchestration (admin/admin) |
| **MLflow** | http://localhost:5555 | ML experiment tracking |
| **PostgreSQL** | localhost:5432 | Data warehouse (airflow/airflow) |

### Run the Full Pipeline

```powershell
# Terminal 1: Start Kafka producer (ingests 80 global cities)
python data_ingestion/kafka_producer_openweather.py

# Terminal 2: Start Spark streaming (Kafka → Bronze)
python data_processing/spark_streaming_bronze.py

# Terminal 3: Run batch processing
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

# Terminal 4: Start FastAPI backend
python api/main.py

# Terminal 5: Start Streamlit dashboard
streamlit run dashboard/app.py
```

---

## 🔄 Pipeline Deep Dive

### Data Flow

```
OpenWeatherMap API (80 cities, 6 continents, every 60 seconds)
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
FastAPI REST API (10+ endpoints serving data, predictions, AI chat)
       ↓
Streamlit Dashboard (5 tabs: Map, Cities, ML, Regions, AI Chat)
       ↓
Gen AI (Groq LLM reports, anomaly explanations, RAG chatbot, text-to-SQL)
```

### Medallion Architecture

| Layer | Purpose | Partitioning |
|-------|---------|-------------|
| **Bronze** | Raw data from Kafka (untouched) | `ingestion_date` |
| **Silver** | Cleaned, validated, quality flagged | `reading_date` |
| **Gold** | Feature-engineered, ML-ready (49 columns) | `reading_date` |

### Star Schema (PostgreSQL)

```
              ┌─────────────────┐
              │    dim_time      │
              │  (hourly grain)  │
              └───────┬─────────┘
                      │
┌───────────────┐     │     ┌───────────────────────┐
│ dim_location   ├─────┼─────┤ fact_weather_readings  │
│ 80+ cities     │     │     │ 24 measurements         │
│ 35 countries   │     │     │ per reading             │
│ 6 continents   │     │     └───────────────────────┘
└───────────────┘     │
              ┌───────┴─────────┐
              │dim_weather_type  │
              │ 15+ conditions   │
              └─────────────────┘
```

---

## 🤖 ML Models

### Model Performance

| Model | Task | Key Metric | Value |
|-------|------|-----------|-------|
| **XGBoost** | Extreme weather classification | F1 Score | 1.0000 |
| **XGBoost (Optuna-tuned)** | Optimized hyperparameters | F1 Score | 1.0000 |
| **LSTM** | Temperature forecasting | MAE | 0.0393 |
| **LSTM** | Temperature forecasting | RMSE | 0.0638 |

### Explainability (SHAP)

SHAP values generated for every prediction, showing which features contributed most to the extreme weather classification. Plots saved to `ml/plots/` and logged to MLflow.

---

## 🧠 Gen AI Integration

| Feature | Technology | What It Does |
|---------|-----------|-------------|
| **Weather Reports** | Groq (Llama 3.1) | ML predictions → Natural language weather intelligence |
| **Anomaly Explainer** | Groq (Llama 3.1) | Detects anomalies → Explains WHY with risks |
| **RAG Chatbot** | ChromaDB + Groq | User asks → Vector search → Grounded answer |
| **Text-to-SQL** | Groq + PostgreSQL | English → SQL → Execute → Natural language answer |
| **Smart Routing** | 3-tier system | DataFrame (instant) → SQL → RAG fallback |

---

## 🔌 FastAPI Documentation

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check & API status |
| GET | `/api/stats` | Dashboard summary metrics |
| GET | `/api/cities` | All 80+ cities with current weather |
| GET | `/api/weather/{city}` | Detailed weather for a specific city |
| GET | `/api/extreme` | Extreme weather events with reasons |
| GET | `/api/predictions` | ML risk levels for all cities |
| GET | `/api/forecast/{city}` | 24-hour temperature forecast |
| GET | `/api/anomalies?threshold=1.5` | Cities with anomaly scores above threshold |
| GET | `/api/regions` | Weather statistics by continent/region |
| POST | `/api/chat` | AI chatbot (supports RAG, SQL, Report, Anomaly modes) |

### Example Responses

**GET /api/weather/Tokyo**
```json
{
  "city": "Tokyo",
  "state": null,
  "temperature": { "fahrenheit": 68.4, "celsius": 20.2, "heat_index": 68.4 },
  "conditions": { "weather": "Clouds", "humidity_percent": 65.0, "wind_speed_mph": 8.2 },
  "analysis": { "is_extreme_weather": false, "anomaly_score": 0.42, "risk_level": "🟢 LOW" }
}
```

**POST /api/chat**
```json
{
  "question": "Which city has the highest temperature?",
  "mode": "auto"
}
// Response:
{
  "answer": "🔥 Dubai has the highest temperature at 105.2°F...",
  "mode": "rag"
}
```

---

## 📊 Streamlit Dashboard

| Tab | Features |
|-----|----------|
| 🗺️ **Weather Map** | Interactive world map with color-coded temperature dots, temperature bar chart |
| 🏙️ **City Monitor** | City cards with live weather, deep-dive selector, 24-hour forecast chart |
| 🤖 **ML Predictions** | Risk summary (HIGH/MED/LOW), predictions table, temperature vs anomaly scatter |
| 📊 **Regional Analysis** | Continental temperature comparison, humidity vs wind scatter, region table |
| 🧠 **AI Chat** | Quick action buttons, 4 AI modes (RAG/SQL/Report/Anomaly), chat history |

---

## ☁️ GCP Deployment

### Architecture

| GCP Service | Replaces | Purpose |
|-------------|----------|---------|
| **Cloud Storage (GCS)** | Local Parquet files | Cloud data lake (Bronze/Silver/Gold) |
| **BigQuery** | PostgreSQL | Cloud data warehouse with star schema |
| **Cloud Run** | Local Docker | Serverless API + Dashboard deployment |
| **Artifact Registry** | Local Docker images | Container image storage |
| **Terraform** | Manual setup | Infrastructure as Code |
| **Cloud Monitoring** | Manual checks | Uptime & health monitoring |

### Deploy with Terraform

```bash
# 1. Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 2. Create service account
gcloud iam service-accounts create terraform-sa --display-name="Terraform"
gcloud projects add-iam-policy-binding PROJECT_ID --member="serviceAccount:terraform-sa@PROJECT.iam.gserviceaccount.com" --role="roles/editor"

# 3. Deploy
cd infrastructure/terraform
terraform init
terraform plan
terraform apply    # Type 'yes'

# 4. Push Docker images
gcloud auth configure-docker us-central1-docker.pkg.dev
docker build -t us-central1-docker.pkg.dev/PROJECT/climate-platform/climate-api:latest -f Dockerfile.api .
docker push us-central1-docker.pkg.dev/PROJECT/climate-platform/climate-api:latest
```

### Resources Created by Terraform

- 3 GCS buckets (bronze, silver, gold)
- BigQuery dataset with 4 tables
- Artifact Registry repository
- 2 Cloud Run services (API + Dashboard)
- Uptime monitoring check

---

## 🔄 CI/CD Pipeline

```
git push to main
       │
       ▼
┌─────────────┐    ┌──────────┐    ┌───────────────┐    ┌────────────────┐
│ 🔍 LINT      │───→│ 🧪 TEST   │───→│ 🐳 BUILD      │───→│ 🚀 DEPLOY      │
│ flake8       │    │ pytest   │    │ Docker images │    │ Cloud Run      │
│ black        │    │ imports  │    │ Push to GAR   │    │ API + Dashboard│
└─────────────┘    └──────────┘    └───────────────┘    └────────────────┘
```

### GitHub Secrets Required

| Secret | Description |
|--------|-------------|
| `GCP_PROJECT_ID` | Google Cloud project ID |
| `GCP_SA_KEY` | Service account JSON key |
| `GROQ_API_KEY` | Groq API key for LLM |

---

## 📊 Docker Services

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| zookeeper | confluentinc/cp-zookeeper:7.5.0 | 2181 | Kafka cluster management |
| kafka | confluentinc/cp-kafka:7.5.0 | 9092 | Message broker |
| schema-registry | confluentinc/cp-schema-registry:7.5.0 | 8081 | Avro schema enforcement |
| kafka-ui | provectuslabs/kafka-ui:latest | 8888 | Web dashboard for Kafka |
| spark-master | bitnamilegacy/spark:3.5.1 | 8090 | Spark job coordinator |
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
| **7** | API & Dashboard | ✅ Done | FastAPI (10+ endpoints), Streamlit (5-tab dashboard) |
| **8** | GCP & CI/CD | ✅ Done | Terraform, Dockerfiles, GitHub Actions, Cloud Run |

---

## 🎓 Why This Project Stands Out

- **End-to-end pipeline**: From raw API data → Kafka → Spark → ML → Gen AI → REST API → Dashboard
- **Global scale**: 80+ cities across 6 continents, not just US data
- **Production-grade**: Avro schemas, data quality validation, MLflow tracking, CI/CD pipeline
- **Real data**: Live OpenWeatherMap data from 35 countries
- **Full-stack**: FastAPI backend + Streamlit frontend + PostgreSQL warehouse
- **Modern stack**: Kafka + Spark + XGBoost/LSTM + Groq LLM + ChromaDB RAG
- **Explainable AI**: SHAP values show WHY the model predicted extreme weather
- **Gen AI powered**: 4 modes — RAG chatbot, report generation, anomaly explanation, text-to-SQL
- **Smart answer system**: 3-tier routing (DataFrame → SQL → RAG) for accurate responses
- **Cloud-ready**: GCP deployment with Terraform IaC + GitHub Actions CI/CD
- **Orchestrated**: Airflow DAGs automate the entire pipeline on schedule
- **49 ML features**: Heat index, wind chill, anomaly scores, time features, city statistics

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

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow
POSTGRES_DB=airflow

# GCP (for production deployment)
GCP_PROJECT_ID=your_gcp_project_id
GCP_REGION=us-central1
```

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

*Built with ❤️ for global climate resilience*
