import csv
import json
from pathlib import Path

import pyarrow.parquet as pq

from data_generator.ingestion.xjtu import parse_xjtu

HEADERS = ["Horizontal_vibration_signals", "Vertical_vibration_signals"]


def write_csv(path: Path, rows: list[tuple[float, float]], *, headers=HEADERS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def test_parse_writes_two_observations_per_csv(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    write_csv(raw / "35Hz12kN" / "Bearing1_1" / "1.csv", [(1.0, 2.0), (3.0, 4.0)])
    output = tmp_path / "output"

    report = parse_xjtu(raw, output, expected_signal_length=2)

    assert report["summary"] == {
        "files_discovered": 1,
        "files_parsed": 1,
        "files_with_errors": 0,
        "observations_written": 2,
        "warning_count": 0,
        "trajectory_gap_count": 0,
    }
    observations = pq.read_table(output / "xjtu_observations.parquet")
    assert observations.num_rows == 2
    assert observations.column_names == [
        "dataset_name",
        "experiment_id",
        "bearing_id",
        "measurement_index",
        "elapsed_time_sec",
        "rotational_speed_rpm",
        "radial_load_kn",
        "channel_id",
        "channel_direction",
        "sampling_rate_hz",
        "signal_length",
        "vibration_signal",
    ]
    rows = observations.to_pylist()
    assert {row["channel_id"] for row in rows} == {"horizontal", "vertical"}
    assert all(row["measurement_index"] == 1 for row in rows)
    assert all(row["elapsed_time_sec"] == 0 for row in rows)
    assert rows[0]["vibration_signal"] in ([1.0, 3.0], [2.0, 4.0])


def test_measurement_number_preserves_time_gaps(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    bearing = raw / "35Hz12kN" / "Bearing1_1"
    write_csv(bearing / "1.csv", [(1.0, 2.0)])
    write_csv(bearing / "3.csv", [(3.0, 4.0)])

    report = parse_xjtu(raw, tmp_path / "output", expected_signal_length=1)

    assert report["summary"]["trajectory_gap_count"] == 1
    assert report["trajectory_gaps"][0]["missing_measurement_indices"] == [2]
    rows = pq.read_table(tmp_path / "output" / "xjtu_observations.parquet").to_pylist()
    assert sorted(row["elapsed_time_sec"] for row in rows) == [0.0, 0.0, 120.0, 120.0]


def test_invalid_file_is_reported_and_valid_file_is_kept(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    bearing = raw / "35Hz12kN" / "Bearing1_1"
    write_csv(bearing / "1.csv", [(1.0, 2.0)])
    (bearing / "2.csv").parent.mkdir(parents=True, exist_ok=True)
    (bearing / "2.csv").write_text("wrong,header\n1,2\n", encoding="utf-8")

    report = parse_xjtu(raw, tmp_path / "output", expected_signal_length=1)

    assert report["summary"]["files_parsed"] == 1
    assert report["summary"]["files_with_errors"] == 1
    manifest = pq.read_table(tmp_path / "output" / "xjtu_source_manifest.parquet").to_pylist()
    assert {row["parse_status"] for row in manifest} == {"ok", "error"}
    assert pq.read_table(tmp_path / "output" / "xjtu_observations.parquet").num_rows == 2


def test_short_waveform_is_preserved_with_warning(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    write_csv(raw / "35Hz12kN" / "Bearing1_1" / "1.csv", [(1.0, 2.0)])

    report = parse_xjtu(raw, tmp_path / "output")

    assert report["summary"]["warning_count"] == 1
    rows = pq.read_table(tmp_path / "output" / "xjtu_observations.parquet").to_pylist()
    assert {row["signal_length"] for row in rows} == {1}


def test_report_is_valid_json(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    write_csv(raw / "35Hz12kN" / "Bearing1_1" / "1.csv", [(1.0, 2.0)])
    output = tmp_path / "output"
    parse_xjtu(raw, output, expected_signal_length=1)

    report = json.loads((output / "xjtu_parse_report.json").read_text(encoding="utf-8"))
    assert report["dataset_name"] == "XJTU-SY"

def test_files_are_processed_in_numeric_measurement_order(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    bearing = raw / "35Hz12kN" / "Bearing1_1"
    for index in (1, 10, 2):
        write_csv(bearing / f"{index}.csv", [(float(index), float(index))])

    parse_xjtu(raw, tmp_path / "output", expected_signal_length=1)

    rows = pq.read_table(tmp_path / "output" / "xjtu_observations.parquet").to_pylist()
    assert [row["measurement_index"] for row in rows] == [1, 1, 2, 2, 10, 10]