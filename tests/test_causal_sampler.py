from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq

from data_generator.features.xjtu import (
    FEATURE_DIMENSION,
    FEATURE_SCHEMA_VERSION,
    SNAPSHOT_FEATURE_SCHEMA,
)
from data_generator.sampling.causal import sample_causal_manifest
from data_generator.sampling.manifest import read_sample_manifest


def _write_snapshot_table(path, count: int = 40) -> None:
    rows = []
    for measurement_index in range(1, count + 1):
        rows.append({
            "dataset_name": "XJTU-SY",
            "experiment_id": "condition_1",
            "bearing_id": "Bearing1_1",
            "measurement_index": measurement_index,
            "elapsed_time_sec": float((measurement_index - 1) * 60),
            "split": "train",
            "rotational_speed_rpm": 2100.0,
            "radial_load_kn": 12.0,
            "horizontal_present": True,
            "vertical_present": True,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "feature_dimension": FEATURE_DIMENSION,
            "raw_feature_vector": [float(measurement_index)] * FEATURE_DIMENSION,
            "feature_vector": [float(measurement_index)] * FEATURE_DIMENSION,
            "feature_valid_mask": [True] * FEATURE_DIMENSION,
        })
    pq.write_table(pa.Table.from_pylist(rows, schema=SNAPSHOT_FEATURE_SCHEMA), path)


def test_causal_sampler_is_deterministic_and_causal(tmp_path):
    snapshot_path = tmp_path / "snapshots.parquet"
    output_a = tmp_path / "manifest_a.parquet"
    output_b = tmp_path / "manifest_b.parquet"
    _write_snapshot_table(snapshot_path)

    report = sample_causal_manifest(
        snapshot_path,
        output_a,
        split="train",
        seed=123,
        epoch=2,
        anchors_per_trajectory=3,
    )
    sample_causal_manifest(
        snapshot_path,
        output_b,
        split="train",
        seed=123,
        epoch=2,
        anchors_per_trajectory=3,
    )

    rows = read_sample_manifest(output_a)
    assert rows == read_sample_manifest(output_b)
    assert report["summary"]["sample_count"] == 3
    assert report["summary"]["eligible_anchor_count"] == 30
    for row in rows:
        assert 10 <= row["context_count_k"] <= 20
        assert row["context_observed_count"] == row["context_count_k"]
        assert row["anchor_measurement_index"] == row["context_measurement_indices"][-1]
        assert row["context_relative_time_sec"][-1] == 0.0
        assert all(index > row["anchor_measurement_index"] for index in row["future_query_measurement_indices"])
        assert all(time > 0.0 for time in row["future_relative_time_sec"])


def test_causal_sampler_supports_short_sparse_and_full_lifecycle_modes(tmp_path):
    snapshot_path = tmp_path / "snapshots.parquet"
    sparse_output = tmp_path / "sparse.parquet"
    full_output = tmp_path / "full.parquet"
    _write_snapshot_table(snapshot_path)

    sample_causal_manifest(
        snapshot_path,
        sparse_output,
        split="train",
        seed=7,
        anchors_per_trajectory=1,
        context_regime="short_robustness",
        sparse_regime="sparse_1",
    )
    sparse_row = read_sample_manifest(sparse_output)[0]
    assert 3 <= sparse_row["context_count_k"] <= 9
    assert sparse_row["context_observed_mask"][-1] is True
    assert sparse_row["context_observed_count"] <= sparse_row["context_count_k"]

    sample_causal_manifest(
        snapshot_path,
        full_output,
        split="train",
        seed=7,
        anchors_per_trajectory=1,
        full_remaining_lifecycle=True,
    )
    full_row = read_sample_manifest(full_output)[0]
    assert full_row["sample_kind"] == "full_lifecycle_eval"
    assert full_row["target_query_policy"] == "all_observed_future"
    assert full_row["future_query_count_q"] == 40 - full_row["anchor_measurement_index"]

