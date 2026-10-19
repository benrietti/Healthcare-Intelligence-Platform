output "landing_bucket" {
  value       = google_storage_bucket.landing.name
  description = "Private Cloud Storage bucket for synthetic raw-data batches."
}

output "raw_dataset" {
  value       = google_bigquery_dataset.datasets["raw"].dataset_id
  description = "BigQuery raw landing dataset."
}

output "analytics_dataset" {
  value       = google_bigquery_dataset.datasets["analytics"].dataset_id
  description = "BigQuery dbt analytics dataset."
}

output "ml_dataset" {
  value       = google_bigquery_dataset.datasets["ml"].dataset_id
  description = "BigQuery model output and telemetry dataset."
}

output "pipeline_service_account" {
  value       = google_service_account.pipeline.email
  description = "Dedicated pipeline service account."
}
