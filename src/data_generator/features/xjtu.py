"""Leakage-safe fixed-dimensional signal features for XJTU-SY."""

from __future__ import annotations

import itertools
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from ..ingestion.xjtu import DATASET_NAME

FEATURE_SCHEMA_VERSION = "xjtu_feature_v1"
CHANNELS = ("horizontal", "vertical")
CHANNEL_FEATURE_NAMES = (
    "mean", "std", "rms", "peak_abs", "peak_to_peak", "kurtosis", "crest_factor",
    "dominant_frequency_hz", "dominant_amplitude", "total_spectral_power", "spectral_entropy",
    "band_power_0_1000_hz", "band_power_1000_5000_hz", "band_power_5000_10000_hz",
    "band_power_10000_12800_hz",
)
SNAPSHOT_FEATURE_NAMES = tuple(
    f"{channel}__{name}" for channel in CHANNELS for name in CHANNEL_FEATURE_NAMES
)
FEATURE_DIMENSION = len(SNAPSHOT_FEATURE_NAMES)
SPECTRAL_BANDS_HZ = ((0.0, 1_000.0), (1_000.0, 5_000.0), (5_000.0, 10_000.0), (10_000.0, 12_800.0))
HIGH_CORRELATION_THRESHOLD = 0.99
ROBUST_OUTLIER_THRESHOLD = 7.0
VALIDATION_BEARINGS = frozenset(("Bearing1_5", "Bearing2_5"))

OBSERVATION_FEATURE_SCHEMA = pa.schema([
    ("dataset_name", pa.string()), ("experiment_id", pa.string()), ("bearing_id", pa.string()),
    ("measurement_index", pa.int64()), ("elapsed_time_sec", pa.float64()),
    ("rotational_speed_rpm", pa.float64()), ("radial_load_kn", pa.float64()),
    ("channel_id", pa.string()), ("channel_direction", pa.string()),
    ("sampling_rate_hz", pa.float64()), ("signal_length", pa.int64()), ("split", pa.string()),
    ("feature_schema_version", pa.string()), ("raw_feature_vector", pa.list_(pa.float32())),
    ("feature_vector", pa.list_(pa.float32())), ("feature_valid_mask", pa.list_(pa.bool_())),
])

SNAPSHOT_FEATURE_SCHEMA = pa.schema([
    ("dataset_name", pa.string()), ("experiment_id", pa.string()), ("bearing_id", pa.string()),
    ("measurement_index", pa.int64()), ("elapsed_time_sec", pa.float64()), ("split", pa.string()),
    ("rotational_speed_rpm", pa.float64()), ("radial_load_kn", pa.float64()),
    ("horizontal_present", pa.bool_()), ("vertical_present", pa.bool_()),
    ("feature_schema_version", pa.string()), ("feature_dimension", pa.int64()),
    ("raw_feature_vector", pa.list_(pa.float32())), ("feature_vector", pa.list_(pa.float32())),
    ("feature_valid_mask", pa.list_(pa.bool_())),
])


def _key(row: dict[str, Any]) -> tuple[str, str, str, int]:
    return row["dataset_name"], row["experiment_id"], row["bearing_id"], int(row["measurement_index"])


def _split_for(experiment_id: str, bearing_id: str) -> str:
    if experiment_id == "condition_3":
        return "test"
    if bearing_id in VALIDATION_BEARINGS:
        return "validation"
    return "train"


def _time_features(values: np.ndarray) -> dict[str, float]:
    names = CHANNEL_FEATURE_NAMES[:7]
    if values.size == 0 or not np.isfinite(values).all():
        return {name: float("nan") for name in names}
    mean = float(np.mean(values))
    centered = values - mean
    variance = float(np.mean(np.square(centered)))
    std = float(np.sqrt(variance))
    rms = float(np.sqrt(np.mean(np.square(values))))
    peak_abs = float(np.max(np.abs(values)))
    return {
        "mean": mean, "std": std, "rms": rms, "peak_abs": peak_abs,
        "peak_to_peak": float(np.ptp(values)),
        "kurtosis": float(np.mean(np.power(centered, 4)) / (variance**2))
        if values.size > 3 and variance > 0.0 else float("nan"),
        "crest_factor": peak_abs / rms if rms > 0.0 else float("nan"),
    }


