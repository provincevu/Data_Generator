from __future__ import annotations

import json

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from data_generator.features.xjtu import (
    FEATURE_DIMENSION,
    FEATURE_SCHEMA_VERSION,
    run_xjtu_features,
)
from data_generator.ingestion.xjtu import OBSERVATION_SCHEMA


def test_xjtu_features_are_fixed_dimensional_and_train_scaled(tmp_path):
    observations = tmp_path / "xjtu_observations.parquet"
    output = tmp_path / "features"
    rows = []
    for measurement_index in (1, 2, 3):
        channels = (("horizontal", 0.0), ("vertical", np.pi / 4))
        if measurement_index == 3:
            channels = (("horizontal", 0.0),)
        for channel_id, phase in channels:
            signal = np.sin(2 * np.pi * np.arange(32) / 8 + phase).astype(np.float32)
            rows.append({
                "dataset_name": "XJTU-SY", "experiment_id": "condition_1", "bearing_id": "Bearing1_1",
                "measurement_index": measurement_index, "elapsed_time_sec": float((measurement_index - 1) * 60),
                "rotational_speed_rpm": 2100.0, "radial_load_kn": 12.0, "channel_id": channel_id,
                "channel_direction": channel_id, "sampling_rate_hz": 25600.0, "signal_length": 32,
                "vibration_signal": signal.tolist(),
            })
    pq.write_table(pa.Table.from_pylist(rows, schema=OBSERVATION_SCHEMA), observations)

    report = run_xjtu_features(observations, output)
    assert report["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    assert report["summary"]["feature_dimension"] == FEATURE_DIMENSION == 30
    assert report["summary"]["snapshot_feature_rows"] == 3
    assert report["summary"]["split_snapshot_rows"]["train"] == 3

    table = pq.read_table(output / "xjtu_snapshot_features.parquet").to_pylist()
    assert all(len(row["feature_vector"]) == 30 for row in table)
    assert all(np.isfinite(row["feature_vector"]).all() for row in table)
    assert table[-1]["vertical_present"] is False
    assert not any(table[-1]["feature_valid_mask"][15:])

    scaler = json.loads((output / "xjtu_feature_scaler.json").read_text(encoding="utf-8"))
    validation = json.loads((output / "xjtu_feature_validation.json").read_text(encoding="utf-8"))
    assert scaler["fit_split"] == "train"
    assert validation["summary"]["normalized_nonfinite_total"] == 0
