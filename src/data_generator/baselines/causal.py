"""Baseline models and masked evaluation for causal XJTU-SY forecasting."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.neural_network import MLPRegressor

from ..batching.materialize import SnapshotFeatureStore, materialize_example
from ..features.xjtu import FEATURE_DIMENSION
from ..sampling.manifest import read_sample_manifest

HORIZON_BINS_SEC = (0.0, 300.0, 600.0, 1_200.0, 1_800.0, 3_600.0, float("inf"))
HORIZON_LABELS = ("0-5m", "5-10m", "10-20m", "20-30m", "30-60m", "60m+")


def horizon_label(seconds: float) -> str:
    for lower, upper, label in zip(HORIZON_BINS_SEC, HORIZON_BINS_SEC[1:], HORIZON_LABELS):
        if lower <= seconds < upper:
            return label
    return HORIZON_LABELS[-1]


class PersistenceBaseline:
    """Repeat the latest observed value independently for every feature."""

    name = "persistence"

    def fit(self, examples: Iterable[dict[str, Any]]) -> PersistenceBaseline:
        return self

    def predict(self, example: dict[str, Any]) -> np.ndarray:
        features = np.asarray(example["context_features"], dtype=np.float32)
        mask = np.asarray(example["context_mask"], dtype=bool)
        last = np.zeros(FEATURE_DIMENSION, dtype=np.float32)
        for feature_index in range(FEATURE_DIMENSION):
            valid_positions = np.flatnonzero(mask[:, feature_index])
            if valid_positions.size:
                last[feature_index] = features[valid_positions[-1], feature_index]
        query_count = int(example["future_query_time"].shape[0])
        return np.repeat(last[None, :], query_count, axis=0)


class LinearTrendBaseline:
    """Extrapolate one least-squares line per feature using observed context."""

    name = "linear_trend"

    def fit(self, examples: Iterable[dict[str, Any]]) -> LinearTrendBaseline:
        return self

    def predict(self, example: dict[str, Any]) -> np.ndarray:
        features = np.asarray(example["context_features"], dtype=np.float32)
        times = np.asarray(example["context_relative_time"], dtype=np.float64)
        mask = np.asarray(example["context_mask"], dtype=bool)
        query_times = np.asarray(example["future_query_time"], dtype=np.float64)
        predictions = np.zeros((query_times.size, FEATURE_DIMENSION), dtype=np.float32)
        persistence = PersistenceBaseline().predict(example)[0]
        for feature_index in range(FEATURE_DIMENSION):
            valid_positions = np.flatnonzero(mask[:, feature_index])
            if valid_positions.size < 2:
                predictions[:, feature_index] = persistence[feature_index]
                continue
            x = times[valid_positions]
            y = features[valid_positions, feature_index].astype(np.float64)
            if np.allclose(x, x[0]):
                predictions[:, feature_index] = persistence[feature_index]
                continue
            slope, intercept = np.polyfit(x, y, deg=1)
            predictions[:, feature_index] = (intercept + slope * query_times).astype(np.float32)
        return predictions


def _encode_context(example: dict[str, Any], max_context: int = 20) -> np.ndarray:
    features = np.asarray(example["context_features"], dtype=np.float32)
    times = np.asarray(example["context_relative_time"], dtype=np.float32)
    mask = np.asarray(example["context_mask"], dtype=np.float32)
    if features.shape[0] > max_context:
        raise ValueError(f"context length {features.shape[0]} exceeds max_context={max_context}")
    encoded = np.zeros(max_context * FEATURE_DIMENSION * 2 + max_context + 1, dtype=np.float32)
    feature_end = max_context * FEATURE_DIMENSION
    mask_end = feature_end * 2
    encoded[:features.shape[0] * FEATURE_DIMENSION] = features.ravel()
    encoded[feature_end:feature_end + features.shape[0] * FEATURE_DIMENSION] = mask.ravel()
    encoded[mask_end:mask_end + times.shape[0]] = times / 1_800.0
    return encoded


class SmallMLPBaseline:
    """Small per-feature MLP ensemble trained only on train examples."""

    name = "mlp_small"

    def __init__(
        self,
        *,
        random_state: int = 0,
        max_context: int = 20,
        hidden_layer_sizes: tuple[int, ...] = (32,),
        max_iter: int = 100,
    ) -> None:
        self.random_state = random_state
        self.max_context = max_context
        self.hidden_layer_sizes = hidden_layer_sizes
        self.max_iter = max_iter
        self._models: list[MLPRegressor | None] = [None] * FEATURE_DIMENSION
        self._constants = np.zeros(FEATURE_DIMENSION, dtype=np.float32)

    def fit(self, examples: Iterable[dict[str, Any]]) -> SmallMLPBaseline:
        materialized = list(examples)
        if not materialized:
            raise ValueError("cannot fit MLP without training examples")
        inputs: list[np.ndarray] = []
        targets: list[np.ndarray] = []
        masks: list[np.ndarray] = []
        for example in materialized:
            base = _encode_context(example, self.max_context)
            query_times = np.asarray(example["future_query_time"], dtype=np.float32)
            inputs.extend(np.concatenate([base[:-1], [time / 3_600.0]]) for time in query_times)
            targets.append(np.asarray(example["future_targets"], dtype=np.float32))
            masks.append(np.asarray(example["future_target_mask"], dtype=bool))
        x = np.asarray(inputs, dtype=np.float32)
        y = np.concatenate(targets, axis=0)
        valid = np.concatenate(masks, axis=0)
        if x.shape[0] != y.shape[0]:
            raise ValueError("training query and target counts do not match")

        for feature_index in range(FEATURE_DIMENSION):
            positions = valid[:, feature_index]
            if not positions.any():
                continue
            feature_y = y[positions, feature_index]
            self._constants[feature_index] = float(np.mean(feature_y))
            if feature_y.size < 3 or np.allclose(feature_y, feature_y[0]):
                continue
            model = MLPRegressor(
                hidden_layer_sizes=self.hidden_layer_sizes,
                max_iter=self.max_iter,
                random_state=self.random_state + feature_index,
                early_stopping=False,
            )
            model.fit(x[positions], feature_y)
            self._models[feature_index] = model
        return self

    def predict(self, example: dict[str, Any]) -> np.ndarray:
        base = _encode_context(example, self.max_context)
        query_times = np.asarray(example["future_query_time"], dtype=np.float32)
        x = np.asarray(
            [np.concatenate([base[:-1], [time / 3_600.0]]) for time in query_times],
            dtype=np.float32,
        )
        predictions = np.zeros((query_times.size, FEATURE_DIMENSION), dtype=np.float32)
        persistence = PersistenceBaseline().predict(example)
        for feature_index, model in enumerate(self._models):
            if model is None:
                predictions[:, feature_index] = (
                    persistence[:, feature_index]
                    if persistence.shape[0]
                    else self._constants[feature_index]
                )
            else:
                predictions[:, feature_index] = model.predict(x).astype(np.float32)
        return predictions


def _add_metrics(
    aggregates: dict[tuple[str, str, str, str], dict[str, float]],
    model_name: str,
    split: str,
    group_name: str,
    group_value: str,
    prediction: np.ndarray,
    target: np.ndarray,
    mask: np.ndarray,
) -> None:
    valid = np.asarray(mask, dtype=bool)
    if not valid.any():
        return
    error = np.asarray(prediction, dtype=np.float64) - np.asarray(target, dtype=np.float64)
    key = model_name, split, group_name, group_value
    aggregate = aggregates.setdefault(key, {"absolute_error": 0.0, "squared_error": 0.0, "feature_count": 0.0})
    aggregate["absolute_error"] += float(np.abs(error[valid]).sum())
    aggregate["squared_error"] += float(np.square(error[valid]).sum())
    aggregate["feature_count"] += float(valid.sum())


def _metric_rows(aggregates: dict[tuple[str, str, str, str], dict[str, float]]) -> list[dict[str, Any]]:
    rows = []
    for (model, split, group_name, group_value), aggregate in sorted(aggregates.items()):
        count = int(aggregate["feature_count"])
        rows.append({
            "model": model,
            "split": split,
            "group": group_name,
            "group_value": group_value,
            "feature_count": count,
            "mae": aggregate["absolute_error"] / count,
            "rmse": float(np.sqrt(aggregate["squared_error"] / count)),
        })
    return rows


def evaluate_models(
    models: Iterable[Any],
    manifest_records: Iterable[dict[str, Any]],
    examples: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Evaluate fitted models and return long-form grouped metric rows."""
    model_list = list(models)
    records = list(manifest_records)
    materialized = list(examples)
    if len(records) != len(materialized):
        raise ValueError("manifest and materialized example counts do not match")
    aggregates: dict[tuple[str, str, str, str], dict[str, float]] = {}

    for record, example in zip(records, materialized):
        split = str(record["split"])
        predictions = {model.name: model.predict(example) for model in model_list}
        targets = np.asarray(example["future_targets"], dtype=np.float32)
        target_mask = np.asarray(example["future_target_mask"], dtype=bool)
        k_value = str(record["context_count_k"])
        sparse_regime = str(record["sparse_regime"])
        for query_index, query_time in enumerate(example["future_query_time"]):
            groups = (
                ("overall", "all"),
                ("bearing", str(record["bearing_id"])),
                ("condition", str(record["experiment_id"])),
                ("K", f"K={k_value}"),
                ("sparse_regime", sparse_regime),
                ("future_horizon", horizon_label(float(query_time))),
            )
            for model in model_list:
                for group_name, group_value in groups:
                    _add_metrics(
                        aggregates,
                        model.name,
                        split,
                        group_name,
                        group_value,
                        predictions[model.name][query_index],
                        targets[query_index],
                        target_mask[query_index],
                    )
    return _metric_rows(aggregates)