def _spectral_features(values: np.ndarray, sampling_rate_hz: float) -> dict[str, float]:
    names = CHANNEL_FEATURE_NAMES[7:]
    empty = {name: float("nan") for name in names}
    if values.size < 2 or not np.isfinite(values).all() or sampling_rate_hz <= 0.0:
        return empty
    window = np.hanning(values.size)
    window_sum = float(np.sum(window))
    if window_sum <= 0.0:
        window = np.ones(values.size)
        window_sum = float(values.size)
    centered = values - np.mean(values)
    frequencies = np.fft.rfftfreq(values.size, d=1.0 / sampling_rate_hz)
    magnitude = np.abs(np.fft.rfft(centered * window)) / window_sum * 2.0
    magnitude[0] /= 2.0
    if values.size % 2 == 0:
        magnitude[-1] /= 2.0
    power = np.square(magnitude)
    total_power = float(np.sum(power))
    if not np.isfinite(total_power) or total_power <= 0.0:
        return {
            "dominant_frequency_hz": float(frequencies[1]) if frequencies.size > 1 else float("nan"),
            "dominant_amplitude": 0.0, "total_spectral_power": total_power,
            "spectral_entropy": float("nan"), **{name: 0.0 for name in CHANNEL_FEATURE_NAMES[11:]},
        }
    dominant = int(np.argmax(magnitude[1:]) + 1) if magnitude.size > 1 else 0
    probabilities = power / total_power
    positive = probabilities[probabilities > 0.0]
    entropy = float(-np.sum(positive * np.log(positive)) / np.log(probabilities.size))
    bands: list[float] = []
    for low, high in SPECTRAL_BANDS_HZ:
        mask = (frequencies >= low) & ((frequencies <= high) if high >= sampling_rate_hz / 2.0 else (frequencies < high))
        bands.append(float(np.sum(power[mask])))
    return {
        "dominant_frequency_hz": float(frequencies[dominant]),
        "dominant_amplitude": float(magnitude[dominant]),
        "total_spectral_power": total_power, "spectral_entropy": entropy,
        "band_power_0_1000_hz": bands[0], "band_power_1000_5000_hz": bands[1],
        "band_power_5000_10000_hz": bands[2], "band_power_10000_12800_hz": bands[3],
    }


def extract_channel_features(signal: Any, sampling_rate_hz: float) -> dict[str, float]:
    """Return the 15 deterministic scalar features for one channel."""
    values = np.asarray(signal, dtype=np.float64)
    features = _time_features(values)
    features.update(_spectral_features(values, float(sampling_rate_hz)))
    return {name: float(features[name]) for name in CHANNEL_FEATURE_NAMES}


def _feature_vector(features: dict[str, float]) -> list[float]:
    return [float(features[name]) for name in CHANNEL_FEATURE_NAMES]


def _feature_row(row: dict[str, Any]) -> dict[str, Any]:
    features = extract_channel_features(row["vibration_signal"], row["sampling_rate_hz"])
    return {
        "dataset_name": row["dataset_name"], "experiment_id": row["experiment_id"], "bearing_id": row["bearing_id"],
        "measurement_index": int(row["measurement_index"]), "elapsed_time_sec": float(row["elapsed_time_sec"]),
        "rotational_speed_rpm": float(row["rotational_speed_rpm"]), "radial_load_kn": float(row["radial_load_kn"]),
        "channel_id": row["channel_id"], "channel_direction": row["channel_direction"],
        "sampling_rate_hz": float(row["sampling_rate_hz"]), "signal_length": int(row["signal_length"]),
        "split": _split_for(row["experiment_id"], row["bearing_id"]),
        "feature_schema_version": FEATURE_SCHEMA_VERSION, "_features": features,
    }


