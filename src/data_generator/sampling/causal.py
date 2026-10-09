"""Causal sampling of XJTU-SY snapshot trajectories.

The sampler creates index-only sample manifests. Feature vectors stay in the
canonical snapshot table and are joined later when a model batch is built.
"""

from __future__ import annotations

import hashlib
import itertools
import math
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

from ..features.xjtu import FEATURE_DIMENSION, FEATURE_SCHEMA_VERSION
from .manifest import MANIFEST_SCHEMA_VERSION, SPARSE_RETENTION, write_sample_manifest

MAX_LOOKBACK_SEC = 1_800.0
MAX_CONTEXT_RECORDS = 20
MIN_MAIN_CONTEXT_RECORDS = 10
MAX_FUTURE_QUERIES = 8


def _stable_seed(*parts: object) -> int:
    """Return a stable non-negative seed independent of Python hash randomization."""
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little") & ((1 << 63) - 1)


def _sample_id(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def _as_snapshot_rows(snapshot_path: str | Path, split: str) -> list[dict[str, Any]]:
    table = pq.read_table(snapshot_path)
    required = {
        "dataset_name", "experiment_id", "bearing_id", "measurement_index",
        "elapsed_time_sec", "split", "feature_schema_version", "feature_dimension",
        "feature_vector", "horizontal_present", "vertical_present",
    }
    missing = sorted(required.difference(table.column_names))
    if missing:
        raise ValueError(f"snapshot table is missing required columns: {', '.join(missing)}")

    rows: list[dict[str, Any]] = []
    for row in table.to_pylist():
        if row["split"] != split:
            continue
        if row["feature_schema_version"] != FEATURE_SCHEMA_VERSION:
            raise ValueError("snapshot feature schema does not match the sampler contract")
        if int(row["feature_dimension"]) != FEATURE_DIMENSION:
            raise ValueError("snapshot feature dimension does not match the sampler contract")
        vector = row["feature_vector"]
        if vector is None or len(vector) != FEATURE_DIMENSION or not np.isfinite(vector).all():
            raise ValueError("snapshot feature vectors must have fixed finite dimension")
        if not bool(row["horizontal_present"]) and not bool(row["vertical_present"]):
            continue
        measurement_index = int(row["measurement_index"])
        elapsed_time = float(row["elapsed_time_sec"])
        if measurement_index < 1 or not math.isfinite(elapsed_time):
            raise ValueError("snapshot chronology fields must be valid")
        rows.append({
            "dataset_name": str(row["dataset_name"]),
            "experiment_id": str(row["experiment_id"]),
            "bearing_id": str(row["bearing_id"]),
            "measurement_index": measurement_index,
            "elapsed_time_sec": elapsed_time,
        })
    return rows


def _trajectory_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["dataset_name"], row["experiment_id"], row["bearing_id"]


def _ordered_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: (row["elapsed_time_sec"], row["measurement_index"]))
    if any(
        previous["measurement_index"] >= current["measurement_index"]
        or previous["elapsed_time_sec"] >= current["elapsed_time_sec"]
        for previous, current in itertools.pairwise(ordered)
    ):
        raise ValueError("a trajectory must have strictly increasing source chronology")
    return ordered


def _eligible_anchors(
    rows: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]]:
    eligible = []
    for position, anchor in enumerate(rows):
        lookback_start = anchor["elapsed_time_sec"] - MAX_LOOKBACK_SEC
        pool = [
            row for row in rows[: position + 1]
            if lookback_start <= row["elapsed_time_sec"] <= anchor["elapsed_time_sec"]
        ][-MAX_CONTEXT_RECORDS:]
        future = [row for row in rows[position + 1:] if row["elapsed_time_sec"] > anchor["elapsed_time_sec"]]
        if len(pool) >= MIN_MAIN_CONTEXT_RECORDS and future:
            eligible.append((anchor, pool, future))
    return eligible


def _choose_anchors(
    eligible: list[tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]],
    count: int | None,
    rng: np.random.Generator,
) -> list[tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]]:
    if count is None:
        return eligible
    if count < 1:
        raise ValueError("anchors_per_trajectory must be positive or None")
    if count >= len(eligible):
        return eligible
    positions = sorted(int(position) for position in rng.choice(len(eligible), size=count, replace=False))
    return [eligible[position] for position in positions]


def _choose_context(
    pool: list[dict[str, Any]],
    context_regime: str,
    rng: np.random.Generator,
) -> tuple[list[dict[str, Any]], int]:
    if context_regime == "main":
        lower = MIN_MAIN_CONTEXT_RECORDS
        upper = min(MAX_CONTEXT_RECORDS, len(pool))
    elif context_regime == "short_robustness":
        lower = 3
        upper = min(9, len(pool))
    else:
        raise ValueError(f"unsupported context_regime: {context_regime}")
    k = int(rng.integers(lower, upper + 1))
    anchor = pool[-1]
    predecessor = pool[-2]
    candidates = pool[:-2]
    chosen_positions = rng.choice(len(candidates), size=k - 2, replace=False)
    chosen = [candidates[int(position)] for position in chosen_positions]
    selected = sorted([*chosen, predecessor, anchor], key=lambda row: row["measurement_index"])
    return selected, k


