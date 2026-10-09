"""Schema and validation contract for causal sample manifests."""

from __future__ import annotations

import math
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ..features.xjtu import FEATURE_SCHEMA_VERSION

MANIFEST_SCHEMA_VERSION = "xjtu_sample_manifest_v1"
ALLOWED_SPLITS = frozenset(("train", "validation", "test"))
ALLOWED_SAMPLE_KINDS = frozenset(("train_dynamic", "validation_fixed", "test_fixed", "full_lifecycle_eval"))
ALLOWED_CONTEXT_REGIMES = frozenset(("main", "short_robustness"))
SPARSE_RETENTION = {
    "dense": 1.0,
    "sparse_10": 0.10,
    "sparse_5": 0.05,
    "sparse_1": 0.01,
}

SAMPLE_MANIFEST_SCHEMA = pa.schema([
    ("manifest_schema_version", pa.string()),
    ("feature_schema_version", pa.string()),
    ("sample_id", pa.string()),
    ("dataset_name", pa.string()),
    ("experiment_id", pa.string()),
    ("bearing_id", pa.string()),
    ("split", pa.string()),
    ("sample_kind", pa.string()),
    ("context_regime", pa.string()),
    ("sparse_regime", pa.string()),
    ("sparse_retention_probability", pa.float64()),
    ("sampling_seed", pa.int64()),
    ("epoch", pa.int64()),
    ("anchor_measurement_index", pa.int64()),
    ("anchor_elapsed_time_sec", pa.float64()),
    ("context_measurement_indices", pa.list_(pa.int64())),
    ("context_relative_time_sec", pa.list_(pa.float64())),
    ("context_observed_mask", pa.list_(pa.bool_())),
    ("context_count_k", pa.int64()),
    ("context_observed_count", pa.int64()),
    ("future_query_measurement_indices", pa.list_(pa.int64())),
    ("future_relative_time_sec", pa.list_(pa.float64())),
    ("future_query_count_q", pa.int64()),
    ("full_remaining_lifecycle", pa.bool_()),
    ("target_query_policy", pa.string()),
])


def _require(record: dict[str, Any], name: str) -> Any:
    value = record.get(name)
    if value is None:
        raise ValueError(f"sample manifest field is missing: {name}")
    return value