def _fit_scaler(rows: list[dict[str, Any]]) -> dict[str, Any]:
    train_rows = [row for row in rows if row["split"] == "train"]
    means: dict[str, float] = {}
    scales: dict[str, float] = {}
    finite_counts: dict[str, int] = {}
    for name in CHANNEL_FEATURE_NAMES:
        values = np.asarray([row["_features"][name] for row in train_rows], dtype=np.float64)
        finite = values[np.isfinite(values)]
        finite_counts[name] = int(finite.size)
        if finite.size == 0:
            means[name], scales[name] = 0.0, 1.0
        else:
            means[name] = float(np.mean(finite))
            std = float(np.std(finite))
            scales[name] = std if std > 0.0 and np.isfinite(std) else 1.0
    return {
        "schema_version": FEATURE_SCHEMA_VERSION, "method": "zscore_population", "fit_split": "train",
        "feature_names_per_channel": list(CHANNEL_FEATURE_NAMES), "feature_names": list(SNAPSHOT_FEATURE_NAMES),
        "means_per_channel": means, "scales_per_channel": scales,
        "finite_train_counts_per_channel": finite_counts,
        "missing_value_policy": "replace with train mean, then standardized value 0; preserve validity mask",
        "split_definition": {
            "test": "experiment_id == condition_3",
            "validation": "bearing_id in Bearing1_5, Bearing2_5 outside condition_3",
            "train": "all remaining bearings",
        },
    }


def _standardize_vector(raw_vector: list[float], scaler: dict[str, Any]) -> tuple[list[float], list[bool]]:
    standardized: list[float] = []
    valid: list[bool] = []
    means = scaler["means_per_channel"]
    scales = scaler["scales_per_channel"]
    for value, name in zip(raw_vector, CHANNEL_FEATURE_NAMES):
        is_valid = bool(np.isfinite(value))
        valid.append(is_valid)
        standardized.append(float((value - means[name]) / scales[name]) if is_valid else 0.0)
    return standardized, valid


def _write_table(path: Path, rows: list[dict[str, Any]], schema: pa.Schema) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path, compression="zstd")


def _finite_stats(values: np.ndarray) -> tuple[float, float, int]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return 0.0, 0.0, 0
    median = float(np.median(finite))
    return median, float(np.median(np.abs(finite - median))), int(finite.size)


