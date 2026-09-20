"""Finite task metrics, descriptive diagnostics and deterministic ranking."""

import json
import math
from collections import Counter
from dataclasses import dataclass

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    silhouette_score,
)

from mlforge.contracts import (
    CandidateResult,
    CandidateStatus,
    DomainError,
    Metric,
    TaskKind,
)


@dataclass(frozen=True)
class Evaluation:
    metrics: tuple[Metric, ...]
    diagnostics_json: str


@dataclass(frozen=True)
class MetricSpec:
    key: str
    label: str
    higher_is_better: bool | None


PRIMARY_METRICS = {
    TaskKind.CLASSIFICATION: (
        MetricSpec("accuracy", "Accuracy", True),
        MetricSpec("macro_f1", "Macro F1", True),
    ),
    TaskKind.REGRESSION: (
        MetricSpec("mae", "MAE", False),
        MetricSpec("r2", "R²", True),
    ),
    TaskKind.CLUSTERING: (
        MetricSpec("silhouette", "Silhouette", None),
        MetricSpec("clusters", "Groups", None),
    ),
    TaskKind.REDUCTION: (
        MetricSpec("retained_variance", "Retained variance", None),
        MetricSpec("components", "Components", None),
    ),
}


def _error() -> DomainError:
    return DomainError(
        "EVALUATION",
        "This candidate produced invalid evaluation values.",
        "Review the data or try another available model.",
    )


def _result(metrics: tuple[Metric, ...], diagnostics: dict) -> Evaluation:
    if any(
        metric.value is not None and not math.isfinite(metric.value)
        for metric in metrics
    ):
        raise _error()
    try:
        return Evaluation(
            metrics, json.dumps(diagnostics, allow_nan=False, sort_keys=True)
        )
    except (ValueError, TypeError):
        raise _error() from None


def classification(train_y, test_y, predictions) -> Evaluation:
    if not len(train_y) or not len(test_y) or len(test_y) != len(predictions):
        raise _error()
    labels = sorted(set(train_y))
    if not set(test_y) <= set(labels) or not set(predictions) <= set(labels):
        raise _error()
    accuracy = float(accuracy_score(test_y, predictions))
    macro = float(
        f1_score(test_y, predictions, labels=labels, average="macro", zero_division=0)
    )
    precision, recall, f1, support = precision_recall_fscore_support(
        test_y, predictions, labels=labels, zero_division=0
    )
    train_counts, test_counts = Counter(train_y), Counter(test_y)
    majority = min(labels, key=lambda label: (-train_counts[label], label))
    baseline = [majority] * len(test_y)
    return _result(
        (Metric("accuracy", accuracy), Metric("macro_f1", macro)),
        {
            "labels": labels,
            "confusion_matrix": confusion_matrix(
                test_y, predictions, labels=labels
            ).tolist(),
            "per_class": [
                {
                    "label": label,
                    "precision": float(p),
                    "recall": float(r),
                    "f1": float(f),
                    "support": int(s),
                }
                for label, p, r, f, s in zip(
                    labels, precision, recall, f1, support, strict=True
                )
            ],
            "train_class_counts": dict(train_counts),
            "test_class_counts": dict(test_counts),
            "baseline": {
                "label": majority,
                "accuracy": float(accuracy_score(test_y, baseline)),
                "macro_f1": float(
                    f1_score(
                        test_y,
                        baseline,
                        labels=labels,
                        average="macro",
                        zero_division=0,
                    )
                ),
            },
        },
    )


def _regression_metrics(truth: np.ndarray, predicted: np.ndarray) -> dict:
    residual = truth - predicted
    mae = float(np.mean(np.abs(residual)))
    rmse = float(np.sqrt(np.mean(residual**2)))
    variation = float(np.sum((truth - np.mean(truth)) ** 2))
    r2 = (
        None
        if len(truth) < 2 or variation == 0
        else float(1 - np.sum(residual**2) / variation)
    )
    return {"mae": mae, "rmse": rmse, "r2": r2}


def regression(train_y, test_y, predictions) -> Evaluation:
    train, truth, predicted = (
        np.asarray(values, dtype=float) for values in (train_y, test_y, predictions)
    )
    if any(
        values.ndim != 1 or not len(values) or not np.isfinite(values).all()
        for values in (train, truth, predicted)
    ) or len(truth) != len(predicted):
        raise _error()
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            scores = _regression_metrics(truth, predicted)
            mean = float(np.mean(train))
            baseline = _regression_metrics(truth, np.full(len(truth), mean))
            residual = truth - predicted
            summary = {
                "count": len(truth),
                "mean": float(np.mean(residual)),
                "minimum": float(np.min(residual)),
                "maximum": float(np.max(residual)),
            }
    except FloatingPointError:
        raise _error() from None
    reason = (
        "R² is undefined for a constant or single-row test target."
        if scores["r2"] is None
        else None
    )
    return _result(
        (
            Metric("mae", scores["mae"]),
            Metric("r2", scores["r2"], reason),
            Metric("rmse", scores["rmse"]),
        ),
        {"residuals": summary, "baseline_mean": mean, "baseline": baseline},
    )


