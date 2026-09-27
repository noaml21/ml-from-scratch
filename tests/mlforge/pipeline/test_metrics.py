"""Independently calculated metrics, baselines, edge cases and ranking rules."""

import json
import math
from dataclasses import replace

import numpy as np
import pytest
from threadpoolctl import threadpool_limits

from mlforge.contracts import (
    CandidateResult,
    CandidateStatus,
    DomainError,
    Metric,
    ModelBundle,
    TaskKind,
)
from mlforge.evaluation import (
    PRIMARY_METRICS,
    classification,
    clustering,
    ranked_candidates,
    recommendation,
    reduction,
    regression,
)


def values(result):
    return {metric.key: metric.value for metric in result.metrics}


def test_classification_hand_calculation_and_train_only_baseline():
    result = classification(
        ["b", "a", "b", "a"], ["a", "a", "b", "b"], ["a", "b", "b", "b"]
    )
    assert values(result) == pytest.approx(
        {"accuracy": 0.75, "macro_f1": (2 / 3 + 4 / 5) / 2}
    )
    details = json.loads(result.diagnostics_json)
    assert details["labels"] == ["a", "b"]
    assert details["confusion_matrix"] == [[1, 1], [0, 2]]
    assert details["per_class"][0] == pytest.approx(
        {"label": "a", "precision": 1.0, "recall": 0.5, "f1": 2 / 3, "support": 2}
    )
    assert (
        details["baseline"]["label"] == "a"
    )  # TRAIN frequency tie uses lexical order.
    assert details["baseline"]["accuracy"] == 0.5
    assert details["baseline"]["macro_f1"] == pytest.approx(1 / 3)
    assert details["train_class_counts"] == {"a": 2, "b": 2}


def test_absent_predicted_class_uses_zero_division_without_dropping_class():
    result = classification(["a", "a", "b"], ["a", "b"], ["a", "a"])
    assert values(result)["macro_f1"] == pytest.approx(1 / 3)
    missing = json.loads(result.diagnostics_json)["per_class"][1]
    assert missing["precision"] == missing["recall"] == missing["f1"] == 0
    with pytest.raises(DomainError):
        classification(["a", "b"], ["a", "b"], ["a", "unexpected"])


def test_regression_hand_calculation_negative_r2_and_train_mean():
    result = regression([2, 4], [1, 3], [2, 5])
    assert values(result) == pytest.approx(
        {"mae": 1.5, "rmse": math.sqrt(2.5), "r2": -1.5}
    )
    details = json.loads(result.diagnostics_json)
    assert details["residuals"] == {
        "count": 2,
        "mean": -1.5,
        "minimum": -2.0,
        "maximum": -1.0,
    }
    assert details["baseline_mean"] == 3  # TRAIN mean, not test mean 2.
    assert details["baseline"] == pytest.approx(
        {"mae": 1.0, "rmse": math.sqrt(2), "r2": -1.0}
    )


def test_constant_test_r2_is_explicitly_unavailable():
    result = regression([1, 2], [3, 3], [3, 3])
    r2 = next(m for m in result.metrics if m.key == "r2")
    assert r2.value is None and "constant" in r2.reason
    assert values(result)["mae"] == 0
    assert json.loads(result.diagnostics_json)["baseline"]["r2"] is None


@pytest.mark.parametrize(
    "train,truth,predicted",
    [
        ([], [1], [1]),
        ([1], [1, 2], [1]),
        ([1], [math.inf], [1]),
        ([1], [1], [math.nan]),
        ([1], [1e308], [-1e308]),
    ],
)
def test_invalid_regression_outputs_fail_safely(train, truth, predicted):
    with pytest.raises(DomainError) as error:
        regression(train, truth, predicted)
    assert error.value.code == "EVALUATION"


def test_silhouette_hand_calculation_and_no_quality_recommendation():
    result = clustering([[0], [1], [10], [11]], [0, 0, 1, 1], [[0.5], [10.5]], 1.0, 2)
    assert values(result)["silhouette"] == pytest.approx(
        ((10.5 - 1) / 10.5 + (9.5 - 1) / 9.5) / 2
    )
    details = json.loads(result.diagnostics_json)
    assert details["cluster_sizes"] == {"0": 2, "1": 2}
    assert details["centers"] == [[0.5], [10.5]]
    assert details["silhouette_rows"] == 4 and not details["silhouette_sampled"]
    assert recommendation(TaskKind.CLUSTERING, ()) is None