def _validation_report(snapshot_rows: list[dict[str, Any]], scaler: dict[str, Any]) -> dict[str, Any]:
    raw = np.asarray([row["_raw_vector"] for row in snapshot_rows], dtype=np.float64)
    normalized = np.asarray([row["feature_vector"] for row in snapshot_rows], dtype=np.float64)
    train_mask = np.asarray([row["_split"] == "train" for row in snapshot_rows], dtype=bool)
    train_raw = raw[train_mask]
    per_feature: dict[str, Any] = {}
    outlier_counts: dict[str, int] = {}
    for index, name in enumerate(SNAPSHOT_FEATURE_NAMES):
        values = raw[:, index]
        finite = values[np.isfinite(values)]
        reference_values = train_raw[:, index] if train_raw.size else values
        median, mad, reference_finite_count = _finite_stats(reference_values)
        finite_count = int(finite.size)
        if mad > 0.0:
            outliers = np.abs(0.6745 * (values - median) / mad) > ROBUST_OUTLIER_THRESHOLD
        elif finite_count > 0:
            q1, q3 = np.percentile(finite, [25.0, 75.0])
            iqr = q3 - q1
            outliers = np.abs(values - median) > 1.5 * iqr if iqr > 0.0 else np.zeros(values.shape, dtype=bool)
        else:
            outliers = np.zeros(values.shape, dtype=bool)
        outliers &= np.isfinite(values)
        outlier_counts[name] = int(np.sum(outliers))
        per_feature[name] = {
            "finite_count": finite_count, "nan_count": int(np.sum(np.isnan(values))),
            "inf_count": int(np.sum(np.isinf(values))),
            "constant": bool(finite_count > 0 and np.ptp(finite) <= 1e-12),
            "outlier_count": outlier_counts[name],
            "outlier_rate_over_finite": float(outlier_counts[name] / finite_count) if finite_count else 0.0,
            "outlier_reference_finite_count": reference_finite_count,
        }

    high_correlations: list[dict[str, Any]] = []
    for left, right in itertools.combinations(range(raw.shape[1]), 2):
        mask = np.isfinite(raw[:, left]) & np.isfinite(raw[:, right])
        if int(np.sum(mask)) < 2:
            continue
        left_values, right_values = raw[mask, left], raw[mask, right]
        if np.ptp(left_values) <= 1e-12 or np.ptp(right_values) <= 1e-12:
            continue
        correlation = float(np.corrcoef(left_values, right_values)[0, 1])
        if np.isfinite(correlation) and abs(correlation) >= HIGH_CORRELATION_THRESHOLD:
            high_correlations.append({
                "feature_a": SNAPSHOT_FEATURE_NAMES[left], "feature_b": SNAPSHOT_FEATURE_NAMES[right],
                "correlation": correlation, "absolute_correlation": abs(correlation),
            })

    normalized_nonfinite = int(np.sum(~np.isfinite(normalized)))
    constants = [name for name, item in per_feature.items() if item["constant"]]
    status = "pass" if normalized_nonfinite == 0 else "fail"
    if status == "pass" and (constants or high_correlations or any(outlier_counts.values())):
        status = "pass_with_warnings"
    return {
        "schema_version": "1.0", "feature_schema_version": FEATURE_SCHEMA_VERSION, "status": status,
        "configuration": {
            "high_correlation_threshold": HIGH_CORRELATION_THRESHOLD,
            "outlier_method": "modified_z_score_with_iqr_fallback",
            "modified_z_score_threshold": ROBUST_OUTLIER_THRESHOLD,
            "outliers_are_reported_not_removed": True, "normalization": scaler["method"],
        },
        "summary": {
            "snapshot_rows": len(snapshot_rows), "feature_dimension": FEATURE_DIMENSION,
            "raw_nan_total": int(np.sum(np.isnan(raw))), "raw_inf_total": int(np.sum(np.isinf(raw))),
            "normalized_nonfinite_total": normalized_nonfinite, "constant_feature_count": len(constants),
            "high_correlation_pair_count": len(high_correlations), "outlier_total": int(sum(outlier_counts.values())),
        },
        "per_feature": per_feature,
        "high_correlation_pairs": sorted(high_correlations, key=lambda item: -item["absolute_correlation"]),
    }