def _finite(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _check_sorted_unique(values: list[int], name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicates")
    if values != sorted(values):
        raise ValueError(f"{name} must be sorted in source chronology")


def validate_sample_manifest_record(record: dict[str, Any]) -> None:
    """Validate one sample manifest row before Parquet serialization."""
    sample_id = str(record.get("sample_id", "<unknown>"))
    if record.get("manifest_schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"{sample_id}: unsupported manifest_schema_version")
    if record.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise ValueError(f"{sample_id}: feature_schema_version does not match snapshot features")
    for name in ("dataset_name", "experiment_id", "bearing_id", "split", "sample_kind", "context_regime", "sparse_regime", "target_query_policy"):
        if not str(_require(record, name)):
            raise ValueError(f"{sample_id}: {name} must not be empty")
    if record["split"] not in ALLOWED_SPLITS:
        raise ValueError(f"{sample_id}: invalid split")
    if record["sample_kind"] not in ALLOWED_SAMPLE_KINDS:
        raise ValueError(f"{sample_id}: invalid sample_kind")
    if record["context_regime"] not in ALLOWED_CONTEXT_REGIMES:
        raise ValueError(f"{sample_id}: invalid context_regime")
    sparse_regime = record["sparse_regime"]
    if sparse_regime not in SPARSE_RETENTION:
        raise ValueError(f"{sample_id}: invalid sparse_regime")
    retention = _finite(_require(record, "sparse_retention_probability"), "sparse_retention_probability")
    if not math.isclose(retention, SPARSE_RETENTION[sparse_regime], rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"{sample_id}: sparse retention does not match sparse_regime")
    seed = _require(record, "sampling_seed")
    if not isinstance(seed, int) or seed < 0:
        raise ValueError(f"{sample_id}: sampling_seed must be a non-negative integer")
    _finite(_require(record, "anchor_elapsed_time_sec"), "anchor_elapsed_time_sec")
    anchor_index = _require(record, "anchor_measurement_index")
    if not isinstance(anchor_index, int) or anchor_index < 1:
        raise ValueError(f"{sample_id}: anchor_measurement_index must be positive")

    context_indices = [int(value) for value in _require(record, "context_measurement_indices")]
    context_times = [_finite(value, "context_relative_time_sec") for value in _require(record, "context_relative_time_sec")]
    context_mask = [bool(value) for value in _require(record, "context_observed_mask")]
    context_count = _require(record, "context_count_k")
    observed_count = _require(record, "context_observed_count")
    if not isinstance(context_count, int) or context_count != len(context_indices):
        raise ValueError(f"{sample_id}: context_count_k does not match context indices")
    if len(context_times) != context_count or len(context_mask) != context_count:
        raise ValueError(f"{sample_id}: context arrays must have equal length K")
    if context_count < 1:
        raise ValueError(f"{sample_id}: context must not be empty")
    if record["context_regime"] == "main" and not 10 <= context_count <= 20:
        raise ValueError(f"{sample_id}: main context_count_k must be between 10 and 20")
    if record["context_regime"] == "short_robustness" and not 3 <= context_count <= 9:
        raise ValueError(f"{sample_id}: short context_count_k must be between 3 and 9")
    if not isinstance(observed_count, int) or observed_count != sum(context_mask):
        raise ValueError(f"{sample_id}: context_observed_count does not match context mask")
    _check_sorted_unique(context_indices, "context_measurement_indices")
    if anchor_index not in context_indices or not context_mask[context_indices.index(anchor_index)]:
        raise ValueError(f"{sample_id}: anchor must be present and observed in context")
    if any(time > 1e-9 for time in context_times) or not math.isclose(context_times[-1], 0.0, abs_tol=1e-9):
        raise ValueError(f"{sample_id}: context relative times must end at anchor time 0")
    if any(context_times[index] >= context_times[index + 1] for index in range(len(context_times) - 1)):
        raise ValueError(f"{sample_id}: context relative times must be strictly increasing")
    if sparse_regime == "dense" and observed_count != context_count:
        raise ValueError(f"{sample_id}: dense context must retain every selected record")

    future_indices = [int(value) for value in _require(record, "future_query_measurement_indices")]
    future_times = [_finite(value, "future_relative_time_sec") for value in _require(record, "future_relative_time_sec")]
    query_count = _require(record, "future_query_count_q")
    if not isinstance(query_count, int) or query_count != len(future_indices) or len(future_times) != query_count:
        raise ValueError(f"{sample_id}: future query arrays must have equal length Q")
    if query_count < 1:
        raise ValueError(f"{sample_id}: future query set must not be empty")
    _check_sorted_unique(future_indices, "future_query_measurement_indices")
    if any(index in context_indices for index in future_indices):
        raise ValueError(f"{sample_id}: future queries must not overlap context")
    if any(time <= 0.0 for time in future_times):
        raise ValueError(f"{sample_id}: future relative times must be strictly positive")
    if any(future_times[index] >= future_times[index + 1] for index in range(len(future_times) - 1)):
        raise ValueError(f"{sample_id}: future relative times must be strictly increasing")
    full_lifecycle = bool(_require(record, "full_remaining_lifecycle"))
    policy = record["target_query_policy"]
    if full_lifecycle and policy != "all_observed_future":
        raise ValueError(f"{sample_id}: full lifecycle samples require all_observed_future policy")
    if not full_lifecycle and policy != "random_observed_future":
        raise ValueError(f"{sample_id}: random samples require random_observed_future policy")


def validate_sample_manifest(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate and materialize an iterable of manifest rows."""
    materialized = list(records)
    for record in materialized:
        validate_sample_manifest_record(record)
    sample_ids = [record["sample_id"] for record in materialized]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("sample_id values must be unique within one manifest")
    return materialized


def write_sample_manifest(path: str | Path, records: Iterable[dict[str, Any]]) -> None:
    """Validate and write a sample manifest Parquet file."""
    materialized = validate_sample_manifest(records)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(materialized, schema=SAMPLE_MANIFEST_SCHEMA), output_path, compression="zstd")


def read_sample_manifest(path: str | Path) -> list[dict[str, Any]]:
    """Read and validate a sample manifest Parquet file."""
    records = pq.read_table(path).to_pylist()
    return validate_sample_manifest(records)
