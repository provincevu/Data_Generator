"""Automated leakage and reproducibility checks for causal sample manifests.

This module only reads the snapshot table and manifest files, then writes a JSON
report. It never creates or modifies manifests.

Example:
    python -m data_generator.validation.causal \
        --snapshot-features data/interim/xjtu/xjtu_snapshot_features.parquet \
        --manifest data/interim/xjtu/xjtu_sample_manifest_validation.parquet \
        --report data/interim/xjtu/xjtu_causal_validation_report.json
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from ..features.xjtu import FEATURE_DIMENSION, FEATURE_SCHEMA_VERSION
from ..sampling.manifest import validate_sample_manifest_record

REPORT_SCHEMA_VERSION = "xjtu_causal_validation_v1"
LOOKBACK_SECONDS = 1_800.0
MAX_CONTEXT_RECORDS = 20
_ALLOWED_SPLITS = frozenset({"train", "validation", "test"})


def _new_report(snapshot_path: Path, manifest_paths: list[Path]) -> dict[str, Any]:
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "snapshot_path": str(snapshot_path),
        "manifest_paths": [str(path) for path in manifest_paths],
        "checks": {
            "snapshot_integrity": "not_run",
            "manifest_contract": "not_run",
            "causal_order": "not_run",
            "split_isolation": "not_run",
            "source_reference_integrity": "not_run",
            "reproducibility": "not_run",
            "model_input_metadata_audit": "not_assessable",
        },
        "summary": {"snapshot_rows": 0, "manifest_rows": 0, "errors": 0, "warnings": 0},
        "errors": [],
        "warnings": [],
    }


def _issue(
    report: dict[str, Any],
    message: str,
    *,
    code: str,
    manifest_path: Path | None = None,
    sample_id: str | None = None,
    warning: bool = False,
) -> None:
    item = {"code": code, "message": message}
    if manifest_path is not None:
        item["manifest_path"] = str(manifest_path)
    if sample_id is not None:
        item["sample_id"] = sample_id
    report["warnings" if warning else "errors"].append(item)


def _source_key(record: dict[str, Any], measurement_index: int) -> tuple[str, str, str, int]:
    return (
        str(record["dataset_name"]),
        str(record["experiment_id"]),
        str(record["bearing_id"]),
        int(measurement_index),
    )


def _load_snapshot_index(path: Path, report: dict[str, Any]) -> dict[tuple[str, str, str, int], dict[str, Any]]:
    required = {
        "dataset_name", "experiment_id", "bearing_id", "measurement_index",
        "elapsed_time_sec", "split", "feature_schema_version", "feature_dimension",
        "feature_vector", "horizontal_present", "vertical_present",
    }
    try:
        table = pq.read_table(path)
    except Exception as exc:
        _issue(report, f"cannot read snapshot table: {exc}", code="snapshot_read_error")
        report["checks"]["snapshot_integrity"] = "fail"
        return {}
    missing = sorted(required.difference(table.column_names))
    if missing:
        _issue(report, f"snapshot table is missing columns: {', '.join(missing)}", code="snapshot_missing_columns")
        report["checks"]["snapshot_integrity"] = "fail"
        return {}

    index: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    for row_number, row in enumerate(table.to_pylist()):
        key = (
            str(row["dataset_name"]),
            str(row["experiment_id"]),
            str(row["bearing_id"]),
            int(row["measurement_index"]),
        )
        if key in index:
            _issue(report, f"duplicate snapshot reference at row {row_number}: {key}", code="snapshot_duplicate")
            continue
        vector = row["feature_vector"]
        valid_vector = vector is not None and len(vector) == FEATURE_DIMENSION and all(
            math.isfinite(float(value)) for value in vector
        )
        if row["feature_schema_version"] != FEATURE_SCHEMA_VERSION:
            _issue(report, f"snapshot row has unsupported feature schema: {key}", code="snapshot_feature_schema")
        if int(row["feature_dimension"]) != FEATURE_DIMENSION or not valid_vector:
            _issue(report, f"snapshot row does not have finite dimension {FEATURE_DIMENSION}: {key}", code="snapshot_feature_vector")
        if str(row["split"]) not in _ALLOWED_SPLITS:
            _issue(report, f"snapshot row has invalid split: {key}", code="snapshot_split")
        index[key] = {
            "elapsed_time_sec": float(row["elapsed_time_sec"]),
            "split": str(row["split"]),
        }
    report["summary"]["snapshot_rows"] = len(index)
    report["checks"]["snapshot_integrity"] = "fail" if report["errors"] else "pass"
    return index


def _read_manifest(path: Path, report: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        rows = pq.read_table(path).to_pylist()
    except Exception as exc:
        _issue(report, f"cannot read manifest: {exc}", code="manifest_read_error", manifest_path=path)
        return []
    valid_rows: list[dict[str, Any]] = []
    for row in rows:
        try:
            validate_sample_manifest_record(row)
        except (TypeError, ValueError, KeyError, IndexError) as exc:
            _issue(
                report,
                f"manifest contract violation: {exc}",
                code="manifest_contract",
                manifest_path=path,
                sample_id=str(row.get("sample_id", "<unknown>")),
            )
            continue
        valid_rows.append(row)
    return valid_rows


def _check_sample(
    record: dict[str, Any],
    manifest_path: Path,
    snapshot_index: dict[tuple[str, str, str, int], dict[str, Any]],
    report: dict[str, Any],
) -> None:
    sample_id = str(record["sample_id"])
    anchor_index = int(record["anchor_measurement_index"])
    anchor_key = _source_key(record, anchor_index)
    anchor = snapshot_index.get(anchor_key)
    if anchor is None:
        _issue(report, f"anchor does not reference an existing snapshot: {anchor_key}", code="missing_anchor", manifest_path=manifest_path, sample_id=sample_id)
        return

    anchor_elapsed = anchor["elapsed_time_sec"]
    if not math.isclose(float(record["anchor_elapsed_time_sec"]), anchor_elapsed, abs_tol=1e-9):
        _issue(report, "manifest anchor elapsed time disagrees with snapshot table", code="anchor_time_mismatch", manifest_path=manifest_path, sample_id=sample_id)
    if anchor["split"] != record["split"]:
        _issue(report, "manifest split disagrees with source snapshot split", code="anchor_split_mismatch", manifest_path=manifest_path, sample_id=sample_id)

    context_indices = [int(value) for value in record["context_measurement_indices"]]
    context_times = [float(value) for value in record["context_relative_time_sec"]]
    context_mask = [bool(value) for value in record["context_observed_mask"]]
    if len(context_indices) > MAX_CONTEXT_RECORDS:
        _issue(report, "context contains more than 20 records", code="context_cap", manifest_path=manifest_path, sample_id=sample_id)
    if anchor_index not in context_indices or not context_mask[context_indices.index(anchor_index)]:
        _issue(report, "anchor is absent or masked in context", code="anchor_context_mask", manifest_path=manifest_path, sample_id=sample_id)

    for position, measurement_index in enumerate(context_indices):
        snapshot = snapshot_index.get(_source_key(record, measurement_index))
        if snapshot is None:
            _issue(report, f"context references missing snapshot {measurement_index}", code="missing_context_snapshot", manifest_path=manifest_path, sample_id=sample_id)
            continue
        actual_relative = snapshot["elapsed_time_sec"] - anchor_elapsed
        if not math.isclose(context_times[position], actual_relative, abs_tol=1e-9):
            _issue(report, f"context relative time mismatch at measurement {measurement_index}", code="context_time_mismatch", manifest_path=manifest_path, sample_id=sample_id)
        if actual_relative > 1e-9 or actual_relative < -LOOKBACK_SECONDS - 1e-9:
            _issue(report, f"context measurement {measurement_index} is outside the causal lookback window", code="context_lookback", manifest_path=manifest_path, sample_id=sample_id)
        if snapshot["split"] != record["split"]:
            _issue(report, f"context measurement {measurement_index} crosses split boundary", code="context_split_leakage", manifest_path=manifest_path, sample_id=sample_id)

    future_indices = [int(value) for value in record["future_query_measurement_indices"]]
    future_times = [float(value) for value in record["future_relative_time_sec"]]
    if set(context_indices).intersection(future_indices):
        _issue(report, "future queries overlap context measurements", code="context_future_overlap", manifest_path=manifest_path, sample_id=sample_id)
    for position, measurement_index in enumerate(future_indices):
        snapshot = snapshot_index.get(_source_key(record, measurement_index))
        if snapshot is None:
            _issue(report, f"future references missing snapshot {measurement_index}", code="missing_future_snapshot", manifest_path=manifest_path, sample_id=sample_id)
            continue
        actual_relative = snapshot["elapsed_time_sec"] - anchor_elapsed
        if actual_relative <= 0.0:
            _issue(report, f"future measurement {measurement_index} is not after the anchor", code="future_before_anchor", manifest_path=manifest_path, sample_id=sample_id)
        if not math.isclose(future_times[position], actual_relative, abs_tol=1e-9):
            _issue(report, f"future relative time mismatch at measurement {measurement_index}", code="future_time_mismatch", manifest_path=manifest_path, sample_id=sample_id)
        if snapshot["split"] != record["split"]:
            _issue(report, f"future measurement {measurement_index} crosses split boundary", code="future_split_leakage", manifest_path=manifest_path, sample_id=sample_id)


def _canonical_row(row: dict[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _compare_manifests(
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    left_path: Path,
    right_path: Path,
    report: dict[str, Any],
) -> None:
    left = {str(row["sample_id"]): _canonical_row(row) for row in left_rows}
    right = {str(row["sample_id"]): _canonical_row(row) for row in right_rows}
    if left == right:
        report["checks"]["reproducibility"] = "pass"
        return
    report["checks"]["reproducibility"] = "fail"
    missing = sorted(set(left).difference(right))
    extra = sorted(set(right).difference(left))
    changed = sorted(sample_id for sample_id in set(left).intersection(right) if left[sample_id] != right[sample_id])
    if missing:
        _issue(report, f"reproducibility comparison missing sample IDs: {missing[:10]}", code="repro_missing_samples", manifest_path=right_path)
    if extra:
        _issue(report, f"reproducibility comparison has extra sample IDs: {extra[:10]}", code="repro_extra_samples", manifest_path=right_path)
    if changed:
        _issue(report, f"reproducibility comparison changed sample IDs: {changed[:10]}", code="repro_changed_samples", manifest_path=right_path)
    _issue(report, f"manifests are not identical: {left_path} vs {right_path}", code="reproducibility_mismatch", manifest_path=right_path)


def run_causal_validation(
    snapshot_path: str | Path,
    manifest_paths: list[str | Path],
    report_path: str | Path,
    *,
    compare_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate causal manifests and write a JSON report without changing inputs."""
    snapshot = Path(snapshot_path)
    manifests = [Path(path) for path in manifest_paths]
    report = _new_report(snapshot, manifests)
    snapshot_index = _load_snapshot_index(snapshot, report)

    all_rows: list[tuple[Path, dict[str, Any]]] = []
    for path in manifests:
        rows = _read_manifest(path, report)
        all_rows.extend((path, row) for row in rows)
    report["summary"]["manifest_rows"] = len(all_rows)
    report["checks"]["manifest_contract"] = "fail" if report["errors"] else "pass"

    sample_ids: dict[str, Path] = {}
    trajectory_splits: dict[tuple[str, str, str], str] = {}
    for path, row in all_rows:
        sample_id = str(row["sample_id"])
        if sample_id in sample_ids:
            _issue(report, f"duplicate sample_id also appears in {sample_ids[sample_id]}", code="duplicate_sample_id", manifest_path=path, sample_id=sample_id)
        sample_ids[sample_id] = path
        trajectory = (str(row["dataset_name"]), str(row["experiment_id"]), str(row["bearing_id"]))
        previous_split = trajectory_splits.setdefault(trajectory, str(row["split"]))
        if previous_split != row["split"]:
            _issue(report, f"trajectory appears in multiple splits: {trajectory}", code="trajectory_split_leakage", manifest_path=path, sample_id=sample_id)
        _check_sample(row, path, snapshot_index, report)

    report["checks"]["causal_order"] = "fail" if any(item["code"] in {
        "context_future_overlap", "context_lookback", "future_before_anchor",
        "context_time_mismatch", "future_time_mismatch", "anchor_context_mask",
    } for item in report["errors"]) else "pass"
    report["checks"]["source_reference_integrity"] = "fail" if any(item["code"].startswith(("missing_", "anchor_", "context_split_", "future_split_")) for item in report["errors"]) else "pass"
    report["checks"]["split_isolation"] = "fail" if any(item["code"] == "trajectory_split_leakage" for item in report["errors"]) else "pass"

    if compare_manifest_path is not None and manifests:
        comparison_path = Path(compare_manifest_path)
        comparison_rows = _read_manifest(comparison_path, report)
        _compare_manifests(
            [row for path, row in all_rows if path == manifests[0]],
            comparison_rows,
            manifests[0],
            comparison_path,
            report,
        )
    else:
        report["warnings"].append({
            "code": "reproducibility_comparison_not_requested",
            "message": "Pass --compare-manifest after running the sampler twice to check byte-independent semantic reproducibility.",
        })
    report["warnings"].append({
        "code": "model_input_metadata_audit_not_assessable",
        "message": "Manifest-only validation cannot prove that forbidden metadata are absent from the model tensor; audit the tensor materializer separately.",
    })
    report["summary"]["errors"] = len(report["errors"])
    report["summary"]["warnings"] = len(report["warnings"])
    report["status"] = "fail" if report["errors"] else "pass"
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate causal XJTU-SY manifests for leakage and reproducibility.")
    parser.add_argument("--snapshot-features", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, nargs="+", required=True)
    parser.add_argument("--compare-manifest", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_causal_validation(
        args.snapshot_features,
        args.manifest,
        args.report,
        compare_manifest_path=args.compare_manifest,
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