def _choose_future(
    future: list[dict[str, Any]],
    full_remaining_lifecycle: bool,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    if full_remaining_lifecycle:
        return future
    upper = min(MAX_FUTURE_QUERIES, len(future))
    query_count = int(rng.integers(1, upper + 1))
    positions = rng.choice(len(future), size=query_count, replace=False)
    return sorted((future[int(position)] for position in positions), key=lambda row: row["measurement_index"])


def _make_record(
    *,
    anchor: dict[str, Any],
    context: list[dict[str, Any]],
    future: list[dict[str, Any]],
    split: str,
    sample_kind: str,
    context_regime: str,
    sparse_regime: str,
    sampling_seed: int,
    epoch: int | None,
    full_remaining_lifecycle: bool,
) -> dict[str, Any]:
    retention_probability = SPARSE_RETENTION[sparse_regime]
    mask = [True] * len(context)
    if sparse_regime != "dense":
        rng = np.random.default_rng(sampling_seed)
        mask = [bool(rng.random() < retention_probability) for _ in context]
        mask[-1] = True
    anchor_elapsed = anchor["elapsed_time_sec"]
    key = _trajectory_key(anchor)
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "sample_id": _sample_id(
            *key, anchor["measurement_index"], sampling_seed, epoch,
            context_regime, sparse_regime, full_remaining_lifecycle,
        ),
        "dataset_name": key[0],
        "experiment_id": key[1],
        "bearing_id": key[2],
        "split": split,
        "sample_kind": sample_kind,
        "context_regime": context_regime,
        "sparse_regime": sparse_regime,
        "sparse_retention_probability": retention_probability,
        "sampling_seed": sampling_seed,
        "epoch": epoch,
        "anchor_measurement_index": anchor["measurement_index"],
        "anchor_elapsed_time_sec": anchor_elapsed,
        "context_measurement_indices": [row["measurement_index"] for row in context],
        "context_relative_time_sec": [row["elapsed_time_sec"] - anchor_elapsed for row in context],
        "context_observed_mask": mask,
        "context_count_k": len(context),
        "context_observed_count": sum(mask),
        "future_query_measurement_indices": [row["measurement_index"] for row in future],
        "future_relative_time_sec": [row["elapsed_time_sec"] - anchor_elapsed for row in future],
        "future_query_count_q": len(future),
        "full_remaining_lifecycle": full_remaining_lifecycle,
        "target_query_policy": "all_observed_future" if full_remaining_lifecycle else "random_observed_future",
    }


def sample_causal_manifest(
    snapshot_path: str | Path,
    output_path: str | Path,
    *,
    split: str,
    seed: int,
    anchors_per_trajectory: int | None,
    context_regime: str = "main",
    sparse_regime: str = "dense",
    epoch: int | None = None,
    full_remaining_lifecycle: bool = False,
) -> dict[str, Any]:
    """Sample causal examples and write an index-only manifest."""
    if split not in {"train", "validation", "test"}:
        raise ValueError("split must be train, validation, or test")
    if not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if sparse_regime not in SPARSE_RETENTION:
        raise ValueError(f"unsupported sparse_regime: {sparse_regime}")
    if anchors_per_trajectory is not None and anchors_per_trajectory < 1:
        raise ValueError("anchors_per_trajectory must be positive or None")

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in _as_snapshot_rows(snapshot_path, split):
        grouped[_trajectory_key(row)].append(row)

    records: list[dict[str, Any]] = []
    trajectory_count = 0
    eligible_anchor_count = 0
    selected_anchor_count = 0
    for key in sorted(grouped):
        trajectory_count += 1
        rows = _ordered_rows(grouped[key])
        eligible = _eligible_anchors(rows)
        eligible_anchor_count += len(eligible)
        trajectory_seed = _stable_seed(seed, epoch if epoch is not None else -1, *key)
        selected = _choose_anchors(eligible, anchors_per_trajectory, np.random.default_rng(trajectory_seed))
        selected_anchor_count += len(selected)
        for anchor, pool, future_pool in selected:
            sample_seed = _stable_seed(
                trajectory_seed, anchor["measurement_index"], context_regime,
                sparse_regime, full_remaining_lifecycle,
            )
            rng = np.random.default_rng(sample_seed)
            context, _ = _choose_context(pool, context_regime, rng)
            future = _choose_future(future_pool, full_remaining_lifecycle, rng)
            kind = "full_lifecycle_eval" if full_remaining_lifecycle else {
                "train": "train_dynamic", "validation": "validation_fixed", "test": "test_fixed",
            }[split]
            records.append(_make_record(
                anchor=anchor,
                context=context,
                future=future,
                split=split,
                sample_kind=kind,
                context_regime=context_regime,
                sparse_regime=sparse_regime,
                sampling_seed=sample_seed,
                epoch=epoch,
                full_remaining_lifecycle=full_remaining_lifecycle,
            ))

    if not records:
        raise ValueError("no eligible causal anchors were found for the requested split")
    write_sample_manifest(output_path, records)
    context_counts = [record["context_count_k"] for record in records]
    future_counts = [record["future_query_count_q"] for record in records]
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "snapshot_path": str(snapshot_path),
        "output_path": str(output_path),
        "summary": {
            "split": split,
            "trajectory_count": trajectory_count,
            "eligible_anchor_count": eligible_anchor_count,
            "sample_count": selected_anchor_count,
            "context_regime": context_regime,
            "sparse_regime": sparse_regime,
            "full_remaining_lifecycle": full_remaining_lifecycle,
            "context_count_min": min(context_counts),
            "context_count_max": max(context_counts),
            "future_query_count_min": min(future_counts),
            "future_query_count_max": max(future_counts),
        },
    }


__all__ = ["sample_causal_manifest"]





