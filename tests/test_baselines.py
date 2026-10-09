from __future__ import annotations

import numpy as np

from data_generator.baselines.causal import (
    LinearTrendBaseline,
    PersistenceBaseline,
    SmallMLPBaseline,
    evaluate_models,
)
from data_generator.features.xjtu import FEATURE_DIMENSION


def _example(sample_id: str = "sample-1", future_count: int = 2) -> dict:
    context_count = 10
    context_times = np.arange(-540.0, 1.0, 60.0, dtype=np.float32)
    context_features = np.repeat(np.arange(1, 11, dtype=np.float32)[:, None], FEATURE_DIMENSION, axis=1)
    future_times = np.arange(60.0, 60.0 * (future_count + 1), 60.0, dtype=np.float32)
    future_targets = np.repeat(
        np.arange(11, 11 + future_count, dtype=np.float32)[:, None],
        FEATURE_DIMENSION,
        axis=1,
    )
    return {
        "context_features": context_features,
        "context_relative_time": context_times,
        "context_mask": np.ones((context_count, FEATURE_DIMENSION), dtype=bool),
        "future_query_time": future_times,
        "future_targets": future_targets,
        "future_target_mask": np.ones((future_count, FEATURE_DIMENSION), dtype=bool),
        "context_length": np.int64(context_count),
        "future_length": np.int64(future_count),
        "sample_id": sample_id,
    }


def _manifest(sample_id: str = "sample-1", k: int = 10, q: int = 2) -> dict:
    return {
        "sample_id": sample_id,
        "split": "validation",
        "bearing_id": "Bearing1_5",
        "experiment_id": "condition_1",
        "context_count_k": k,
        "sparse_regime": "dense",
        "future_query_count_q": q,
    }


def test_persistence_and_linear_baselines_return_query_by_feature_arrays():
    example = _example()
    persistence = PersistenceBaseline().predict(example)
    linear = LinearTrendBaseline().predict(example)

    assert persistence.shape == (2, FEATURE_DIMENSION)
    assert linear.shape == (2, FEATURE_DIMENSION)
    assert np.allclose(persistence[0], 10.0)
    assert np.isfinite(linear).all()


def test_small_mlp_trains_and_predicts_masked_query_targets():
    examples = []
    for index in range(5):
        example = _example(sample_id=f"sample-{index}")
        example["future_targets"] = example["future_targets"] + index * 0.1
        examples.append(example)

    model = SmallMLPBaseline(
        random_state=3,
        hidden_layer_sizes=(8,),
        max_iter=5,
    ).fit(examples)
    prediction = model.predict(examples[0])

    assert prediction.shape == (2, FEATURE_DIMENSION)
    assert np.isfinite(prediction).all()


def test_evaluate_models_reports_requested_group_dimensions():
    examples = [_example()]
    records = [_manifest()]
    rows = evaluate_models(
        [PersistenceBaseline(), LinearTrendBaseline()],
        records,
        examples,
    )

    groups = {(row["model"], row["group"]) for row in rows}
    assert ("persistence", "bearing") in groups
    assert ("persistence", "condition") in groups
    assert ("persistence", "K") in groups
    assert ("persistence", "sparse_regime") in groups
    assert ("persistence", "future_horizon") in groups
    assert all(row["feature_count"] > 0 for row in rows)
    assert all(row["mae"] >= 0.0 and row["rmse"] >= 0.0 for row in rows)