def _write_metric_table(path: Path, rows: list[dict[str, Any]]) -> None:
    schema = pa.schema([
        ("model", pa.string()),
        ("split", pa.string()),
        ("group", pa.string()),
        ("group_value", pa.string()),
        ("feature_count", pa.int64()),
        ("mae", pa.float64()),
        ("rmse", pa.float64()),
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path, compression="zstd")


def run_baseline_evaluation(
    snapshot_path: str | Path,
    train_manifest_path: str | Path,
    evaluation_manifest_paths: Iterable[str | Path],
    output_dir: str | Path,
    *,
    random_state: int = 0,
) -> dict[str, Any]:
    """Fit baselines on train and evaluate them on one or more fixed manifests."""
    snapshot_store = SnapshotFeatureStore.from_parquet(snapshot_path)
    train_records = read_sample_manifest(train_manifest_path)
    train_examples = [materialize_example(record, snapshot_store) for record in train_records]
    mlp = SmallMLPBaseline(random_state=random_state).fit(train_examples)
    models = [PersistenceBaseline(), LinearTrendBaseline(), mlp]

    all_metrics: list[dict[str, Any]] = []
    evaluation_summary = []
    for manifest_path in evaluation_manifest_paths:
        path = Path(manifest_path)
        records = read_sample_manifest(path)
        examples = [materialize_example(record, snapshot_store) for record in records]
        metrics = evaluate_models(models, records, examples)
        all_metrics.extend(metrics)
        evaluation_summary.append({"path": str(path), "split": records[0]["split"] if records else None, "samples": len(records)})

    if not all_metrics:
        raise ValueError("no evaluation metrics were produced")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    metrics_path = output_path / "baseline_metrics.parquet"
    report_path = output_path / "baseline_report.json"
    _write_metric_table(metrics_path, all_metrics)
    report = {
        "schema_version": "xjtu_baseline_report_v1",
        "snapshot_path": str(snapshot_path),
        "train_manifest_path": str(train_manifest_path),
        "evaluation_manifests": evaluation_summary,
        "models": [model.name for model in models],
        "metrics_path": str(metrics_path),
        "training_samples": len(train_records),
        "status": "pass",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


__all__ = [
    "LinearTrendBaseline",
    "PersistenceBaseline",
    "SmallMLPBaseline",
    "evaluate_models",
    "horizon_label",
    "run_baseline_evaluation",
]


