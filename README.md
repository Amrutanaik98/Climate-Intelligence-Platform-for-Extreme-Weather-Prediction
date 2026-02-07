# 🌍 Climate Intelligence Platform for Extreme Weather Prediction

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Apache Kafka](https://img.shields.io/badge/Apache%20Kafka-3.6-red.svg)](https://kafka.apache.org)
[![Apache Spark](https://img.shields.io/badge/Apache%20Spark-3.5-orange.svg)](https://spark.apache.org)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED.svg)](https://docker.com)
[![GCP](https://img.shields.io/badge/GCP-Deployed-4285F4.svg)](https://cloud.google.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> A production-grade, end-to-end climate intelligence platform that ingests real-time weather data, processes it through a medallion data lake, predicts extreme weather events using ML/Deep Learning, and provides Gen AI-powered natural language insights — all deployed on Google Cloud Platform with Docker & Kubernetes.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Features](#features)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Pipeline Deep Dive](#pipeline-deep-dive)
- [ML Models](#ml-models)
- [Gen AI Integration](#gen-ai-integration)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [API Documentation](#api-documentation)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 Overview

### The Problem
Extreme weather events (heatwaves, floods, hurricanes, storms) are increasing in frequency and severity. Early prediction can save lives, reduce economic damage, and help communities prepare. Current systems often lack real-time processing, explainability, and accessible interfaces for non-technical users.

### The Solution
This platform combines **real-time data engineering**, **machine learning**, and **generative AI** to:
- Ingest live weather streams from multiple sources via Apache Kafka
- Process terabytes of climate data using Apache Spark (batch + streaming)
- Predict extreme weather events 24-72 hours in advance using ensemble ML models
- Generate human-readable weather intelligence reports using LLMs
- Allow users to query climate data in natural language via a RAG-powered chatbot

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
│   NOAA API  │  OpenWeatherMap API  │  NASA Satellite  │  Weather CSVs    │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                 INGESTION LAYER (Real-Time Streaming)                     │
│                                                                           │
│   Python Kafka Producers ──→ Apache Kafka (3-Broker Cluster)             │
│                                ├── Topic: raw-weather-data               │
│                                ├── Topic: weather-alerts                 │
│                                └── Topic: satellite-metadata             │
│                                                                           │
│   Confluent Schema Registry (Avro) ── Data contracts & validation        │
│   Kafka Connect ── GCS Sink Connector (raw archival)                     │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│              PROCESSING LAYER (Batch + Stream)                            │
│                                                                           │
│   Spark Structured Streaming                                             │
│     └── Kafka → Bronze Layer (real-time, sub-second latency)             │
│                                                                           │
│   Spark Batch Jobs (Medallion Architecture)                              │
│     ├── Bronze → Silver : Deduplication, null handling, type casting     │
│     ├── Silver → Gold   : Aggregations, feature engineering, indexing    │
│     └── Gold  → BigQuery: Analytics-ready dimensional tables             │
│                                                                           │
│   Great Expectations ── Data quality validation at every layer           │
│   Apache Airflow ── DAG orchestration for all pipelines                  │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       STORAGE LAYER                                       │
│                                                                           │
│   Google Cloud Storage (Data Lake)                                       │
│     ├── gs://climate-bronze/  → Raw Parquet (as received)                │
│     ├── gs://climate-silver/  → Cleaned & validated                      │
│     └── gs://climate-gold/    → Feature-engineered & aggregated          │
│                                                                           │
│   Google BigQuery (Data Warehouse)                                       │
│     ├── Fact: fact_weather_readings, fact_predictions                    │
│     ├── Dim:  dim_location, dim_time, dim_weather_type                  │
│     └── ML:   feature_store_weather                                      │
│                                                                           │
│   PostgreSQL (Application metadata & user state)                         │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        ML / AI LAYER                                      │
│                                                                           │
│   Traditional ML                                                         │
│     ├── XGBoost ── Extreme weather classification                        │
│     ├── SHAP ── Feature importance & explainability                      │
│     └── Optuna ── Hyperparameter optimization                            │
│                                                                           │
│   Deep Learning (PyTorch)                                                │
│     ├── LSTM ── Time-series forecasting (temperature, pressure)          │
│     ├── GRU ── Comparison variant                                        │
│     └── Uncertainty quantification (confidence intervals)                │
│                                                                           │
│   Ensemble                                                               │
│     └── Weighted voting: XGBoost + LSTM combined predictions             │
│                                                                           │
│   MLflow ── Experiment tracking, model versioning, registry              │
│   Vertex AI ── Production model serving (auto-scaling endpoints)         │
│   Evidently AI ── Data drift & model performance monitoring              │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      GEN AI LAYER                                         │
│                                                                           │
│   Natural Language Report Generator                                      │
│     └── Raw predictions → LLM → Human-readable weather intelligence      │
│         Example: "Severe heatwave expected in Phoenix, AZ. Temperatures  │
│         will exceed 115°F over the next 72 hours. Risk level: HIGH."     │
│                                                                           │
│   Anomaly Explanation Engine                                             │
│     └── Model detects anomaly → LLM explains WHY in plain English        │
│                                                                           │
│   RAG-Powered Climate Chatbot                                            │
│     └── User: "What caused the 2024 Texas floods?"                       │
│         → Retrieves from ChromaDB → LLM generates grounded answer        │
│                                                                           │
│   Text-to-SQL Query Engine                                               │
│     └── User: "Show heatwave predictions for California next week"       │
│         → Converts to SQL → Queries BigQuery → Returns natural response  │
│                                                                           │
│   ChromaDB (Vector Store) + Sentence-Transformers (Embeddings)           │
│   LangChain (Orchestration) + Gemini / Claude API (LLM)                 │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                   SERVING & VISUALIZATION                                 │
│                                                                           │
│   FastAPI Backend                                                        │
│     ├── POST /predict       → Weather predictions                        │
│     ├── POST /chat          → Gen AI chatbot                             │
│     ├── GET  /anomalies     → Anomaly explanations                       │
│     ├── GET  /reports       → Generated weather reports                  │
│     └── GET  /health        → Service health check                       │
│                                                                           │
│   Streamlit Dashboard                                                    │
│     ├── Real-time weather map with prediction overlays                   │
│     ├── Historical trend analysis & model accuracy tracker               │
│     ├── Interactive chatbot tab (natural language queries)               │
│     └── Model performance & drift monitoring panel                       │
└──────────────────────┬───────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                  DEPLOYMENT & INFRASTRUCTURE                              │
│                                                                           │
│   Docker ── Every service containerized (12+ Dockerfiles)                │
│   Docker Compose ── Local development (single command startup)           │
│   GKE (Kubernetes) ── Production container orchestration                 │
│   Terraform ── Infrastructure as Code (all GCP resources)                │
│   GitHub Actions ── CI/CD (lint, test, build, deploy)                    │
│   Prometheus + Grafana ── Infrastructure monitoring & alerting           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Category | Technologies | Purpose |
|----------|-------------|---------|
| **Data Ingestion** | Apache Kafka (3-broker), Schema Registry (Avro), Kafka Connect | Real-time streaming ingestion with data contracts |
| **Stream Processing** | Spark Structured Streaming | Sub-second processing from Kafka to data lake |
| **Batch Processing** | Apache Spark (PySpark), Spark SQL | Medallion transformations (Bronze → Silver → Gold) |
| **Orchestration** | Apache Airflow | DAG-based pipeline scheduling & dependency management |
| **Data Quality** | Great Expectations | Automated validation checkpoints at every layer |
| **Data Lake** | Google Cloud Storage (GCS) | Partitioned Parquet files in medallion layers |
| **Data Warehouse** | Google BigQuery | Star schema dimensional model for analytics |
| **Traditional ML** | XGBoost, Scikit-learn, SHAP, Optuna | Classification, explainability, hyperparameter tuning |
| **Deep Learning** | PyTorch (LSTM, GRU) | Time-series forecasting with uncertainty quantification |
| **ML Ops** | MLflow, Evidently AI | Experiment tracking, model registry, drift detection |
| **Model Serving** | Vertex AI Endpoints | Auto-scaling production inference |
| **Gen AI** | Gemini/Claude API, LangChain, ChromaDB | RAG chatbot, report generation, text-to-SQL |
| **Backend API** | FastAPI | High-performance async REST API |
| **Frontend** | Streamlit | Interactive dashboard with real-time visualizations |
| **Containerization** | Docker, Docker Compose | Service isolation & reproducible environments |
| **Cloud Platform** | GCP (GKE, GCS, BigQuery, Vertex AI, Cloud Run) | Production deployment |
| **Infrastructure as Code** | Terraform | Automated GCP resource provisioning |
| **CI/CD** | GitHub Actions | Automated testing, building, and deployment |
| **Monitoring** | Prometheus, Grafana | Infrastructure metrics & alerting |

---

## ✨ Features

### Data Engineering
- **Real-time ingestion** from 4+ weather data sources via Kafka
- **Schema enforcement** with Avro and Schema Registry (backward compatible evolution)
- **Medallion data lake** (Bronze → Silver → Gold) on GCS
- **Star schema** dimensional model in BigQuery
- **Automated data quality** checks with Great Expectations at every layer
- **Airflow DAGs** orchestrating ingestion, processing, training, and monitoring

### Machine Learning
- **Extreme weather classification** (flood, heatwave, storm, hurricane) with XGBoost
- **Time-series forecasting** (temperature, pressure, wind) with LSTM & GRU
- **Ensemble model** combining traditional ML + deep learning
- **Explainability** via SHAP values (know WHY the model predicted an event)
- **Uncertainty quantification** with confidence intervals on every prediction
- **Automated hyperparameter tuning** with Optuna
- **Full experiment tracking** with MLflow (metrics, parameters, artifacts)
- **Model drift detection** with Evidently AI

### Generative AI
- **Natural language weather reports** generated from raw model predictions
- **Anomaly explanation engine** — when models detect something unusual, the LLM explains why
- **RAG-powered chatbot** — ask climate questions grounded in your actual data
- **Text-to-SQL** — query BigQuery using natural language ("Show me all storms in Texas last month")

### Deployment & Operations
- **12+ Dockerized microservices** with Docker Compose for local development
- **Kubernetes (GKE)** manifests for production orchestration
- **Terraform** for all GCP infrastructure as code
- **GitHub Actions CI/CD** with automated lint, test, build, and deploy
- **Prometheus + Grafana** monitoring with custom dashboards

---

## 📁 Project Structure

```
climate-intelligence-platform/
│
├── README.md
├── docker-compose.yml                    # Start everything locally with one command
├── .env.example                          # Environment variable template
├── requirements.txt                      # Python dependencies
├── Makefile                              # Common commands (make build, make test, etc.)
│
├── .github/
│   └── workflows/
│       ├── ci.yml                        # Lint + test on every pull request
│       └── cd.yml                        # Build + deploy on merge to main
│
├── infrastructure/
│   ├── terraform/
│   │   ├── main.tf                       # GCS, BigQuery, GKE, Vertex AI resources
│   │   ├── variables.tf                  # Configurable parameters
│   │   └── outputs.tf                    # Resource IDs & endpoints
│   └── kubernetes/
│       ├── kafka-deployment.yml
│       ├── spark-deployment.yml
│       ├── api-deployment.yml
│       ├── dashboard-deployment.yml
│       └── monitoring-deployment.yml
│
├── ingestion/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── kafka_producer_noaa.py            # NOAA API → Kafka
│   ├── kafka_producer_openweather.py     # OpenWeatherMap API → Kafka
│   ├── kafka_producer_nasa.py            # NASA satellite metadata → Kafka
│   ├── avro_schemas/
│   │   ├── weather_reading.avsc          # Schema for weather observations
│   │   └── weather_alert.avsc           # Schema for severe weather alerts
│   └── kafka_connect/
│       └── gcs_sink_connector.json       # Auto-archive raw messages to GCS
│
├── processing/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── spark_streaming_bronze.py         # Kafka → Bronze (real-time)
│   ├── spark_batch_silver.py             # Bronze → Silver (cleaning)
│   ├── spark_batch_gold.py               # Silver → Gold (feature engineering)
│   ├── spark_to_bigquery.py              # Gold → BigQuery (warehouse load)
│   └── data_quality/
│       └── great_expectations/
│           ├── expectations/
│           │   ├── bronze_suite.json     # Raw data expectations
│           │   ├── silver_suite.json     # Cleaned data expectations
│           │   └── gold_suite.json       # Feature data expectations
│           └── checkpoints/
│               └── weather_checkpoint.yml
│
├── orchestration/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── dags/
│       ├── daily_ingestion_dag.py        # Scheduled data collection
│       ├── batch_processing_dag.py       # Bronze → Silver → Gold → BigQuery
│       ├── model_training_dag.py         # Weekly retraining pipeline
│       └── model_monitoring_dag.py       # Daily drift detection
│
├── ml/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── feature_engineering.py            # Create ML features from Gold data
│   ├── train_xgboost.py                 # XGBoost classifier training
│   ├── train_lstm.py                    # PyTorch LSTM training
│   ├── train_gru.py                     # PyTorch GRU variant
│   ├── ensemble_model.py               # Combine XGBoost + LSTM predictions
│   ├── hyperparameter_tuning.py         # Optuna optimization
│   ├── model_evaluation.py             # Metrics, SHAP, confusion matrix
│   └── mlflow_config.py                # MLflow tracking server config
│
├── genai/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── rag_pipeline.py                  # ChromaDB retrieval + LLM generation
│   ├── report_generator.py             # Predictions → natural language reports
│   ├── anomaly_explainer.py            # Anomaly → LLM explanation
│   ├── text_to_sql.py                  # Natural language → BigQuery SQL
│   ├── embeddings/
│   │   └── embed_historical_reports.py  # Build vector store from climate docs
│   └── prompts/
│       ├── report_prompt.txt            # Prompt template for reports
│       ├── anomaly_prompt.txt           # Prompt template for anomaly explanation
│       └── sql_prompt.txt               # Prompt template for text-to-SQL
│
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                          # FastAPI application entry point
│   ├── routers/
│   │   ├── predictions.py               # /predict endpoints
│   │   ├── chat.py                      # /chat endpoints (Gen AI)
│   │   ├── anomalies.py                # /anomalies endpoints
│   │   ├── reports.py                  # /reports endpoints
│   │   └── health.py                   # /health endpoint
│   └── schemas/
│       ├── request_models.py            # Pydantic request schemas
│       └── response_models.py           # Pydantic response schemas
│
├── dashboard/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py                           # Streamlit main entry point
│   ├── pages/
│   │   ├── 1_realtime_map.py           # Live weather map + predictions
│   │   ├── 2_historical_trends.py      # Trend analysis & charts
│   │   ├── 3_chatbot.py               # Gen AI chatbot interface
│   │   └── 4_model_monitoring.py       # Drift & accuracy tracking
│   └── utils/
│       └── api_client.py               # Helper to call FastAPI backend
│
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml              # Scrape configs for all services
│   ├── grafana/
│   │   └── dashboards/
│   │       ├── pipeline_health.json    # Data pipeline metrics
│   │       └── model_performance.json  # ML model metrics
│   └── evidently/
│       └── drift_detection.py          # Scheduled drift reports
│
├── tests/
│   ├── test_ingestion/
│   │   └── test_kafka_producer.py
│   ├── test_processing/
│   │   └── test_spark_jobs.py
│   ├── test_ml/
│   │   └── test_model_training.py
│   ├── test_genai/
│   │   └── test_rag_pipeline.py
│   └── test_api/
│       └── test_endpoints.py
│
├── scripts/
│   ├── setup_local.sh                  # Install dependencies & start Docker
│   ├── setup_gcp.sh                    # Create GCP project & enable APIs
│   ├── create_kafka_topics.sh          # Initialize Kafka topics
│   └── load_historical_data.sh         # Backfill historical weather data
│
└── docs/
    ├── ARCHITECTURE.md                  # Detailed architecture decisions
    ├── DEPLOYMENT.md                    # Step-by-step cloud deployment guide
    ├── API.md                           # Full API reference
    └── TROUBLESHOOTING.md              # Common issues & fixes
```

---

## 🚀 Getting Started

### Prerequisites

| Tool | Version | Installation |
|------|---------|-------------|
| Python | 3.10+ | [python.org](https://python.org) |
| Docker Desktop | Latest | [docker.com](https://docker.com/products/docker-desktop) |
| Git | Latest | [git-scm.com](https://git-scm.com) |
| Google Cloud SDK | Latest | [cloud.google.com/sdk](https://cloud.google.com/sdk/docs/install) |

### Quick Start (Local Development)

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/climate-intelligence-platform.git
cd climate-intelligence-platform

# 2. Copy environment template and add your API keys
cp .env.example .env
# Edit .env with your NOAA_API_KEY, OPENWEATHER_API_KEY, GEMINI_API_KEY

# 3. Start all services (Kafka, Spark, Airflow, API, Dashboard, etc.)
docker-compose up -d

# 4. Verify services are running
docker-compose ps
```

### Access Points (Local)

| Service | URL | Description |
|---------|-----|-------------|
| **FastAPI** | http://localhost:8000 | REST API + Swagger docs at /docs |
| **Streamlit Dashboard** | http://localhost:8501 | Interactive visualization |
| **Airflow** | http://localhost:8080 | Pipeline orchestration UI |
| **Spark Master** | http://localhost:8090 | Spark job monitoring |
| **MLflow** | http://localhost:5000 | Experiment tracking UI |
| **Kafka UI** | http://localhost:9021 | Kafka topic monitoring |
| **Grafana** | http://localhost:3000 | Infrastructure dashboards |
| **Prometheus** | http://localhost:9090 | Metrics collection |

---

## 🔄 Pipeline Deep Dive

### 1. Ingestion (Kafka Producers)

Weather data flows from multiple APIs into a 3-broker Kafka cluster. Each source has its own producer with Avro schema validation via Schema Registry. This ensures data contracts are enforced before any data enters the pipeline.

```
NOAA API ─────┐
               ├──→ Kafka Broker Cluster ──→ 3 Topics (partitioned by region)
OpenWeather ──┤                               │
               │                               ├──→ Spark Streaming (real-time)
NASA ─────────┘                               └──→ Kafka Connect → GCS (archival)
```

### 2. Processing (Medallion Architecture)

| Layer | Purpose | Format | Example Transformation |
|-------|---------|--------|----------------------|
| **Bronze** | Raw data as-is | Parquet, partitioned by `ingestion_date` | Kafka JSON → Parquet |
| **Silver** | Cleaned & validated | Parquet, partitioned by `date/region` | Remove nulls, fix types, deduplicate |
| **Gold** | Business-ready features | Parquet, partitioned by `date/region` | Rolling averages, heat index, anomaly flags |

### 3. Warehouse (BigQuery Star Schema)

```
              ┌──────────────┐
              │  dim_time     │
              │  date_key     │
              │  hour, day    │
              │  month, year  │
              └──────┬───────┘
                     │
┌──────────────┐     │     ┌───────────────────┐
│ dim_location  ├─────┼─────┤ fact_weather      │
│ location_key  │     │     │ temperature       │
│ city, state   │     │     │ humidity          │
│ lat, lon      │     │     │ wind_speed        │
│ region        │     │     │ pressure          │
└──────────────┘     │     │ precipitation     │
                     │     └───────────────────┘
              ┌──────┴───────┐
              │dim_weather   │
              │type          │
              │severity      │
              │category      │
              └──────────────┘
```

---

## 🤖 ML Models

| Model | Task | Input | Output |
|-------|------|-------|--------|
| **XGBoost** | Classify extreme weather events | Gold layer features (30+ features) | Event type + probability |
| **LSTM** | Forecast temperature/pressure | 7-day sliding window time-series | 24-72 hour forecast + confidence interval |
| **GRU** | Benchmark comparison to LSTM | Same as LSTM | Same as LSTM |
| **Ensemble** | Final production prediction | XGBoost + LSTM outputs | Weighted combined prediction |

All experiments tracked in **MLflow** with metrics, parameters, and model artifacts. Best model auto-promoted to **Vertex AI** for serving.

---

## 🧠 Gen AI Integration

| Feature | How It Works | Example |
|---------|-------------|---------|
| **Weather Reports** | Model prediction → LLM prompt → Natural language report | *"A severe heatwave is expected in Phoenix, AZ over the next 72 hours with temperatures exceeding 115°F. Risk level: HIGH. Recommend increased water distribution and cooling center activation."* |
| **Anomaly Explainer** | Anomaly detected → Historical context retrieved → LLM explains | *"Unusual pressure drop detected in Gulf Coast region. Historically, this pattern preceded Category 3+ hurricanes 73% of the time."* |
| **RAG Chatbot** | Question → Embed → Retrieve from ChromaDB → LLM answer | User: "What caused major flooding in Houston?" → Grounded answer from historical data |
| **Text-to-SQL** | Natural language → SQL query → BigQuery → Natural response | User: "How many storms hit Florida in 2024?" → `SELECT COUNT(*)...` → "There were 47 storm events recorded in Florida during 2024." |

---

## ☁️ Deployment

### Local Development
```bash
docker-compose up -d        # Start all services
docker-compose logs -f      # View logs
docker-compose down         # Stop all services
```

### GCP Production Deployment
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

### CI/CD Pipeline (GitHub Actions)
```
Push to feature branch → Lint & Test → Build Docker images
                                              │
Merge to main → Build → Push to Artifact Registry → Deploy to GKE
```

---

## 📊 Monitoring

| Tool | What It Monitors |
|------|-----------------|
| **Prometheus** | Service uptime, API latency, Kafka lag, Spark job duration |
| **Grafana** | Visual dashboards for all metrics with alerting |
| **Evidently AI** | Data drift (input feature distribution changes), model performance drift (accuracy/F1 degradation) |
| **MLflow** | Experiment history, model versions, comparison across runs |
| **Airflow UI** | DAG run status, task failures, retry history |

---

## 📡 API Documentation

Full interactive docs available at `http://localhost:8000/docs` (Swagger UI) when running locally.

### Key Endpoints

```
POST   /api/v1/predict          → Get extreme weather prediction for a location
POST   /api/v1/chat             → Ask a climate question (Gen AI chatbot)
GET    /api/v1/anomalies        → List recent anomalies with LLM explanations
GET    /api/v1/reports/{date}   → Get generated weather report for a date
GET    /api/v1/health           → Service health check
```

### Example Request
```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 33.4484,
    "longitude": -112.0740,
    "forecast_hours": 72
  }'
```

### Example Response
```json
{
  "location": "Phoenix, AZ",
  "predictions": [
    {
      "event_type": "heatwave",
      "probability": 0.89,
      "severity": "extreme",
      "confidence_interval": [0.82, 0.94],
      "forecast_window": "2025-07-15 to 2025-07-18",
      "explanation": "Persistent high-pressure ridge combined with record soil moisture deficit indicates extreme heat event."
    }
  ],
  "model_version": "ensemble-v2.3.1",
  "generated_report": "A severe heatwave is expected in Phoenix, AZ..."
}
```

---

## 📅 Implementation Roadmap

| Week | Focus | Key Deliverables |
|------|-------|-----------------|
| **1** | Foundation & Kafka | Project setup, Docker Compose, Kafka cluster running, first message flowing |
| **2** | Data Ingestion | Python producers for NOAA + OpenWeather, Avro schemas, Kafka Connect to GCS |
| **3** | Spark Processing | Structured Streaming (Kafka → Bronze), batch jobs (Silver, Gold), GCS partitioning |
| **4** | BigQuery & Airflow | Star schema design, Gold → BigQuery load, Airflow DAGs, Great Expectations |
| **5** | ML Models & MLflow | XGBoost + LSTM training, ensemble, SHAP, Optuna, MLflow tracking |
| **6** | Gen AI Integration | ChromaDB + RAG, report generator, anomaly explainer, text-to-SQL |
| **7** | API & Dashboard | FastAPI endpoints, Streamlit dashboard, Evidently drift monitoring |
| **8** | Deployment & CI/CD | Dockerize all services, Terraform, GKE deploy, GitHub Actions, Grafana |

---

## 🎓 Why This Project Stands Out

- **End-to-end**: From raw API data to Gen AI-powered insights — not just a notebook
- **Production-grade**: Kafka, Docker, Kubernetes, CI/CD, monitoring — how real systems work
- **Modern stack**: Combines traditional big data (Spark) with cutting-edge Gen AI (RAG, LLMs)
- **Explainable AI**: SHAP values + LLM explanations — not a black box
- **Scalable**: Designed to handle terabytes with proper partitioning, streaming, and auto-scaling

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

---

*Built with ❤️ for climate resilience*
