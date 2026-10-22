# Portfolio capability build and validation

This build adds the portfolio capabilities to the synthetic healthcare project.
The local run is executable without GCP or Power BI. Cloud execution and Power BI
rendering/refresh are separate acceptance steps and are not implied by source files.

## Run locally

From the repository root, using Python 3.12:

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
python -m pip install -e . -r requirements-demo.txt
python -m unittest discover -s tests -v
python -m healthcare_capstone.demo --output data/demo --patients 2000 --seed 42
python scripts/quality_gate.py --input data/demo
python scripts/render_demo.py --input data/demo
```

Open `data/demo/review.html`. On macOS/Linux activate with `source .venv/bin/activate`.
The review page is a local HTML view of generated results, not a Power BI screenshot.

The generated report CSVs are in `data/demo/reports`. Models, metrics, reference-bin
PSI, permutation importance, individual reference-substitution explanations, and
predictions are in `data/demo/models`. `alerts.json` describes threshold alerts and
response ownership. `quality_gate.json` is a blocking pass/fail result.

## What is implemented

| Portfolio capability | Implementation and evidence |
|---|---|
| Deterministic synthetic source and anomaly manifest | Generator and existing source tests; extra claim-submission attributes and source taxonomy codes |
| Admission-time readmission and LOS experiments | Explicit admission feature allowlist; chronological holdout; purged immature labels; corrected row identity; saved models and metrics |
| Event-time availability | `available_events` requires both event time and ingestion time at/before the encounter prediction cutoff; tests cover late documentation and mixed timestamp precision |
| Claim-denial risk prioritization | Submission-time features only; adjudication-time labels; pending outcomes excluded; purged chronological evaluation; held-out review queue and top-20% precision |
| Interpretability | Held-out permutation importance with five repeats; individual reference substitutions with sign stability across two training-reference windows |
| Drift | Reference-bin numeric PSI and categorical PSI including unseen categories; missingness reports; configurable warning thresholds |
| Encounter and data-quality marts | Existing encounter/reporting models plus local report CSVs and blocking checks |
| Ingestion audit, freshness, alert records | Existing ingestion audit plus cloud monitoring command, source freshness, local gate, and persisted alert records |
| PR validation | GitHub Actions source/test/demo/quality/dbt-parse job; manual authenticated cloud workflow adds dbt execution, freshness, query-budget dry runs and alert checks |
| Orchestration | Airflow DAG for local validation, cloud load/build, and monitoring; worker setup required |
| Bed readiness and ED dwell design example | Synthetic milestone fixture, readiness reconciliation, null handling, turnover and ED dwell output; no live ADT/EVS connection |
| Clinical source taxonomy design example | Generated synthetic flowsheet codes, seed crosswalk, event-to-category reporting model; no proprietary Epic content |
| EDI examples | Synthetic 837 CLM and 835 CLP segment export/parser and round-trip tests; not full transaction envelopes or implementation-guide certification |
| BI additions | New Denial Risk & Monitoring report page, claim-risk table/measures, and model drift table; existing report pages retained |

## Model limitations

All records and targets are synthetic. The diagnosis group is generated as an
admission-known attribute in this demo; real source availability would need proof.
A chronological split does not by itself establish leakage protection. Explicit
allowlists, label maturity and event-time/recorded-time checks provide that control.
The old saved models were replaced with the corrected run's artifacts.

Readmission negatives require 30 days of observation after discharge. Training
labels must mature before the first held-out prediction. LOS uses discharge time
for label maturity; denial uses adjudication time. No financial adjudication field
or full encounter total is allowed as a clinical admission-time feature.

Compare the saved holdout metrics with the saved dummy baseline. The synthetic
readmission and LOS targets contain little predictive signal; a weak result is
not hidden or converted into a performance claim. Claim ranking evaluates held-out
adjudicated synthetic claims, not prospective decisions on real outstanding claims.

Individual explanation deltas are one-feature reference substitutions, not SHAP,
causal effects, or additive contributions. Stable direction is reported rather
than assumed. Drift uses training versus held-out data; production monitoring
requires recurring scoring batches and a retained reference cohort.

## Cloud execution

Use your existing GCP project and synthetic-only bucket. No cloud credentials,
billing changes, service-account grants or resources were applied by this build.
Install `requirements-gcp.txt`, `requirements-demo.txt`, and `dbt-bigquery==1.9.2`.
Authenticate ADC with your normal GCP workflow. Set these environment variables:

- `GCP_PROJECT_ID`: your existing project ID (not its display name).
- `GCP_BUCKET`: your existing synthetic landing bucket.
- `DBT_RAW_DATASET`: `healthcare_capstone_raw`.
- `DBT_ANALYTICS_DATASET`: `healthcare_capstone_analytics`.
- `ML_PREDICTIONS_DATASET`: `healthcare_capstone_ml`.
- `SOURCE_OBSERVATION_END`: `2025-12-31` for the current generated horizon.

Load a newly generated batch because the source schemas now include claim submission
attributes and synthetic event codes. Then run:

```bash
python -m healthcare_capstone.cli generate --output data/generated --patients 2000
python -m healthcare_capstone.cli ingest-gcp --project-id YOUR_PROJECT_ID --bucket YOUR_BUCKET
python scripts/cloud_build.py
python scripts/query_budget.py
python scripts/cloud_monitor.py
```

`cloud_build.py` builds upstream dbt models before ML sources exist, trains and loads
three ML tables plus drift evidence, seeds the synthetic design examples, and runs
the complete dbt build and source freshness check. Any failed command stops execution.
The query budget defaults to 1 GiB per reporting dry run; override `MAX_QUERY_BYTES`
only after reviewing the intended workload. Cloud monitoring exits nonzero for
stale input, historical ingestion failures, poor source quality or drift warnings.
Investigate alerts; do not disable checks just to obtain a passing deployment.

For GitHub cloud execution configure the `portfolio-cloud` environment and its
GCP variables shown in `.github/workflows/cloud-validation.yml`. Workload Identity
Federation must be configured in GCP. Source/test validation runs on PRs; cloud
execution is manual and requires the authorized environment. No workflow execution
in your GitHub account is claimed by the local evidence.

## Power BI acceptance

Open the existing `.pbip` from this source tree in Power BI Desktop after cloud
execution. The original project ID in its connections is retained. The new page
requires `rpt_claim_denial_queue` and `rpt_model_drift` in the analytics dataset.
Refresh and check:

1. Existing Overview, Finance, Pipeline Health, and Clinical & Predictions pages
   still render and existing slicers preserve their expected behavior.
2. Denial Risk & Monitoring displays held-out claim scores; probabilities are in
   [0,1], ranks are unique, and counts equal the warehouse's scored claim cohort.
3. The drift table includes all three models and matches stored PSI/thresholds.
4. Readmission and LOS scoring coverage is below 100% because scores are held out;
   compare predicted and actual metrics within the same scored cohort.
5. Ingestion counts and latest timestamps match the current load audit. Test a
   failing source or freshness condition and confirm the monitoring job fails.

New report JSON parses and visual fields resolve to semantic tables. Opening,
rendering and refreshing this PBIP in Desktop are still required; local checks do
not validate the Power BI engine or cloud connection.

## Publishing the changes

The download is a source update, not an upload to your live GitHub repository.
Copy its files into the repository root on a branch and review the diff. Push the
branch and let the PR validation run. Retain cloud test results and refreshed
Power BI screenshots before presenting the platform as deployed and verified.

After the first cloud deployment, set the repository variable
`ENABLE_CLOUD_PR_CHECKS=true` to enable BigQuery dry-run checks on internal PRs.
The protected `portfolio-cloud` environment supplies the GCP identity. Fork PRs
only run local validation. Compiled SELECT statements are dry-run, not executed;
referenced datasets and views must already exist. The workflow checks both query
validity and estimated bytes without overwriting production tables.