@pytest.mark.parametrize("labels,centers", [([0, 0], [[0.5]]), ([0, 1], [[0], [1]])])
def test_degenerate_silhouette_is_na_with_reason(labels, centers):
    result = clustering([[0], [1]], labels, centers, 0.0, 1)
    metric = result.metrics[0]
    assert metric.value is None and metric.reason


def test_silhouette_sampling_is_bounded_and_reproducible():
    matrix = np.arange(2100, dtype=float).reshape(-1, 1)
    labels = np.arange(2100) // 700
    with threadpool_limits(limits=1):
        first = clustering(matrix, labels, [[350], [1050], [1750]], 100.0, 2)
        second = clustering(matrix, labels, [[350], [1050], [1750]], 100.0, 2)
    assert first == second
    details = json.loads(first.diagnostics_json)
    assert details["silhouette_sampled"] and details["silhouette_rows"] == 2000


def test_fractional_or_invalid_cluster_ids_not_silently_coerced():
    for labels in ([0.0, 0.5], [-1, 0], [0, 2]):
        with pytest.raises(DomainError):
            clustering([[0], [1]], labels, [[0.5]], 0.0, 1)


def test_pca_reconstruction_and_variance_hand_calculation():
    result = reduction([[1, 2], [3, 4]], [[1, 1], [3, 3]], [2.0], [0.75])
    assert values(result) == {"retained_variance": 0.75, "components": 1.0}
    details = json.loads(result.diagnostics_json)
    assert details["reconstruction_mse"] == 0.5 and details["original_features"] == 2
    assert details["per_component"] == [
        {"component": 1, "variance": 2.0, "variance_ratio": 0.75}
    ]
    assert recommendation(TaskKind.REDUCTION, ()) is None
    with pytest.raises(DomainError):
        reduction([[1, 1], [1, 1]], [[1, 1], [1, 1]], [0.0], [0.0])


def candidate(model, task, metrics):
    bundle = ModelBundle("synthetic", model, task, "model-hash", "schema-hash", "{}")
    return CandidateResult(
        model,
        CandidateStatus.COMPLETED,
        1.0,
        tuple(Metric(k, v) for k, v in metrics.items()),
        bundle=bundle,
    )


def test_ranking_stable_ties_invalid_and_partial_results():
    task = TaskKind.CLASSIFICATION
    a = candidate("a", task, {"macro_f1": 0.8, "accuracy": 0.9})
    b = candidate("b", task, {"macro_f1": 0.8, "accuracy": 0.8})
    c = candidate("c", task, {"macro_f1": 0.8, "accuracy": 0.9})
    invalid = candidate("invalid", task, {"macro_f1": None, "accuracy": 1.0})
    failed = CandidateResult(
        "failed", CandidateStatus.FAILED, 1.0, error_code="CONVERGENCE"
    )
    assert [
        r.model_id for r in ranked_candidates(task, (c, b, invalid, failed, a))
    ] == ["a", "c", "b"]
    assert recommendation(task, (c, b, a)) == (
        "a",
        "Recommended based on test performance",
    )
    assert recommendation(task, (failed, a)) == ("a", "Only completed model")
    assert recommendation(task, (failed, invalid)) is None
    # Higher F1 wins even when accuracy is lower.
    assert (
        ranked_candidates(
            task,
            (a, replace(b, metrics=(Metric("macro_f1", 0.9), Metric("accuracy", 0.1)))),
        )[0].model_id
        == "b"
    )
    rtask = TaskKind.REGRESSION
    r1 = candidate("a", rtask, {"mae": 2.0, "r2": 0.9})
    r2 = candidate("b", rtask, {"mae": 1.0, "r2": None})
    assert ranked_candidates(rtask, (r1, r2))[0] == r2
    assert all(len(metrics) <= 2 for metrics in PRIMARY_METRICS.values())
