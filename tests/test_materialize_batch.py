from __future__ import annotations

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from data_generator.batching.materialize import (
    SnapshotFeatureStore,
    collate_examples,
    materialize_example,
)
from data_generator.features.xjtu import (
    FEATURE_DIMENSION,
    FEATURE_SCHEMA_VERSION,
    SNAPSHOT_FEATURE_SCHEMA,
)
from data_generator.sampling.manifest import (
    MANIFEST_SCHEMA_VERSION,
    SPARSE_RETENTION,
)


def _write_snapshot_table(path, count: int = 20) -> None:
    rows = []
    for measurement_index in range(1, count + 1):
        valid_mask = [True] * FEATURE_DIMENSION
        if measurement_index == 11:
            valid_mask[0] = False
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
            "feature_valid_mask": valid_mask,
        })
    pq.write_table(pa.Table.from_pylist(rows, schema=SNAPSHOT_FEATURE_SCHEMA), path)


def _record(
    *,
    sample_id: str,
    context_indices: list[int],
    future_indices: list[int],
    sparse_regime: str = "dense",
    observed_mask: list[bool] | None = None,
) -> dict:
    anchor = context_indices[-1]
    anchor_time = float((anchor - 1) * 60)
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "sample_id": sample_id,
        "dataset_name": "XJTU-SY",
        "experiment_id": "condition_1",
        "bearing_id": "Bearing1_1",
        "split": "train",
        "sample_kind": "train_dynamic",
        "context_regime": "main",
        "sparse_regime": sparse_regime,
        "sparse_retention_probability": SPARSE_RETENTION[sparse_regime],
        "sampling_seed": 17,
        "epoch": 0,
        "anchor_measurement_index": anchor,
        "anchor_elapsed_time_sec": anchor_time,
        "context_measurement_indices": context_indices,
        "context_relative_time_sec": [float((index - anchor) * 60) for index in context_indices],
        "context_observed_mask": observed_mask or [True] * len(context_indices),
        "context_count_k": len(context_indices),
        "context_observed_count": sum(observed_mask or [True] * len(context_indices)),
        "future_query_measurement_indices": future_indices,
        "future_relative_time_sec": [float((index - anchor) * 60) for index in future_indices],
        "future_query_count_q": len(future_indices),
        "full_remaining_lifecycle": False,
        "target_query_policy": "random_observed_future",
    }


def test_materialize_example_applies_feature_and_sparse_masks(tmp_path):
    snapshot_path = tmp_path / "snapshots.parquet"
    _write_snapshot_table(snapshot_path)
    store = SnapshotFeatureStore.from_parquet(snapshot_path)
    record = _record(
        sample_id="sample-1",
        context_indices=list(range(1, 11)),
        future_indices=[11, 12],
        sparse_regime="sparse_10",
        observed_mask=[True] * 8 + [False, True],
    )

    example = materialize_example(record, store)

    assert example["context_features"].shape == (10, FEATURE_DIMENSION)
    assert example["context_relative_time"].shape == (10,)
    assert example["context_mask"].shape == (10, FEATURE_DIMENSION)
    assert example["future_targets"].shape == (2, FEATURE_DIMENSION)
    assert example["future_target_mask"].shape == (2, FEATURE_DIMENSION)
    assert np.all(example["context_features"][8] == 0.0)
    assert not example["context_mask"][8].any()
    assert example["context_mask"][-1].all()
    assert example["future_targets"][0, 0] == 0.0
    assert not example["future_target_mask"][0, 0]
    assert example["future_target_mask"][0, 1:].all()


def test_collate_pads_variable_context_and_future_lengths(tmp_path):
    snapshot_path = tmp_path / "snapshots.parquet"
    _write_snapshot_table(snapshot_path)
    store = SnapshotFeatureStore.from_parquet(snapshot_path)
    first = materialize_example(_record(
        sample_id="sample-1",
        context_indices=list(range(1, 11)),
        future_indices=[11, 12],
    ), store)
    second = materialize_example(_record(
        sample_id="sample-2",
        context_indices=list(range(4, 16)),
        future_indices=[16, 17, 18],
    ), store)

    batch = collate_examples([first, second])

    assert batch["context_features"].shape == (2, 12, FEATURE_DIMENSION)
    assert batch["context_relative_time"].shape == (2, 12)
    assert batch["context_mask"].shape == (2, 12, FEATURE_DIMENSION)
    assert batch["future_query_time"].shape == (2, 3)
    assert batch["future_targets"].shape == (2, 3, FEATURE_DIMENSION)
    assert batch["future_target_mask"].shape == (2, 3, FEATURE_DIMENSION)
    assert batch["context_lengths"].tolist() == [10, 12]
    assert batch["future_lengths"].tolist() == [2, 3]
    assert not batch["context_mask"][0, 10].any()
    assert not batch["future_target_mask"][0, 2].any()
    assert batch["sample_ids"] == ["sample-1", "sample-2"]


def test_materializer_does_not_use_future_rows_as_context(tmp_path):
    snapshot_path = tmp_path / "snapshots.parquet"
    _write_snapshot_table(snapshot_path)
    store = SnapshotFeatureStore.from_parquet(snapshot_path)
    record = _record(
        sample_id="sample-1",
        context_indices=list(range(1, 11)),
        future_indices=[11, 12],
    )

    example = materialize_example(record, store)

    assert np.all(example["context_features"][:, 0] == np.arange(1, 11, dtype=np.float32))
    assert np.all(example["future_targets"][:, 0] == np.array([0.0, 12.0], dtype=np.float32))

