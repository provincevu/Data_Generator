import csv
from pathlib import Path

import pyarrow.parquet as pq

from data_generator.ingestion.metadata import build_xjtu_metadata
from data_generator.ingestion.xjtu import parse_xjtu

HEADERS = ["Horizontal_vibration_signals", "Vertical_vibration_signals"]


def write_csv(path: Path, rows: list[tuple[float, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)
        writer.writerows(rows)


def write_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "dataset_name",
        "experiment_id",
        "bearing_id",
        "source_csv_count",
        "reported_lifetime_raw",
        "reported_lifetime_min",
        "fault_element_raw",
        "fault_elements",
        "failure_observed",
        "metadata_source",
        "metadata_source_locator",
        "metadata_confidence",
        "notes",
    ]
    row = {
        "dataset_name": "XJTU-SY",
        "experiment_id": "condition_1",
        "bearing_id": "Bearing1_1",
        "source_csv_count": "1",
        "reported_lifetime_raw": "2 h 3 min",
        "reported_lifetime_min": "123",
        "fault_element_raw": "Inner race and outer race",
        "fault_elements": "inner_race;outer_race",
        "failure_observed": "true",
        "metadata_source": "source.pdf",
        "metadata_source_locator": "Table 2 page 3",
        "metadata_confidence": "high",
        "notes": "",
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)


def test_metadata_preserves_raw_labels_and_derives_counts(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    write_csv(raw / "35Hz12kN" / "Bearing1_1" / "1.csv", [(1.0, 2.0)])
    parse_output = tmp_path / "parsed"
    parse_xjtu(raw, parse_output, expected_signal_length=1)

    config = tmp_path / "config.csv"
    write_config(config)
    output = tmp_path / "metadata"
    report = build_xjtu_metadata(
        config, parse_output / "xjtu_source_manifest.parquet", output
    )

    assert report["summary"]["trajectory_metadata_rows"] == 1
    row = pq.read_table(output / "xjtu_trajectory_metadata.parquet").to_pylist()[0]
    assert row["fault_element_raw"] == "Inner race and outer race"
    assert row["fault_elements"] == ["inner_race", "outer_race"]
    assert row["reported_lifetime_min"] == 123.0
    assert row["parsed_measurement_count"] == 1
    assert row["first_measurement_index"] == 1
    assert row["last_measurement_index"] == 1

    dataset = pq.read_table(output / "xjtu_dataset_metadata.parquet").to_pylist()[0]
    assert dataset["bearing_model"] == "LDK UER204"
    condition = pq.read_table(output / "xjtu_condition_metadata.parquet").to_pylist()[0]
    assert condition["rotational_speed_rpm"] == 2100.0