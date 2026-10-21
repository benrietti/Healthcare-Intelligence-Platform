resource "random_id" "suffix" {
  byte_length = 3
}

resource "google_project_service" "required_apis" {
  for_each = toset([
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "landing" {
  name                        = "${var.project_id}-hc-capstone-${random_id.suffix.hex}"
  location                    = var.location
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels = {
    app         = "healthcare-capstone"
    environment = var.environment
    data        = "synthetic"
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_bigquery_dataset" "datasets" {
  for_each = toset(["raw", "analytics", "ml"])

  dataset_id                 = "${var.dataset_prefix}_${each.value}"
  friendly_name              = "Healthcare capstone ${each.value} (${var.environment})"
  description                = "Synthetic healthcare capstone ${each.value} data; no patient or employer data."
  location                   = var.location
  delete_contents_on_destroy = false
  labels = {
    app         = "healthcare-capstone"
    environment = var.environment
    data        = "synthetic"
    layer       = each.value
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_service_account" "pipeline" {
  account_id   = "hc-capstone-${var.environment}"
  display_name = "Healthcare capstone ${var.environment} pipeline"
  description  = "Demo-only identity for the synthetic healthcare capstone pipeline."

  depends_on = [google_project_service.required_apis]
}

resource "google_project_iam_member" "pipeline_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_bigquery_dataset_iam_member" "pipeline_data_editor" {
  for_each = google_bigquery_dataset.datasets

  project    = var.project_id
  dataset_id = each.value.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_storage_bucket_iam_member" "pipeline_object_admin" {
  bucket = google_storage_bucket.landing.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}
