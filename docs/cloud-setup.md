# GCP setup (not yet applied)

The Terraform in `infra/terraform` is intentionally a plan-first scaffold. It creates a private landing bucket, separate raw/analytics/ML datasets, and a dedicated pipeline service account with dataset-scoped data editing plus BigQuery job and bucket-object permissions.

1. Create or select a GCP project and enable billing.
2. Install Terraform and authenticate locally with Application Default Credentials.
3. Copy `terraform.tfvars.example` to `terraform.tfvars` and set the real project ID.
4. From `infra/terraform`, run `terraform init`, then `terraform plan` and review every resource and permission.
5. Apply only after the plan is understood. This project has not provisioned cloud resources.

The bucket is private, uniform bucket-level access is enabled, public access prevention is enforced, and landing objects expire after 90 days. There is no `force_destroy`; teardown will not silently empty the bucket.
