"""Lossless raw parser for the XJTU-SY bearing dataset."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

DATASET_NAME = "XJTU-SY"
EXPECTED_SIGNAL_LENGTH = 32_768
MEASUREMENT_INTERVAL_SEC = 60.0
HORIZONTAL_HEADER = "Horizontal_vibration_signals"
VERTICAL_HEADER = "Vertical_vibration_signals"
EXPECTED_HEADERS = (HORIZONTAL_HEADER, VERTICAL_HEADER)


@dataclass(frozen=True)
class ConditionConfig:
    source_name: str
    experiment_id: str
    rotational_speed_rpm: float
    radial_load_kn: float


CONDITIONS: dict[str, ConditionConfig] = {
    "35Hz12kN": ConditionConfig("35Hz12kN", "condition_1", 2100.0, 12.0),
    "37.5Hz11kN": ConditionConfig("37.5Hz11kN", "condition_2", 2250.0, 11.0),
    "40Hz10kN": ConditionConfig("40Hz10kN", "condition_3", 2400.0, 10.0),
}

OBSERVATION_SCHEMA = pa.schema(
    [
        ("dataset_name", pa.string()),
        ("experiment_id", pa.string()),
        ("bearing_id", pa.string()),
        ("measurement_index", pa.int64()),
        ("elapsed_time_sec", pa.float64()),
        ("rotational_speed_rpm", pa.float64()),
        ("radial_load_kn", pa.float64()),
        ("channel_id", pa.string()),
        ("channel_direction", pa.string()),
        ("sampling_rate_hz", pa.float64()),
        ("signal_length", pa.int64()),
        ("vibration_signal", pa.list_(pa.float32())),
    ]
)

MANIFEST_SCHEMA = pa.schema(
    [
        ("source_relative_path", pa.string()),
        ("file_sha256", pa.string()),
        ("file_size_bytes", pa.int64()),
        ("condition_source_name", pa.string()),
        ("experiment_id", pa.string()),
        ("bearing_id", pa.string()),
        ("measurement_index", pa.int64()),
        ("source_columns", pa.list_(pa.string())),
        ("source_row_count", pa.int64()),
        ("horizontal_signal_length", pa.int64()),
        ("vertical_signal_length", pa.int64()),
        ("parse_status", pa.string()),
        ("error", pa.string()),
        ("warnings", pa.list_(pa.string())),
    ]
)


class ParseFileError(ValueError):
    """A source file cannot be converted into normalized observations."""


@dataclass
class ParsedSignals:
    columns: list[str]
    signals: dict[str, np.ndarray]
    row_count: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_measurement_index(path: Path) -> int:
    stem = path.stem
    if not stem.isdigit():
        raise ParseFileError(f"filename stem is not a positive integer: {path.name}")
    index = int(stem)
    if index < 1:
        raise ParseFileError(f"measurement index must be positive: {path.name}")
    return index


def _read_csv_signals(path: Path) -> ParsedSignals:
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise ParseFileError(f"cannot open CSV: {exc}") from exc

    with handle:
        reader = csv.reader(handle)
        try:
            raw_header = next(reader)
        except StopIteration as exc:
            raise ParseFileError("CSV is empty") from exc

        columns = [value.strip() for value in raw_header]
        if len(columns) != len(set(columns)):
            raise ParseFileError(f"duplicate CSV headers: {columns}")
        if set(columns) != set(EXPECTED_HEADERS) or len(columns) != 2:
            raise ParseFileError(
                f"expected headers {list(EXPECTED_HEADERS)}, got {columns}"
            )

        signals_by_column: dict[str, list[float]] = {column: [] for column in columns}
        data_row_count = 0
        for line_number, row in enumerate(reader, start=2):
            if not row or all(not value.strip() for value in row):
                continue
            if len(row) != len(columns):
                raise ParseFileError(
                    f"line {line_number} has {len(row)} columns; expected 2"
                )
            parsed_row: list[float] = []
            for value in row:
                text = value.strip()
                if not text:
                    raise ParseFileError(f"line {line_number} contains an empty value")
                try:
                    number = float(text)
                except ValueError as exc:
                    raise ParseFileError(
                        f"line {line_number} contains a non-numeric value: {text!r}"
                    ) from exc
                if not math.isfinite(number):
                    raise ParseFileError(
                        f"line {line_number} contains a non-finite value: {text!r}"
                    )
                parsed_row.append(number)
            for column, number in zip(columns, parsed_row):
                signals_by_column[column].append(number)
            data_row_count += 1

    if data_row_count == 0:
        raise ParseFileError("CSV contains no data rows")

    signals: dict[str, np.ndarray] = {}
    for column, values in signals_by_column.items():
        signal = np.asarray(values, dtype=np.float32)
        if not np.isfinite(signal).all():
            raise ParseFileError(f"{column} is not finite after float32 conversion")
        signals[column] = signal
    return ParsedSignals(columns, signals, data_row_count)


def _manifest_row(
    *,
    path: Path,
    raw_root: Path,
    condition: ConditionConfig,
    bearing_id: str,
    measurement_index: int | None,
    status: str,
    file_hash: str,
    file_size: int,
    source_columns: list[str] | None = None,
    source_row_count: int | None = None,
    horizontal_length: int | None = None,
    vertical_length: int | None = None,
    error: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source_relative_path": path.relative_to(raw_root).as_posix(),
        "file_sha256": file_hash,
        "file_size_bytes": file_size,
        "condition_source_name": condition.source_name,
        "experiment_id": condition.experiment_id,
        "bearing_id": bearing_id,
        "measurement_index": measurement_index,
        "source_columns": source_columns or [],
        "source_row_count": source_row_count,
        "horizontal_signal_length": horizontal_length,
        "vertical_signal_length": vertical_length,
        "parse_status": status,
        "error": error,
        "warnings": warnings or [],
    }


def _write_parquet(path: Path, rows: list[dict[str, Any]], schema: pa.Schema) -> None:
    table = pa.Table.from_pylist(rows, schema=schema)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, compression="zstd")


def _discover_files(raw_root: Path) -> tuple[list[Path], list[str], list[str]]:
    paths: list[Path] = []
    ignored_conditions: list[str] = []
    missing_conditions: list[str] = []
    for condition_dir in sorted(raw_root.iterdir(), key=lambda item: item.name):
        if not condition_dir.is_dir():
            continue
        if condition_dir.name not in CONDITIONS:
            ignored_conditions.append(condition_dir.name)
            continue
        for bearing_dir in sorted(condition_dir.iterdir(), key=lambda item: item.name):
            if not bearing_dir.is_dir():
                continue
            paths.extend(
                sorted(
                    (item for item in bearing_dir.iterdir() if item.is_file() and item.suffix.lower() == ".csv"),
                    key=lambda item: (0, int(item.stem)) if item.stem.isdigit() else (1, item.name),
                )
            )
    for source_name in CONDITIONS:
        if not (raw_root / source_name).is_dir():
            missing_conditions.append(source_name)
    return paths, ignored_conditions, missing_conditions


def _gap_records(paths: list[Path], raw_root: Path) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], set[int]] = defaultdict(set)
    for path in paths:
        condition_name = path.parent.parent.name
        bearing_id = path.parent.name
        try:
            index = _parse_measurement_index(path)
        except ParseFileError:
            continue
        grouped[(condition_name, bearing_id)].add(index)

    gaps: list[dict[str, Any]] = []
    for (condition_name, bearing_id), indices in sorted(grouped.items()):
        if not indices:
            continue
        missing = sorted(set(range(1, max(indices) + 1)) - indices)
        if missing:
            gaps.append(
                {
                    "condition_source_name": condition_name,
                    "experiment_id": CONDITIONS[condition_name].experiment_id,
                    "bearing_id": bearing_id,
                    "missing_measurement_indices": missing,
                }
            )
    return gaps


def parse_xjtu(
    raw_root: str | Path,
    output_dir: str | Path,
    *,
    sampling_rate_hz: float = 25_600.0,
    expected_signal_length: int = EXPECTED_SIGNAL_LENGTH,
    fail_on_errors: bool = False,
) -> dict[str, Any]:
    """Parse XJTU-SY CSV files into a manifest and canonical observations.

    The raw tree is never modified. Invalid files are reported and skipped;
    ``fail_on_errors`` controls whether the caller should treat those errors as
    fatal after valid output has been written.
    """
    raw_root = Path(raw_root).resolve()
    output_dir = Path(output_dir).resolve()
    if not raw_root.is_dir():
        raise FileNotFoundError(f"raw root does not exist: {raw_root}")
    output_dir.mkdir(parents=True, exist_ok=True)

    source_paths, ignored_conditions, missing_conditions = _discover_files(raw_root)
    duplicate_indices: dict[tuple[str, str, int], list[Path]] = defaultdict(list)
    for path in source_paths:
        try:
            index = _parse_measurement_index(path)
        except ParseFileError:
            continue
        duplicate_indices[(path.parent.parent.name, path.parent.name, index)].append(path)

    manifest_rows: list[dict[str, Any]] = []
    observation_batch: list[dict[str, Any]] = []
    observation_output = output_dir / "xjtu_observations.parquet"
    observation_writer: pq.ParquetWriter | None = None
    observation_count = 0
    errors: list[dict[str, str]] = []
    warning_count = 0
    parsed_file_count = 0
    duplicate_paths = {
        path
        for paths in duplicate_indices.values()
        if len(paths) > 1
        for path in paths
    }

    def flush_observations() -> None:
        nonlocal observation_writer
        if not observation_batch:
            return
        table = pa.Table.from_pylist(observation_batch, schema=OBSERVATION_SCHEMA)
        if observation_writer is None:
            observation_writer = pq.ParquetWriter(
                observation_output, OBSERVATION_SCHEMA, compression="zstd"
            )
        observation_writer.write_table(table)
        observation_batch.clear()

    for path in source_paths:
        condition_name = path.parent.parent.name
        bearing_id = path.parent.name
        condition = CONDITIONS[condition_name]
        file_hash = _sha256(path)
        file_size = path.stat().st_size
        measurement_index: int | None = None
        try:
            measurement_index = _parse_measurement_index(path)
            if path in duplicate_paths:
                raise ParseFileError(
                    f"duplicate measurement index {measurement_index} for {bearing_id}"
                )
            parsed = _read_csv_signals(path)
            warnings: list[str] = []
            horizontal_length = len(parsed.signals[HORIZONTAL_HEADER])
            vertical_length = len(parsed.signals[VERTICAL_HEADER])
            if (
                horizontal_length != expected_signal_length
                or vertical_length != expected_signal_length
            ):
                warnings.append(
                    "waveform length differs from expected "
                    f"{expected_signal_length}: horizontal={horizontal_length}, "
                    f"vertical={vertical_length}"
                )
            elapsed_time_sec = (measurement_index - 1) * MEASUREMENT_INTERVAL_SEC
            for channel_id, header in (
                ("horizontal", HORIZONTAL_HEADER),
                ("vertical", VERTICAL_HEADER),
            ):
                signal = parsed.signals[header]
                observation_batch.append(
                    {
                        "dataset_name": DATASET_NAME,
                        "experiment_id": condition.experiment_id,
                        "bearing_id": bearing_id,
                        "measurement_index": measurement_index,
                        "elapsed_time_sec": elapsed_time_sec,
                        "rotational_speed_rpm": condition.rotational_speed_rpm,
                        "radial_load_kn": condition.radial_load_kn,
                        "channel_id": channel_id,
                        "channel_direction": channel_id,
                        "sampling_rate_hz": sampling_rate_hz,
                        "signal_length": len(signal),
                        "vibration_signal": signal.tolist(),
                    }
                )
            observation_count += 2
            if len(observation_batch) >= 128:
                flush_observations()
            manifest_rows.append(
                _manifest_row(
                    path=path,
                    raw_root=raw_root,
                    condition=condition,
                    bearing_id=bearing_id,
                    measurement_index=measurement_index,
                    status="ok",
                    file_hash=file_hash,
                    file_size=file_size,
                    source_columns=parsed.columns,
                    source_row_count=parsed.row_count,
                    horizontal_length=horizontal_length,
                    vertical_length=vertical_length,
                    warnings=warnings,
                )
            )
            parsed_file_count += 1
            warning_count += len(warnings)
        except (OSError, ParseFileError, KeyError, ValueError) as exc:
            error = str(exc)
            errors.append(
                {
                    "source_relative_path": path.relative_to(raw_root).as_posix(),
                    "error": error,
                }
            )
            manifest_rows.append(
                _manifest_row(
                    path=path,
                    raw_root=raw_root,
                    condition=condition,
                    bearing_id=bearing_id,
                    measurement_index=measurement_index,
                    status="error",
                    file_hash=file_hash,
                    file_size=file_size,
                    error=error,
                )
            )

    gaps = _gap_records(source_paths, raw_root)
    flush_observations()
    if observation_writer is not None:
        observation_writer.close()
    else:
        _write_parquet(observation_output, [], OBSERVATION_SCHEMA)
    _write_parquet(output_dir / "xjtu_source_manifest.parquet", manifest_rows, MANIFEST_SCHEMA)

    report: dict[str, Any] = {
        "schema_version": "1.0",
        "dataset_name": DATASET_NAME,
        "raw_root": str(raw_root),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "sampling_rate_hz": sampling_rate_hz,
            "measurement_interval_sec": MEASUREMENT_INTERVAL_SEC,
            "expected_signal_length": expected_signal_length,
            "conditions": {
                name: {
                    "experiment_id": config.experiment_id,
                    "rotational_speed_rpm": config.rotational_speed_rpm,
                    "radial_load_kn": config.radial_load_kn,
                }
                for name, config in CONDITIONS.items()
            },
        },
        "summary": {
            "files_discovered": len(source_paths),
            "files_parsed": parsed_file_count,
            "files_with_errors": len(errors),
            "observations_written": observation_count,
            "warning_count": warning_count,
            "trajectory_gap_count": len(gaps),
        },
        "ignored_condition_directories": ignored_conditions,
        "missing_condition_directories": missing_conditions,
        "errors": errors,
        "trajectory_gaps": gaps,
        "output_files": [
            "xjtu_source_manifest.parquet",
            "xjtu_observations.parquet",
            "xjtu_parse_report.json",
        ],
    }
    (output_dir / "xjtu_parse_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if fail_on_errors and errors:
        raise RuntimeError(f"XJTU parse completed with {len(errors)} file errors")
    return report