def run_xjtu_features(observations_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Create per-observation and fixed-dimensional per-snapshot features."""
    observations_path, output_dir = Path(observations_path).resolve(), Path(output_dir).resolve()
    if not observations_path.is_file():
        raise FileNotFoundError(f"observations do not exist: {observations_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    columns = [
        "dataset_name", "experiment_id", "bearing_id", "measurement_index", "elapsed_time_sec",
        "rotational_speed_rpm", "radial_load_kn", "channel_id", "channel_direction", "sampling_rate_hz",
        "signal_length", "vibration_signal",
    ]
    for batch in pq.ParquetFile(observations_path).iter_batches(columns=columns, batch_size=8):
        rows.extend(_feature_row(row) for row in batch.to_pylist())
    rows.sort(key=lambda row: (*_key(row), row["channel_id"]))
    scaler = _fit_scaler(rows)

    observation_output: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        raw_vector = _feature_vector(row["_features"])
        standardized, valid = _standardize_vector(raw_vector, scaler)
        observation_output.append({
            **{name: row[name] for name in OBSERVATION_FEATURE_SCHEMA.names if name in row},
            "raw_feature_vector": raw_vector, "feature_vector": standardized, "feature_valid_mask": valid,
        })
        grouped[_key(row)][row["channel_id"]] = {
            "row": row, "raw_vector": raw_vector, "standardized": standardized, "valid": valid,
        }

    snapshot_output: list[dict[str, Any]] = []
    snapshot_internal: list[dict[str, Any]] = []
    for key in sorted(grouped):
        channels = grouped[key]
        first = next(iter(channels.values()))["row"]
        raw_vector: list[float] = []
        standardized: list[float] = []
        valid: list[bool] = []
        for channel in CHANNELS:
            item = channels.get(channel)
            if item is None:
                raw_vector.extend([float("nan")] * len(CHANNEL_FEATURE_NAMES))
                standardized.extend([0.0] * len(CHANNEL_FEATURE_NAMES))
                valid.extend([False] * len(CHANNEL_FEATURE_NAMES))
            else:
                raw_vector.extend(item["raw_vector"])
                standardized.extend(item["standardized"])
                valid.extend(item["valid"])
        snapshot_output.append({
            "dataset_name": first["dataset_name"], "experiment_id": first["experiment_id"],
            "bearing_id": first["bearing_id"], "measurement_index": first["measurement_index"],
            "elapsed_time_sec": first["elapsed_time_sec"], "split": first["split"],
            "rotational_speed_rpm": first["rotational_speed_rpm"], "radial_load_kn": first["radial_load_kn"],
            "horizontal_present": "horizontal" in channels, "vertical_present": "vertical" in channels,
            "feature_schema_version": FEATURE_SCHEMA_VERSION, "feature_dimension": FEATURE_DIMENSION,
            "raw_feature_vector": raw_vector, "feature_vector": standardized, "feature_valid_mask": valid,
        })
        snapshot_internal.append({"_raw_vector": raw_vector, "feature_vector": standardized, "_split": first["split"]})

    validation = _validation_report(snapshot_internal, scaler)
    _write_table(output_dir / "xjtu_observation_features.parquet", observation_output, OBSERVATION_FEATURE_SCHEMA)
    _write_table(output_dir / "xjtu_snapshot_features.parquet", snapshot_output, SNAPSHOT_FEATURE_SCHEMA)
    (output_dir / "xjtu_feature_scaler.json").write_text(json.dumps(scaler, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "xjtu_feature_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")

    split_counts = {split: sum(row["split"] == split for row in snapshot_output) for split in ("train", "validation", "test")}
    report = {
        "schema_version": "1.0", "dataset_name": DATASET_NAME, "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "inputs": {"observations": str(observations_path)},
        "configuration": {
            "feature_names_per_channel": list(CHANNEL_FEATURE_NAMES), "feature_names": list(SNAPSHOT_FEATURE_NAMES),
            "feature_dimension": FEATURE_DIMENSION, "spectral_preprocessing": "mean_centered_hann_real_one_sided_fft",
            "spectral_entropy": "normalized_shannon_entropy_of_power_spectrum", "normalization": scaler["method"],
            "fit_split": "train", "stft": "deferred",
        },
        "summary": {
            "observation_feature_rows": len(observation_output), "snapshot_feature_rows": len(snapshot_output),
            "split_snapshot_rows": split_counts, "feature_dimension": FEATURE_DIMENSION,
            "validation_status": validation["status"],
        },
        "output_files": [
            "xjtu_observation_features.parquet", "xjtu_snapshot_features.parquet", "xjtu_feature_scaler.json",
            "xjtu_feature_validation.json", "xjtu_feature_report.json",
        ],
    }
    (output_dir / "xjtu_feature_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
