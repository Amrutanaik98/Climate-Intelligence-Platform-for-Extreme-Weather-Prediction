
# ============================================
# FILE: infrastructure/terraform/outputs.tf
# ============================================

 output "bronze_bucket" {
   description = "GCS Bronze bucket name"
   value       = google_storage_bucket.bronze.name
 }

 output "silver_bucket" {
   description = "GCS Silver bucket name"
   value       = google_storage_bucket.silver.name
 }

 output "gold_bucket" {
   description = "GCS Gold bucket name"
   value       = google_storage_bucket.gold.name
 }

 output "bigquery_dataset" {
   description = "BigQuery dataset ID"
   value       = google_bigquery_dataset.warehouse.dataset_id
 }

 output "docker_registry" {
   description = "Artifact Registry URL"
   value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}"
 }

 output "api_url" {
   description = "Cloud Run API URL"
   value       = google_cloud_run_v2_service.api.uri
 }

 output "dashboard_url" {
   description = "Cloud Run Dashboard URL"
   value       = google_cloud_run_v2_service.dashboard.uri
 }

 output "monitoring_check_id" {
   description = "Uptime monitoring check ID"
   value       = google_monitoring_uptime_check_config.api_health.uptime_check_id
 }
