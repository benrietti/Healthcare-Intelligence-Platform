"""Contract tests for the deterministic synthetic data source."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from healthcare_capstone.generator import generate_dataset


class GeneratorTests(unittest.TestCase):
    def test_generation_is_reproducible_except_manifest_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            a = generate_dataset(Path(first), patient_count=30, seed=7)
            b = generate_dataset(Path(second), patient_count=30, seed=7)
            self.assertEqual(a["row_counts"], b["row_counts"])
            for filename in ("patients.csv", "encounters.csv", "clinical_events.csv", "claims.csv"):
                self.assertEqual((Path(first) / filename).read_bytes(), (Path(second) / filename).read_bytes())

    def test_tables_have_expected_keys_and_synthetic_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = generate_dataset(Path(tmp), patient_count=40, seed=12)
            for name, key in (("patients", "patient_id"), ("encounters", "encounter_id"),
                              ("clinical_events", "event_id"), ("claims", "claim_id")):
                with (Path(tmp) / f"{name}.csv").open(newline="", encoding="utf-8") as source:
                    rows = list(csv.DictReader(source))
                self.assertEqual(len(rows), manifest["row_counts"][name])
                self.assertEqual(len({row[key] for row in rows}), len(rows))
                self.assertTrue(all(row["synthetic"] == "True" for row in rows))

    def test_event_anomalies_are_injected_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = generate_dataset(Path(tmp), patient_count=100, seed=42)
            counts = manifest["injected_data_quality_conditions"]
            self.assertGreater(counts.get("missing_event_timestamps", 0), 0)
            self.assertGreater(counts.get("null_departments", 0), 0)
            self.assertGreater(counts.get("late_arriving_events", 0), 0)
            self.assertGreater(counts.get("replayed_source_events", 0), 0)
            with (Path(tmp) / "clinical_events.csv").open(newline="", encoding="utf-8") as source:
                events = list(csv.DictReader(source))
            self.assertTrue(any(not row["event_ts"] for row in events))

    def test_nonpositive_patient_count_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                generate_dataset(Path(tmp), patient_count=0)

    def test_readmission_label_matches_next_encounter_within_30_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generate_dataset(Path(tmp), patient_count=100, seed=20)
            with (Path(tmp) / "encounters.csv").open(newline="", encoding="utf-8") as source:
                rows = list(csv.DictReader(source))
            rows.sort(key=lambda row: (row["patient_id"], row["admission_ts"]))
            for index, row in enumerate(rows):
                following = next((candidate for candidate in rows[index + 1:]
                                  if candidate["patient_id"] == row["patient_id"]), None)
                expected = False
                if following is not None:
                    from datetime import datetime

                    discharged = datetime.fromisoformat(row["discharge_ts"].replace("Z", "+00:00"))
                    readmitted = datetime.fromisoformat(following["admission_ts"].replace("Z", "+00:00"))
                    days = (readmitted - discharged).total_seconds() / 86400
                    expected = 0 <= days <= 30
                self.assertEqual(row["readmitted_30d"], str(expected))


if __name__ == "__main__":
    unittest.main()
