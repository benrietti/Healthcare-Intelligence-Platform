"""Create deterministic, explicitly synthetic healthcare source records.

The generator keeps encounter facts internally coherent while making the
clinical event log imperfect on purpose. Anomaly injection is deterministic
for a given seed, and the manifest records the expected defects.
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


UTC = timezone.utc
START = datetime(2024, 1, 1, tzinfo=UTC)
END = datetime(2025, 12, 31, tzinfo=UTC)
FACILITIES = ("FAC-CO-01", "FAC-CO-02", "FAC-WA-01")
SERVICE_LINES = ("medicine", "cardiology", "orthopedics", "oncology", "surgery")
DIAGNOSES = ("cardiovascular", "respiratory", "infection", "injury", "neoplasm", "other")
PAYERS = ("commercial", "medicare", "medicaid", "self_pay")
EVENT_TYPES = ("admission", "assessment", "lab_result", "medication", "transfer", "discharge")
PATIENT_FIELDS = ("patient_id", "birth_year", "sex", "home_state", "synthetic")
ENCOUNTER_FIELDS = (
    "encounter_id", "patient_id", "facility_id", "admission_ts", "discharge_ts",
    "service_line", "primary_diagnosis_group", "payer", "discharge_disposition",
    "length_of_stay_hours", "readmitted_30d", "synthetic",
)
EVENT_FIELDS = (
    "event_id", "source_event_key", "encounter_id", "event_ts", "ingested_at",
    "event_type", "department", "event_status", "synthetic", "source_system", "source_code",
)
CLAIM_FIELDS = (
    "claim_id", "encounter_id", "payer", "claim_submit_ts", "billed_amount",
    "allowed_amount", "paid_amount", "claim_status", "denial_reason", "synthetic",
    "authorization_present", "documentation_complete", "procedure_group", "adjudicated_at",
)


def _iso(value: datetime | None) -> str:
    return "" if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _money(rng: random.Random, low: float, high: float) -> float:
    return round(rng.uniform(low, high), 2)


def generate_dataset(
    output_dir: Path,
    patient_count: int = 500,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate source tables and a machine-readable anomaly manifest."""
    if patient_count < 1:
        raise ValueError("patient_count must be at least 1")

    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    patients: list[dict[str, Any]] = []
    encounters: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []

    event_id_counter = 1
    encounter_records_by_patient: list[list[dict[str, Any]]] = []
    for patient_num in range(1, patient_count + 1):
        patient_id = f"SYN-P-{patient_num:06d}"
        patients.append({
            "patient_id": patient_id,
            "birth_year": rng.randint(1935, 2004),
            "sex": rng.choice(("female", "male", "unknown")),
            "home_state": rng.choice(("CO", "WA", "OR", "NM")),
            "synthetic": True,
        })

        count = rng.choices((1, 2, 3), weights=(0.72, 0.23, 0.05), k=1)[0]
        patient_encounters: list[dict[str, Any]] = []
        base_day = rng.randint(0, (END - START).days - 100)
        previous_discharge: datetime | None = None
        for sequence in range(count):
            if previous_discharge is None:
                admission = START + timedelta(days=base_day, minutes=rng.randint(0, 1439))
            else:
                # Model a subsequent admission after discharge, allowing both
                # short-gap readmissions and longer-term return encounters.
                admission = previous_discharge + timedelta(
                    days=rng.randint(5, 90), minutes=rng.randint(0, 1439)
                )
            if admission > END:
                break
            los_hours = max(4, round(rng.lognormvariate(3.4, 0.55), 1))
            discharge = admission + timedelta(hours=los_hours)
            encounter_id = f"SYN-E-{len(encounters) + 1:07d}"
            record = {
                "encounter_id": encounter_id,
                "patient_id": patient_id,
                "facility_id": rng.choice(FACILITIES),
                "admission_ts": admission,
                "discharge_ts": discharge,
                "service_line": rng.choice(SERVICE_LINES),
                "primary_diagnosis_group": rng.choice(DIAGNOSES),
                "payer": rng.choice(PAYERS),
                "discharge_disposition": rng.choices(
                    ("home", "home_health", "skilled_nursing", "other"),
                    weights=(0.70, 0.12, 0.12, 0.06), k=1,
                )[0],
                "length_of_stay_hours": los_hours,
                "readmitted_30d": False,
                "synthetic": True,
            }
            encounters.append(record)
            patient_encounters.append(record)
            previous_discharge = discharge
        for current, following in zip(patient_encounters, patient_encounters[1:]):
            days_to_next = (following["admission_ts"] - current["discharge_ts"]).total_seconds() / 86400
            current["readmitted_30d"] = 0 <= days_to_next <= 30
        encounter_records_by_patient.append(patient_encounters)

    anomaly_counts: Counter[str] = Counter()
    event_index = 0
    for encounter in encounters:
        admission = encounter["admission_ts"]
        discharge = encounter["discharge_ts"]
        department = encounter["service_line"]
        count = rng.randint(4, 9)
        event_times = sorted(
            admission + (discharge - admission) * (i / max(1, count - 1))
            for i in range(count)
        )
        event_batch: list[dict[str, Any]] = []
        for i, event_ts in enumerate(event_times):
            event_index += 1
            source_key = f"SRC-{event_index:08d}"
            event_type = EVENT_TYPES[min(i, len(EVENT_TYPES) - 1)]
            is_missing_ts = rng.random() < 0.035
            is_missing_department = rng.random() < 0.025
            ingested_at = event_ts + timedelta(minutes=rng.randint(0, 90))
            if rng.random() < 0.025:
                ingested_at += timedelta(days=rng.randint(1, 20))
                anomaly_counts["late_arriving_events"] += 1
            if is_missing_ts:
                anomaly_counts["missing_event_timestamps"] += 1
            if is_missing_department:
                anomaly_counts["null_departments"] += 1
            event_batch.append({
                "event_id": f"SYN-EVT-{event_id_counter:09d}",
                "source_event_key": source_key,
                "encounter_id": encounter["encounter_id"],
                "event_ts": "" if is_missing_ts else _iso(event_ts),
                "ingested_at": _iso(ingested_at),
                "event_type": event_type,
                "department": "" if is_missing_department else department,
                "event_status": "complete",
                "source_system": "synthetic_flowsheet",
                "source_code": ("SYN-VITAL-HR", "SYN-VITAL-RR", "SYN-TEMP")[i % 3],
                "synthetic": True,
            })
            event_id_counter += 1

        # A source emits some events out of order. Arrival order is the row order;
        # event_ts remains the event-time ordering signal used by downstream models.
        if len(event_batch) > 3 and rng.random() < 0.25:
            event_batch[1], event_batch[2] = event_batch[2], event_batch[1]
            anomaly_counts["out_of_order_event_pairs"] += 1
        # Replayed source messages have a new transport id but the same source key.
        if event_batch and rng.random() < 0.015:
            replay = dict(event_batch[-1])
            replay["event_id"] = f"SYN-EVT-{event_id_counter:09d}"
            event_id_counter += 1
            event_batch.append(replay)
            anomaly_counts["replayed_source_events"] += 1
        events.extend(event_batch)

        billed = _money(rng, 1200, 95000)
        allowed = round(billed * rng.uniform(0.35, 0.82), 2)
        authorization = rng.random() > 0.18
        documentation = rng.random() > 0.22
        procedure = rng.choice(("evaluation", "imaging", "procedure"))
        denial_probability = min(0.85, 0.04 + 0.30 * (not authorization)
                                 + 0.25 * (not documentation)
                                 + 0.08 * (procedure == "procedure"))
        status = "pending" if rng.random() < 0.10 else (
            "denied" if rng.random() < denial_probability else
            rng.choices(("paid", "partial"), weights=(0.9, 0.1))[0])
        submitted = discharge + timedelta(days=rng.randint(1, 14))
        paid = {
            "paid": allowed,
            "pending": 0.0,
            "denied": 0.0,
            "partial": round(allowed * rng.uniform(0.25, 0.85), 2),
        }[status]
        claims.append({
            "claim_id": f"SYN-C-{len(claims) + 1:07d}",
            "encounter_id": encounter["encounter_id"],
            "payer": encounter["payer"],
            "claim_submit_ts": _iso(submitted),
            "authorization_present": authorization,
            "documentation_complete": documentation,
            "procedure_group": procedure,
            "adjudicated_at": "" if status == "pending" else _iso(submitted + timedelta(days=rng.randint(3, 30))),
            "billed_amount": billed,
            "allowed_amount": allowed,
            "paid_amount": paid,
            "claim_status": status,
            "denial_reason": "missing_documentation" if status == "denied" else "",
            "synthetic": True,
        })

    # Shuffle entire event log rows to model batch arrival order across encounters.
    rng.shuffle(events)
    _write_csv(output_dir / "patients.csv", PATIENT_FIELDS, patients)
    _write_csv(output_dir / "encounters.csv", ENCOUNTER_FIELDS, [
        {**row,
         "admission_ts": _iso(row["admission_ts"]),
         "discharge_ts": _iso(row["discharge_ts"])}
        for row in encounters
    ])
    _write_csv(output_dir / "clinical_events.csv", EVENT_FIELDS, events)
    _write_csv(output_dir / "claims.csv", CLAIM_FIELDS, claims)

    manifest = {
        "dataset_name": "synthetic_healthcare_operations_v1",
        "synthetic_only": True,
        "seed": seed,
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "row_counts": {
            "patients": len(patients),
            "encounters": len(encounters),
            "clinical_events": len(events),
            "claims": len(claims),
        },
        "injected_data_quality_conditions": dict(sorted(anomaly_counts.items())),
        "expected_keys": {
            "patients": ["patient_id"],
            "encounters": ["encounter_id"],
            "clinical_events": ["event_id"],
            "claims": ["claim_id"],
        },
        "deduplication_candidate": ["source_event_key", "encounter_id", "event_type"],
        "notes": [
            "Synthetic records only; no patient or employer data is used.",
            "Readmission label is based on a subsequent synthetic inpatient encounter within 30 days of discharge.",
            "The event log is deliberately shuffled; use event_ts for event order and ingested_at for arrival order.",
            "Blank event_ts, blank department, late arrivals, and repeated source keys are intentional quality cases.",
        ],
    }
    (output_dir / "data_quality_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
