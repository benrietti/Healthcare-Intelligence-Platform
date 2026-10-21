"""Command-line entry point for synthetic source data generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from healthcare_capstone.generator import generate_dataset
from healthcare_capstone.ingest_gcp import ingest_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="healthcare-capstone")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="generate synthetic source CSVs")
    generate.add_argument("--output", type=Path, default=Path("data/generated"))
    generate.add_argument("--patients", type=int, default=500)
    generate.add_argument("--seed", type=int, default=42)

    ingest = subparsers.add_parser("ingest-gcp", help="upload generated CSVs and load BigQuery raw tables")
    ingest.add_argument("--input", type=Path, default=Path("data/generated"))
    ingest.add_argument("--project-id", required=True)
    ingest.add_argument("--bucket", required=True)
    ingest.add_argument("--dataset", default="healthcare_capstone_raw")
    ingest.add_argument("--location", default="US")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "generate":
        if args.patients < 1:
            raise SystemExit("--patients must be at least 1")
        result = generate_dataset(args.output, patient_count=args.patients, seed=args.seed)
        print(f"Generated {result['row_counts']['patients']} patients and "
              f"{result['row_counts']['encounters']} encounters in {args.output}")
        print(f"Manifest: {args.output / 'data_quality_manifest.json'}")
    elif args.command == "ingest-gcp":
        result = ingest_dataset(
            input_dir=args.input,
            project_id=args.project_id,
            bucket_name=args.bucket,
            dataset_id=args.dataset,
            location=args.location,
        )
        print(f"Ingested run {result['run_id']} into {args.project_id}.{args.dataset}")


if __name__ == "__main__":
    main()
