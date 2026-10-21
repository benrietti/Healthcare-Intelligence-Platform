variable "project_id" {
  description = "Existing GCP project ID. No project is created by this module."
  type        = string
}

variable "location" {
  description = "BigQuery dataset and bucket location. Keep both in one region for simpler cost and data movement."
  type        = string
  default     = "US"
}

variable "dataset_prefix" {
  description = "Prefix for the capstone BigQuery datasets."
  type        = string
  default     = "healthcare_capstone"

  validation {
    condition     = can(regex("^[a-zA-Z0-9_]+$", var.dataset_prefix))
    error_message = "dataset_prefix can contain only letters, numbers, and underscores."
  }
}

variable "environment" {
  description = "Environment label used on capstone resources."
  type        = string
  default     = "dev"
}
