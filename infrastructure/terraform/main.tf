# ============================================
# Climate Intelligence Platform — GCP Infrastructure
# ============================================
# Setup:
#   cd infrastructure/terraform
#   terraform init
#   terraform plan
#   terraform apply
#
# Destroys all resources:
#   terraform destroy
# ============================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# ============================================
# PROVIDER
# ============================================

provider "google" {
  project     = var.project_id
  region      = var.region
  credentials = file("gcp-key.json")
}

# ============================================
# ENABLE REQUIRED APIs
# ============================================

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "aiplatform.googleapis.com",
    "container.googleapis.com",
    "monitoring.googleapis.com",
  ])
  project = var.project_id
  service = each.value
  disable_on_destroy = false
}

# ============================================
# GOOGLE CLOUD STORAGE — Data Lake
# ============================================

resource "google_storage_bucket" "bronze" {
  name          = "${var.project_id}-climate-bronze"
  location      = var.region
  storage_class = "STANDARD"
  force_destroy = true

  lifecycle_rule {
    action { type = "Delete" }
    condition { age = 90 }
  }

  labels = {
    environment = var.environment
    layer       = "bronze"
    project     = "climate-intelligence"
  }
}

resource "google_storage_bucket" "silver" {
  name          = "${var.project_id}-climate-silver"
  location      = var.region
  storage_class = "STANDARD"
  force_destroy = true

  labels = {
    environment = var.environment
    layer       = "silver"
    project     = "climate-intelligence"
  }
}

resource "google_storage_bucket" "gold" {
  name          = "${var.project_id}-climate-gold"
  location      = var.region
  storage_class = "STANDARD"
  force_destroy = true

  labels = {
    environment = var.environment
    layer       = "gold"
    project     = "climate-intelligence"
  }
}

# ============================================
# BIGQUERY — Data Warehouse
# ============================================

resource "google_bigquery_dataset" "warehouse" {
  dataset_id    = "climate_warehouse"
  friendly_name = "Climate Intelligence Warehouse"
  description   = "Star schema warehouse for weather data"
  location      = var.region

  labels = {
    environment = var.environment
    project     = "climate-intelligence"
  }

  delete_contents_on_destroy = true
}

resource "google_bigquery_table" "fact_weather" {
  dataset_id          = google_bigquery_dataset.warehouse.dataset_id
  table_id            = "fact_weather_readings"
  deletion_protection = false

  schema = jsonencode([
    { name = "reading_key",            type = "INT64",     mode = "REQUIRED" },
    { name = "location_key",           type = "INT64",     mode = "REQUIRED" },
    { name = "time_key",               type = "INT64",     mode = "NULLABLE" },
    { name = "weather_type_key",       type = "INT64",     mode = "NULLABLE" },
    { name = "temperature_fahrenheit", type = "FLOAT64",   mode = "NULLABLE" },
    { name = "temperature_celsius",    type = "FLOAT64",   mode = "NULLABLE" },
    { name = "humidity_percent",       type = "FLOAT64",   mode = "NULLABLE" },
    { name = "pressure_hpa",          type = "FLOAT64",   mode = "NULLABLE" },
    { name = "wind_speed_mph",        type = "FLOAT64",   mode = "NULLABLE" },
    { name = "heat_index",            type = "FLOAT64",   mode = "NULLABLE" },
    { name = "wind_chill",            type = "FLOAT64",   mode = "NULLABLE" },
    { name = "temperature_anomaly",   type = "FLOAT64",   mode = "NULLABLE" },
    { name = "temp_anomaly_score",    type = "FLOAT64",   mode = "NULLABLE" },
    { name = "is_extreme_weather",    type = "INT64",     mode = "NULLABLE" },
    { name = "loaded_at",             type = "TIMESTAMP", mode = "NULLABLE" },
  ])

  labels = {
    environment = var.environment
  }
}

resource "google_bigquery_table" "dim_location" {
  dataset_id          = google_bigquery_dataset.warehouse.dataset_id
  table_id            = "dim_location"
  deletion_protection = false

  schema = jsonencode([
    { name = "location_key", type = "INT64",   mode = "REQUIRED" },
    { name = "city",         type = "STRING",  mode = "REQUIRED" },
    { name = "state",        type = "STRING",  mode = "NULLABLE" },
    { name = "latitude",     type = "FLOAT64", mode = "NULLABLE" },
    { name = "longitude",    type = "FLOAT64", mode = "NULLABLE" },
    { name = "region",       type = "STRING",  mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "dim_time" {
  dataset_id          = google_bigquery_dataset.warehouse.dataset_id
  table_id            = "dim_time"
  deletion_protection = false

  schema = jsonencode([
    { name = "time_key",           type = "INT64",     mode = "REQUIRED" },
    { name = "reading_timestamp",  type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "hour",               type = "INT64",     mode = "NULLABLE" },
    { name = "day_of_week",        type = "INT64",     mode = "NULLABLE" },
    { name = "month",              type = "INT64",     mode = "NULLABLE" },
    { name = "year",               type = "INT64",     mode = "NULLABLE" },
    { name = "is_daytime",         type = "INT64",     mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "dim_weather_type" {
  dataset_id          = google_bigquery_dataset.warehouse.dataset_id
  table_id            = "dim_weather_type"
  deletion_protection = false

  schema = jsonencode([
    { name = "weather_type_key",  type = "INT64",  mode = "REQUIRED" },
    { name = "weather_condition", type = "STRING", mode = "NULLABLE" },
    { name = "weather_group",     type = "STRING", mode = "NULLABLE" },
  ])
}

# ============================================
# ARTIFACT REGISTRY — Docker Images
# ============================================

resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "climate-platform"
  description   = "Docker images for Climate Intelligence Platform"
  format        = "DOCKER"

  labels = {
    environment = var.environment
    project     = "climate-intelligence"
  }

  depends_on = [google_project_service.apis["artifactregistry.googleapis.com"]]
}

# ============================================
# CLOUD RUN — FastAPI Backend
# ============================================

resource "google_cloud_run_v2_service" "api" {
  name     = "climate-api"
  location = var.region

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/climate-platform/climate-api:latest"

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "GROQ_API_KEY"
        value = var.groq_api_key
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_artifact_registry_repository.docker_repo,
  ]
}

# Allow unauthenticated access to API
resource "google_cloud_run_v2_service_iam_member" "api_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ============================================
# CLOUD RUN — Streamlit Dashboard
# ============================================

resource "google_cloud_run_v2_service" "dashboard" {
  name     = "climate-dashboard"
  location = var.region

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/climate-platform/climate-dashboard:latest"

      ports {
        container_port = 8501
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      env {
        name  = "API_URL"
        value = google_cloud_run_v2_service.api.uri
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_cloud_run_v2_service.api,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "dashboard_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.dashboard.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ============================================
# MONITORING — Uptime Check
# ============================================

resource "google_monitoring_uptime_check_config" "api_health" {
  display_name = "Climate API Health Check"
  timeout      = "10s"
  period       = "300s"

  http_check {
    path         = "/"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = trimprefix(google_cloud_run_v2_service.api.uri, "https://")
    }
  }

  depends_on = [google_project_service.apis["monitoring.googleapis.com"]]
}

