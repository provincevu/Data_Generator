"""Materialize causal sample manifests into padded NumPy batches."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

from ..features.xjtu import FEATURE_DIMENSION, FEATURE_SCHEMA_VERSION
from ..sampling.manifest import validate_sample_manifest_record

SnapshotKey = tuple[str, str, str, int]


@dataclass(frozen=True)
class SnapshotRecord:
    """One normalized snapshot row required by the batch materializer."""

    feature_vector: np.ndarray
    feature_valid_mask: np.ndarray
    elapsed_time_sec: float
    split: str


class SnapshotFeatureStore:
    """In-memory index over the canonical fixed-dimensional snapshot table."""

    def __init__(self, records: dict[SnapshotKey, SnapshotRecord]) -> None:
        self._records = records

    @classmethod
    def from_parquet(cls, path: str | Path) -> SnapshotFeatureStore:
        table = pq.read_table(path)
        required = {
            "dataset_name", "experiment_id", "bearing_id", "measurement_index",
            "elapsed_time_sec", "split", "feature_schema_version", "feature_dimension",
            "feature_vector", "feature_valid_mask",
        }
        missing = sorted(required.difference(table.column_names))
        if missing:
            raise ValueError(f"snapshot table is missing required columns: {', '.join(missing)}")

        records: dict[SnapshotKey, SnapshotRecord] = {}
        for row in table.to_pylist():
            key = (
                str(row["dataset_name"]),
                str(row["experiment_id"]),
                str(row["bearing_id"]),
                int(row["measurement_index"]),
            )
            if key in records:
                raise ValueError(f"duplicate snapshot key: {key}")
            if row["feature_schema_version"] != FEATURE_SCHEMA_VERSION:
                raise ValueError(f"unsupported feature schema for snapshot: {key}")
            if int(row["feature_dimension"]) != FEATURE_DIMENSION:
                raise ValueError(f"unsupported feature dimension for snapshot: {key}")

            vector = np.asarray(row["feature_vector"], dtype=np.float32)
            valid_mask = np.asarray(row["feature_valid_mask"], dtype=bool)
            if vector.shape != (FEATURE_DIMENSION,) or valid_mask.shape != (FEATURE_DIMENSION,):
                raise ValueError(f"snapshot feature arrays must have dimension {FEATURE_DIMENSION}: {key}")
            if not np.isfinite(vector).all():
                raise ValueError(f"snapshot feature vector contains NaN or Inf: {key}")
            records[key] = SnapshotRecord(
                feature_vector=vector,
                feature_valid_mask=valid_mask,
                elapsed_time_sec=float(row["elapsed_time_sec"]),
                split=str(row["split"]),
            )
        return cls(records)

    def get(self, key: SnapshotKey) -> SnapshotRecord:
        try:
            return self._records[key]
        except KeyError as exc:
            raise ValueError(f"manifest references missing snapshot: {key}") from exc

    def __len__(self) -> int:
        return len(self._records)


def _key_from_manifest(record: dict[str, Any], measurement_index: int) -> SnapshotKey:
    return (
        str(record["dataset_name"]),
        str(record["experiment_id"]),
        str(record["bearing_id"]),
        int(measurement_index),
    )


def _check_snapshot_split(
    snapshot: SnapshotRecord,
    manifest_record: dict[str, Any],
    measurement_index: int,
) -> None:
    if snapshot.split != manifest_record["split"]:
        raise ValueError(
            f"snapshot {measurement_index} belongs to split {snapshot.split!r}, "
            f"not manifest split {manifest_record['split']!r}"
        )


def _masked_vector(snapshot: SnapshotRecord, observed: bool) -> tuple[np.ndarray, np.ndarray]:
    mask = snapshot.feature_valid_mask.copy()
    if not observed:
        mask.fill(False)
    vector = snapshot.feature_vector.copy()
    vector[~mask] = 0.0
    return vector, mask


def materialize_example(
    manifest_record: dict[str, Any],
    snapshot_store: SnapshotFeatureStore,
) -> dict[str, Any]:
    """Materialize one manifest row without exposing identity metadata as tensors."""
    validate_sample_manifest_record(manifest_record)

    anchor_index = int(manifest_record["anchor_measurement_index"])
    anchor = snapshot_store.get(_key_from_manifest(manifest_record, anchor_index))
    _check_snapshot_split(anchor, manifest_record, anchor_index)

    context_indices = [int(value) for value in manifest_record["context_measurement_indices"]]
    context_times = np.asarray(manifest_record["context_relative_time_sec"], dtype=np.float32)
    context_observed = [bool(value) for value in manifest_record["context_observed_mask"]]
    context_features = np.zeros((len(context_indices), FEATURE_DIMENSION), dtype=np.float32)
    context_mask = np.zeros((len(context_indices), FEATURE_DIMENSION), dtype=bool)

    for position, measurement_index in enumerate(context_indices):
        snapshot = snapshot_store.get(_key_from_manifest(manifest_record, measurement_index))
        _check_snapshot_split(snapshot, manifest_record, measurement_index)
        context_features[position], context_mask[position] = _masked_vector(
            snapshot,
            context_observed[position],
        )

    future_indices = [int(value) for value in manifest_record["future_query_measurement_indices"]]
    future_times = np.asarray(manifest_record["future_relative_time_sec"], dtype=np.float32)
    future_targets = np.zeros((len(future_indices), FEATURE_DIMENSION), dtype=np.float32)
    future_target_mask = np.zeros((len(future_indices), FEATURE_DIMENSION), dtype=bool)

    for position, measurement_index in enumerate(future_indices):
        snapshot = snapshot_store.get(_key_from_manifest(manifest_record, measurement_index))
        _check_snapshot_split(snapshot, manifest_record, measurement_index)
        future_targets[position], future_target_mask[position] = _masked_vector(snapshot, True)

    return {
        "context_features": context_features,
        "context_relative_time": context_times,
        "context_mask": context_mask,
        "future_query_time": future_times,
        "future_targets": future_targets,
        "future_target_mask": future_target_mask,
        "context_length": np.int64(len(context_indices)),
        "future_length": np.int64(len(future_indices)),
        "sample_id": str(manifest_record["sample_id"]),
    }


def collate_examples(examples: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Pad variable-K and variable-Q examples into one batch of NumPy arrays."""
    materialized = list(examples)
    if not materialized:
        raise ValueError("cannot collate an empty example list")

    feature_dimensions = {
        int(example["context_features"].shape[-1])
        for example in materialized
    } | {
        int(example["future_targets"].shape[-1])
        for example in materialized
    }
    if feature_dimensions != {FEATURE_DIMENSION}:
        raise ValueError(f"all examples must use feature dimension {FEATURE_DIMENSION}")

    batch_size = len(materialized)
    max_context = max(int(example["context_features"].shape[0]) for example in materialized)
    max_future = max(int(example["future_targets"].shape[0]) for example in materialized)

    context_features = np.zeros((batch_size, max_context, FEATURE_DIMENSION), dtype=np.float32)
    context_relative_time = np.zeros((batch_size, max_context), dtype=np.float32)
    context_mask = np.zeros((batch_size, max_context, FEATURE_DIMENSION), dtype=bool)
    future_query_time = np.zeros((batch_size, max_future), dtype=np.float32)
    future_targets = np.zeros((batch_size, max_future, FEATURE_DIMENSION), dtype=np.float32)
    future_target_mask = np.zeros((batch_size, max_future, FEATURE_DIMENSION), dtype=bool)
    context_lengths = np.zeros(batch_size, dtype=np.int64)
    future_lengths = np.zeros(batch_size, dtype=np.int64)
    sample_ids: list[str] = []

    for batch_index, example in enumerate(materialized):
        context_length = int(example["context_features"].shape[0])
        future_length = int(example["future_targets"].shape[0])
        context_features[batch_index, :context_length] = example["context_features"]
        context_relative_time[batch_index, :context_length] = example["context_relative_time"]
        context_mask[batch_index, :context_length] = example["context_mask"]
        future_query_time[batch_index, :future_length] = example["future_query_time"]
        future_targets[batch_index, :future_length] = example["future_targets"]
        future_target_mask[batch_index, :future_length] = example["future_target_mask"]
        context_lengths[batch_index] = context_length
        future_lengths[batch_index] = future_length
        sample_ids.append(str(example["sample_id"]))

    return {
        "context_features": context_features,
        "context_relative_time": context_relative_time,
        "context_mask": context_mask,
        "future_query_time": future_query_time,
        "future_targets": future_targets,
        "future_target_mask": future_target_mask,
        "context_lengths": context_lengths,
        "future_lengths": future_lengths,
        "sample_ids": sample_ids,
    }


def materialize_batch(
    snapshot_path: str | Path,
    manifest_records: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Load a snapshot table and materialize a batch from manifest records."""
    store = SnapshotFeatureStore.from_parquet(snapshot_path)
    return collate_examples(materialize_example(record, store) for record in manifest_records)


__all__ = [
    "SnapshotFeatureStore",
    "collate_examples",
    "materialize_batch",
    "materialize_example",
]

