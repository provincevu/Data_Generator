from __future__ import annotations

import json

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from data_generator.eda.xjtu import run_xjtu_eda
from data_generator.ingestion.xjtu import MANIFEST_SCHEMA, OBSERVATION_SCHEMA


def test_xjtu_eda_writes_time_summary_and_eleven_fft_anchors(tmp_path):
    interim = tmp_path / "interim"
    interim.mkdir()
    observations = interim / "xjtu_observations.parquet"
    manifest = interim / "xjtu_source_manifest.parquet"
    trajectory = interim / "xjtu_trajectory_metadata.parquet"
    rows = []
    manifest_rows = []
    for measurement_index in (1, 2, 3):
        for channel_id, phase in (("horizontal", 0.0), ("vertical", np.pi / 4)):
            signal = np.sin(2 * np.pi * np.arange(32) / 8 + phase).astype(np.float32)
            rows.append({
                "dataset_name": "XJTU-SY", "experiment_id": "condition_1", "bearing_id": "Bearing1_1",
                "measurement_index": measurement_index, "elapsed_time_sec": float((measurement_index - 1) * 60),
                "rotational_speed_rpm": 2100.0, "radial_load_kn": 12.0, "channel_id": channel_id,
                "channel_direction": channel_id, "sampling_rate_hz": 25600.0, "signal_length": 32,
                "vibration_signal": signal.tolist(),
            })
        manifest_rows.append({
            "source_relative_path": f"35Hz12kN/Bearing1_1/{measurement_index}.csv", "file_sha256": "x",
            "file_size_bytes": 1, "condition_source_name": "35Hz12kN", "experiment_id": "condition_1",
            "bearing_id": "Bearing1_1", "measurement_index": measurement_index,
            "source_columns": ["Horizontal_vibration_signals", "Vertical_vibration_signals"],
            "source_row_count": 32, "horizontal_signal_length": 32, "vertical_signal_length": 32,
            "parse_status": "ok", "error": None, "warnings": [],
        })
    pq.write_table(pa.Table.from_pylist(rows, schema=OBSERVATION_SCHEMA), observations)
    pq.write_table(pa.Table.from_pylist(manifest_rows, schema=MANIFEST_SCHEMA), manifest)
    pq.write_table(pa.Table.from_pylist([{
        "dataset_name": "XJTU-SY", "experiment_id": "condition_1", "bearing_id": "Bearing1_1",
        "source_csv_count": 3, "reported_lifetime_raw": "3 min", "reported_lifetime_min": 3.0,
        "parsed_measurement_count": 3, "first_measurement_index": 1, "last_measurement_index": 3,
        "fault_element_raw": "inner race", "fault_elements": ["inner_race"], "failure_observed": True,
        "metadata_source": "test", "metadata_source_locator": "test", "metadata_confidence": "high", "notes": "",
    }]), trajectory)

    report = run_xjtu_eda(observations, manifest, trajectory, interim, make_plots=False)
    assert report["summary"]["observation_summary_rows"] == 6
    assert report["summary"]["fft_summary_rows"] == 22
    fft_rows = pq.read_table(interim / "xjtu_fft_summary.parquet").to_pylist()
    assert {row["anchor_percent"] for row in fft_rows} == set(range(0, 101, 10))
    assert {row["selected_measurement_index"] for row in fft_rows} == {1, 2, 3}
    assert all(len(row["frequencies_hz"]) == 17 for row in fft_rows)
    saved_report = json.loads((interim / "xjtu_eda_report.json").read_text(encoding="utf-8"))
    assert saved_report["configuration"]["fft_window"] == "Hann"

def test_signal_metric_definitions_match_project_contract():
    from data_generator.eda.xjtu import _signal_metrics

    metrics = _signal_metrics(np.array([-1.0, 0.0, 1.0, 0.0]))
    assert np.isclose(metrics["std"], np.sqrt(0.5))
    assert np.isclose(metrics["kurtosis"], 2.0)
    assert np.isclose(metrics["crest_factor"], np.sqrt(2.0))
