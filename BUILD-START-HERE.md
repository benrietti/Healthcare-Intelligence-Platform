# Healthcare Intelligence Platform build update

This package contains updated project source, locally trained models and a new
Power BI page. It does not replace your live repository until you upload/push it.

1. Extract the package and copy the project files into a separate branch of your
   existing Healthcare-Intelligence-Platform repository.
2. Follow `docs/portfolio-build-runbook.md` to install dependencies and run the
   local demo. Generated source CSVs now include new claim and event fields.
3. Inspect `docs/evidence/` and the saved metrics under `data/models/`. Run
   `python scripts/render_demo.py --input data/demo` after building locally.
4. Run the GCP commands in the runbook using your existing project and bucket.
   This builds new views and regenerates predictions with the corrected feature
   controls. Cloud credentials remain on your machine/GCP, outside this package.
5. Open the included `.pbip`, refresh it, and validate the new Denial Risk &
   Monitoring page plus the existing pages before publishing.

The local evidence demonstrates execution on synthetic data. Cloud/CI/Airflow
execution and Power BI refresh must still be verified in their respective systems.
The included REVIEW-RESULTS.html is generated from these local run results;
it is not a Power BI screenshot.
