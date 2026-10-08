"""Metadata normalization for the XJTU-SY dataset."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .xjtu import CONDITIONS, DATASET_NAME, MEASUREMENT_INTERVAL_SEC

SOURCE_DOCUMENT = (
    "data/raw/XJTU-SY_Bearing_Datasets/Data/"
    "XJTU-SY_Bearing_Datasets/Introduction_to_XJTU-SY_Bearing_Dataset.pdf"
)
ALLOWED_FAULT_ELEMENTS = {"inner_race", "outer_race", "cage", "ball"}

DATASET_METADATA_SCHEMA = pa.schema(
    [
        ("dataset_name", pa.string()),
        ("bearing_model", pa.string()),
        ("sensor_model", pa.string()),
        ("channel_count", pa.int64()),
        ("channel_directions", pa.list_(pa.string())),
        ("sampling_rate_hz", pa.float64()),
        ("recording_window_sec", pa.float64()),
        ("documented_signal_length", pa.int64()),
        ("measurement_interval_sec", pa.float64()),
        ("failure_criterion", pa.string()),
        ("metadata_source", pa.string()),
        ("metadata_source_locator", pa.string()),
        ("metadata_confidence", pa.string()),
    ]
)

CONDITION_METADATA_SCHEMA = pa.schema(
    [
        ("dataset_name", pa.string()),
        ("experiment_id", pa.string()),
        ("source_condition_name", pa.string()),
        ("rotational_speed_rpm", pa.float64()),
        ("rotational_frequency_hz", pa.float64()),
        ("radial_load_kn", pa.float64()),
        ("metadata_source", pa.string()),
        ("metadata_source_locator", pa.string()),
        ("metadata_confidence", pa.string()),
    ]
)

TRAJECTORY_METADATA_SCHEMA = pa.schema(
    [
        ("dataset_name", pa.string()),
        ("experiment_id", pa.string()),
        ("bearing_id", pa.string()),
        ("source_csv_count", pa.int64()),
        ("reported_lifetime_raw", pa.string()),
        ("reported_lifetime_min", pa.float64()),
        ("parsed_measurement_count", pa.int64()),
        ("first_measurement_index", pa.int64()),
        ("last_measurement_index", pa.int64()),
        ("fault_element_raw", pa.string()),
        ("fault_elements", pa.list_(pa.string())),
        ("failure_observed", pa.bool_()),
        ("metadata_source", pa.string()),
        ("metadata_source_locator", pa.string()),
        ("metadata_confidence", pa.string()),
        ("notes", pa.string()),
    ]
)


class MetadataError(ValueError):
    """Metadata source or manifest cannot be normalized safely."""


def _write_parquet(path: Path, rows: list[dict[str, Any]], schema: pa.Schema) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path, compression="zstd")


def _parse_bool(value: str, field_name: str, row_number: int) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise MetadataError(f"row {row_number}: {field_name} must be true or false")
    return normalized == "true"


def _read_trajectory_config(path: Path) -> list[dict[str, Any]]:
    required = {
        "dataset_name",
        "experiment_id",
        "bearing_id",
        "source_csv_count",
        "reported_lifetime_raw",
        "reported_lifetime_min",
        "fault_element_raw",
        "fault_elements",
        "failure_observed",
        "metadata_source",
        "metadata_source_locator",
        "metadata_confidence",
        "notes",
    }
    rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or []))
            raise MetadataError(f"metadata config is missing columns: {missing}")
        for row_number, raw in enumerate(reader, start=2):
            key = (raw["dataset_name"], raw["experiment_id"], raw["bearing_id"])
            if key in seen_keys:
                raise MetadataError(f"row {row_number}: duplicate metadata key {key}")
            seen_keys.add(key)
            try:
                source_csv_count = int(raw["source_csv_count"])
                lifetime_min = float(raw["reported_lifetime_min"])
            except ValueError as exc:
                raise MetadataError(f"row {row_number}: invalid numeric metadata") from exc
            if source_csv_count < 1 or lifetime_min < 0:
                raise MetadataError(f"row {row_number}: negative or empty lifetime/count")
            fault_elements = [
                item.strip()
                for item in raw["fault_elements"].split(";")
                if item.strip()
            ]
            unknown_faults = sorted(set(fault_elements) - ALLOWED_FAULT_ELEMENTS)
            if not fault_elements or unknown_faults:
                raise MetadataError(
                    f"row {row_number}: invalid fault_elements {unknown_faults or fault_elements}"
                )
            if raw["dataset_name"] != DATASET_NAME:
                raise MetadataError(f"row {row_number}: unexpected dataset name")
            if raw["experiment_id"] not in {config.experiment_id for config in CONDITIONS.values()}:
                raise MetadataError(f"row {row_number}: unexpected experiment_id")
            rows.append(
                {
                    "dataset_name": raw["dataset_name"],
                    "experiment_id": raw["experiment_id"],
                    "bearing_id": raw["bearing_id"],
                    "source_csv_count": source_csv_count,
                    "reported_lifetime_raw": raw["reported_lifetime_raw"],
                    "reported_lifetime_min": lifetime_min,
                    "fault_element_raw": raw["fault_element_raw"],
                    "fault_elements": fault_elements,
                    "failure_observed": _parse_bool(
                        raw["failure_observed"], "failure_observed", row_number
                    ),
                    "metadata_source": raw["metadata_source"],
                    "metadata_source_locator": raw["metadata_source_locator"],
                    "metadata_confidence": raw["metadata_confidence"],
                    "notes": raw["notes"],
                }
            )
    if not rows:
        raise MetadataError("metadata config contains no rows")
    return rows


def _condition_rows() -> list[dict[str, Any]]:
    frequencies = {"condition_1": 35.0, "condition_2": 37.5, "condition_3": 40.0}
    return [
        {
            "dataset_name": DATASET_NAME,
            "experiment_id": config.experiment_id,
            "source_condition_name": config.source_name,
            "rotational_speed_rpm": config.rotational_speed_rpm,
            "rotational_frequency_hz": frequencies[config.experiment_id],
            "radial_load_kn": config.radial_load_kn,
            "metadata_source": SOURCE_DOCUMENT,
            "metadata_source_locator": "Sections 2.3 and 2.4, pages 2-3",
            "metadata_confidence": "high",
        }
        for config in CONDITIONS.values()
    ]


def _dataset_row() -> dict[str, Any]:
    return {
        "dataset_name": DATASET_NAME,
        "bearing_model": "LDK UER204",
        "sensor_model": "PCB 352C33",
        "channel_count": 2,
        "channel_directions": ["horizontal", "vertical"],
        "sampling_rate_hz": 25_600.0,
        "recording_window_sec": 1.28,
        "documented_signal_length": 32_768,
        "measurement_interval_sec": MEASUREMENT_INTERVAL_SEC,
        "failure_criterion": "maximum horizontal or vertical amplitude exceeds 10 * A_h",
        "metadata_source": SOURCE_DOCUMENT,
        "metadata_source_locator": "Sections 2.2-2.4 and 3, pages 1-3",
        "metadata_confidence": "high",
    }


def build_xjtu_metadata(
    metadata_config: str | Path,
    manifest_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Normalize XJTU-SY metadata and join it to the parsed source manifest."""
    metadata_config = Path(metadata_config).resolve()
    manifest_path = Path(manifest_path).resolve()
    output_dir = Path(output_dir).resolve()
    if not metadata_config.is_file():
        raise FileNotFoundError(f"metadata config does not exist: {metadata_config}")
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest does not exist: {manifest_path}")

    config_rows = _read_trajectory_config(metadata_config)
    config_keys = {
        (row["dataset_name"], row["experiment_id"], row["bearing_id"])
        for row in config_rows
    }
    manifest_rows = pq.read_table(manifest_path).to_pylist()
    manifest_by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in manifest_rows:
        key = (DATASET_NAME, row["experiment_id"], row["bearing_id"])
        manifest_by_key[key].append(row)
    manifest_keys = set(manifest_by_key)
    missing_keys = sorted(config_keys - manifest_keys)
    extra_keys = sorted(manifest_keys - config_keys)
    if missing_keys or extra_keys:
        raise MetadataError(
            f"metadata/manifest key mismatch: missing={missing_keys}, extra={extra_keys}"
        )

    trajectory_rows: list[dict[str, Any]] = []
    count_mismatches: list[dict[str, Any]] = []
    for config_row in config_rows:
        key = (
            config_row["dataset_name"],
            config_row["experiment_id"],
            config_row["bearing_id"],
        )
        parsed_rows = [
            row for row in manifest_by_key[key] if row["parse_status"] == "ok"
        ]
        indices = sorted(
            row["measurement_index"]
            for row in parsed_rows
            if row["measurement_index"] is not None
        )
        parsed_count = len(parsed_rows)
        if config_row["source_csv_count"] != parsed_count:
            count_mismatches.append(
                {
                    "experiment_id": config_row["experiment_id"],
                    "bearing_id": config_row["bearing_id"],
                    "source_csv_count": config_row["source_csv_count"],
                    "parsed_measurement_count": parsed_count,
                }
            )
        trajectory_rows.append(
            {
                **config_row,
                "parsed_measurement_count": parsed_count,
                "first_measurement_index": min(indices) if indices else None,
                "last_measurement_index": max(indices) if indices else None,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_parquet(output_dir / "xjtu_dataset_metadata.parquet", [_dataset_row()], DATASET_METADATA_SCHEMA)
    _write_parquet(output_dir / "xjtu_condition_metadata.parquet", _condition_rows(), CONDITION_METADATA_SCHEMA)
    _write_parquet(
        output_dir / "xjtu_trajectory_metadata.parquet",
        trajectory_rows,
        TRAJECTORY_METADATA_SCHEMA,
    )
    report = {
        "schema_version": "1.0",
        "dataset_name": DATASET_NAME,
        "metadata_config": str(metadata_config),
        "manifest": str(manifest_path),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "dataset_metadata_rows": 1,
            "condition_metadata_rows": 3,
            "trajectory_metadata_rows": len(trajectory_rows),
            "count_mismatch_count": len(count_mismatches),
        },
        "count_mismatches": count_mismatches,
        "output_files": [
            "xjtu_dataset_metadata.parquet",
            "xjtu_condition_metadata.parquet",
            "xjtu_trajectory_metadata.parquet",
            "xjtu_metadata_report.json",
        ],
    }
    (output_dir / "xjtu_metadata_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report