def clustering(matrix, labels, centers, inertia: float, iterations: int) -> Evaluation:
    matrix, labels = np.asarray(matrix, dtype=float), np.asarray(labels)
    centers = np.asarray(centers, dtype=float)
    if (
        matrix.ndim != 2
        or labels.ndim != 1
        or len(labels) != len(matrix)
        or not len(labels)
        or not np.isfinite(matrix).all()
        or labels.dtype.kind not in {"i", "u"}
        or np.any(labels < 0)
        or centers.ndim != 2
        or centers.shape[1] != matrix.shape[1]
        or not np.isfinite(centers).all()
        or labels.max() >= len(centers)
        or not math.isfinite(inertia)
        or inertia < 0
        or iterations < 1
    ):
        raise _error()
    indices = (
        np.random.RandomState(42).choice(len(matrix), 2000, replace=False)
        if len(matrix) > 2000
        else np.arange(len(matrix))
    )
    sample_labels = labels[indices]
    unique = len(set(sample_labels))
    if unique < 2 or unique == len(indices):
        silhouette, reason = (
            None,
            "Silhouette needs at least two groups and fewer groups than sampled rows.",
        )
    else:
        silhouette, reason = (
            float(silhouette_score(matrix[indices], sample_labels)),
            None,
        )
    counts = Counter(int(label) for label in labels)
    return _result(
        (
            Metric("silhouette", silhouette, reason),
            Metric("clusters", float(len(counts))),
        ),
        {
            "cluster_sizes": {
                str(label): size for label, size in sorted(counts.items())
            },
            "centers": np.asarray(centers, dtype=float).tolist(),
            "inertia": float(inertia),
            "iterations": int(iterations),
            "actual_clusters": len(counts),
            "silhouette_rows": len(indices),
            "silhouette_sampled": len(matrix) > 2000,
            "scope": "Exploration on this dataset; cluster IDs are arbitrary.",
        },
    )


def reduction(matrix, reconstructed, variance, variance_ratios) -> Evaluation:
    matrix, reconstructed = (
        np.asarray(matrix, dtype=float),
        np.asarray(reconstructed, dtype=float),
    )
    variance, ratios = (
        np.asarray(variance, dtype=float),
        np.asarray(variance_ratios, dtype=float),
    )
    if (
        matrix.ndim != 2
        or reconstructed.shape != matrix.shape
        or not matrix.size
        or variance.ndim != 1
        or ratios.shape != variance.shape
        or not len(ratios)
        or not all(
            np.isfinite(v).all() for v in (matrix, reconstructed, variance, ratios)
        )
        or np.any(variance < 0)
        or np.any(ratios < 0)
        or ratios.sum() > 1 + 1e-10
        or variance.sum() <= 0
    ):
        raise _error()
    try:
        with np.errstate(over="raise", invalid="raise"):
            mse = float(np.mean((matrix - reconstructed) ** 2))
    except FloatingPointError:
        raise _error() from None
    return _result(
        (
            Metric("retained_variance", float(ratios.sum())),
            Metric("components", float(len(ratios))),
        ),
        {
            "per_component": [
                {"component": i + 1, "variance": float(v), "variance_ratio": float(r)}
                for i, (v, r) in enumerate(zip(variance, ratios, strict=True))
            ],
            "reconstruction_mse": mse,
            "original_features": matrix.shape[1],
            "retained_components": len(ratios),
            "scope": "Standardized feature space; descriptive variance, "
            "not predictive accuracy.",
        },
    )


def ranked_candidates(
    task: TaskKind, results: tuple[CandidateResult, ...]
) -> tuple[CandidateResult, ...]:
    required = (
        ("macro_f1", "accuracy")
        if task == TaskKind.CLASSIFICATION
        else ("mae",)
        if task == TaskKind.REGRESSION
        else ()
    )
    valid = []
    for result in results:
        values = {metric.key: metric.value for metric in result.metrics}
        if result.status != CandidateStatus.COMPLETED or result.bundle.task != task:
            continue
        if any(
            values.get(key) is None or not math.isfinite(values[key])
            for key in required
        ):
            continue
        key = (
            (-values["macro_f1"], -values["accuracy"], result.model_id)
            if task == TaskKind.CLASSIFICATION
            else (values["mae"], result.model_id)
            if task == TaskKind.REGRESSION
            else (result.model_id,)
        )
        valid.append((key, result))
    return tuple(result for _, result in sorted(valid, key=lambda item: item[0]))


def recommendation(
    task: TaskKind, results: tuple[CandidateResult, ...]
) -> tuple[str, str] | None:
    if not task.supervised or not (ranked := ranked_candidates(task, results)):
        return None
    return ranked[0].model_id, "Only completed model" if len(
        ranked
    ) == 1 else "Recommended based on test performance"
