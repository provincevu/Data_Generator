from __future__ import annotations

import pyarrow.parquet as pq
import pytest

from data_generator.features.xjtu import FEATURE_SCHEMA_VERSION
from data_generator.sampling.manifest import (
    MANIFEST_SCHEMA_VERSION,
    SAMPLE_MANIFEST_SCHEMA,
    read_sample_manifest,
    validate_sample_manifest_record,
    write_sample_manifest,
)


def _record() -> dict:
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "sample_id": "sample-001",
        "dataset_name": "XJTU-SY",
        "experiment_id": "condition_1",
        "bearing_id": "Bearing1_1",
        "split": "train",
        "sample_kind": "train_dynamic",
        "context_regime": "main",
        "sparse_regime": "dense",
        "sparse_retention_probability": 1.0,
        "sampling_seed": 17,
        "epoch": 0,
        "anchor_measurement_index": 10,
        "anchor_elapsed_time_sec": 540.0,
        "context_measurement_indices": list(range(1, 11)),
        "context_relative_time_sec": [-540.0, -480.0, -420.0, -360.0, -300.0, -240.0, -180.0, -120.0, -60.0, 0.0],
        "context_observed_mask": [True] * 10,
        "context_count_k": 10,
        "context_observed_count": 10,
        "future_query_measurement_indices": [11, 12, 13],
        "future_relative_time_sec": [60.0, 120.0, 180.0],
        "future_query_count_q": 3,
        "full_remaining_lifecycle": False,
        "target_query_policy": "random_observed_future",
    }


def test_manifest_schema_round_trip_and_validation(tmp_path):
    path = tmp_path / "sample_manifest.parquet"
    write_sample_manifest(path, [_record()])
    assert pq.read_table(path).schema == SAMPLE_MANIFEST_SCHEMA
    rows = read_sample_manifest(path)
    assert rows[0]["context_count_k"] == 10
    assert rows[0]["future_query_count_q"] == 3


def test_manifest_rejects_future_overlap_and_bad_context_order():
    record = _record()
    record["future_query_measurement_indices"] = [10]
    record["future_relative_time_sec"] = [60.0]
    record["future_query_count_q"] = 1
    with pytest.raises(ValueError, match="must not overlap"):
        validate_sample_manifest_record(record)

    record = _record()
    record["context_relative_time_sec"] = [0.0] + record["context_relative_time_sec"][1:]
    with pytest.raises(ValueError, match="strictly increasing"):
        validate_sample_manifest_record(record)


def test_manifest_allows_short_robustness_and_sparse_mask():
    record = _record()
    record.update({
        "sample_id": "sample-short",
        "context_regime": "short_robustness",
        "sparse_regime": "sparse_10",
        "sparse_retention_probability": 0.10,
        "context_measurement_indices": [8, 9, 10],
        "context_relative_time_sec": [-120.0, -60.0, 0.0],
        "context_observed_mask": [False, True, True],
        "context_count_k": 3,
        "context_observed_count": 2,
    })
    validate_sample_manifest_record(record)
