"""Fit one candidate on its prepared rows; execution owns all child processes."""

import json
import warnings
from collections.abc import Callable
from pathlib import Path
from time import monotonic

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

from mlforge import evaluation
from mlforge.contracts import (
    CandidateResult,
    CandidateStatus,
    DomainError,
    PreparedRun,
    TaskKind,
)
from mlforge.datasets.records import TabularDataset
from mlforge.models import model_spec
from mlforge.prediction.runtime import ArtifactError, Predictor, environment
from mlforge.prediction.schema import fitted_schema, save_bundle
from mlforge.preprocessing import (
    MAX_FEATURES,
    MAX_MATRIX_BYTES,
    build_pipeline,
    input_fields,
    input_matrix,
    raw_records,
)
from mlforge.tasks import target_values


def fit_pipeline(
    dataset: TabularDataset,
    prepared: PreparedRun,
    model_id: str,
    progress: Callable[[str], None] | None = None,
) -> tuple[Pipeline, tuple[str, ...]]:
    """Child/headless-only result: exact standard fitted pipeline and safe warnings."""
    spec = prepared.experiment
    if (
        dataset.fingerprint != spec.dataset_fingerprint
        or json.loads(prepared.environment_json) != environment()
    ):
        raise DomainError(
            "STALE_RUN",
            "The prepared data or environment changed.",
            "Prepare the experiment again.",
        )
    try:
        definition = model_spec(model_id)
    except ValueError:
        raise DomainError(
            "MODEL", "Choose an available model.", "Return to Models."
        ) from None
    if definition.task != spec.task or model_id not in spec.model_ids:
        raise DomainError(
            "MODEL", "This model is not part of the prepared task.", "Return to Models."
        )
    fields = input_fields(dataset, prepared.schema, spec.feature_ids)
    matrix = input_matrix(
        dataset, prepared.schema, spec.feature_ids, prepared.train_rows
    )
    pipeline = build_pipeline(
        fields, definition.factory(spec.option), scale_numeric=definition.scale_numeric
    )
    notes = []
    for index, field in enumerate(fields):
        if field["type"] == "Number" and all(
            np.isnan(value) for value in matrix[:, index]
        ):
            notes.append(f"TRAIN_ALL_MISSING:{spec.feature_ids[index]}")
    with warnings.catch_warnings(record=True) as captured, threadpool_limits(limits=1):
        warnings.simplefilter("always")
        if progress:
            progress("preprocessing")
        # Fit each standard step once. Keep both objects in the exact Pipeline
        # later used for evaluation/export; no preflight fit or full-data refit.
        transformed = pipeline.steps[0][1].fit_transform(matrix)
        if (
            transformed.ndim != 2
            or not 1 <= transformed.shape[1] <= MAX_FEATURES
            or transformed.nbytes > MAX_MATRIX_BYTES
        ):
            raise DomainError(
                "MATRIX_LIMIT",
                "The fitted matrix exceeds its limits.",
                "Choose fewer features or simplify categories.",
            )
        if not np.isfinite(transformed).all():
            raise DomainError(
                "NUMERICAL",
                "Preprocessing produced nonfinite values.",
                "Review numeric magnitudes and selected features.",
            )
        if not np.any(np.ptp(transformed, axis=0) > 0):
            raise DomainError(
                "CONSTANT_TRAIN",
                "Every training input is constant or empty.",
                "Choose varying features or another dataset.",
            )
        if (
            spec.task == TaskKind.CLUSTERING
            and len(np.unique(transformed, axis=0)) < spec.option
        ):
            raise DomainError(
                "DISTINCT_ROWS",
                "There are fewer distinct input rows than requested groups.",
                "Choose fewer groups or more varied numeric inputs.",
            )
        if progress:
            progress("training")
        estimator = pipeline.steps[-1][1]
        if spec.task.supervised:
            labels = target_values(dataset, prepared.schema, spec.target_id, spec.task)
            y = np.asarray([labels[i] for i in prepared.train_rows])
            estimator.fit(transformed, y)
        else:
            estimator.fit(transformed)
        if any(issubclass(item.category, ConvergenceWarning) for item in captured):
            raise DomainError(
                "CONVERGENCE",
                "This candidate did not converge.",
                "Review the data or try another available model.",
            )
        notes.extend(
            sorted({f"FIT_WARNING:{item.category.__name__}" for item in captured})
        )
    if spec.task == TaskKind.CLUSTERING and len(set(estimator.labels_)) != spec.option:
        raise DomainError(
            "CLUSTERS",
            "The requested number of groups was not formed.",
            "Choose fewer groups or more varied numeric inputs.",
        )
    if spec.task == TaskKind.REDUCTION:
        ratios = estimator.explained_variance_ratio_
        if not np.isfinite(ratios).all():
            raise DomainError(
                "PCA_VARIANCE",
                "PCA variance is undefined.",
                "Choose inputs with nonzero variation.",
            )
        if np.any(estimator.explained_variance_ <= np.finfo(float).eps):
            notes.append("PCA_RANK_DEFICIENT")
    return pipeline, tuple(notes)


def _evaluate(dataset: TabularDataset, prepared: PreparedRun, pipeline: Pipeline):
    spec = prepared.experiment
    matrix = input_matrix(
        dataset,
        prepared.schema,
        spec.feature_ids,
        prepared.test_rows if spec.task.supervised else prepared.train_rows,
    )
    if spec.task.supervised:
        labels = target_values(dataset, prepared.schema, spec.target_id, spec.task)
        train_y = [labels[i] for i in prepared.train_rows]
        test_y = [labels[i] for i in prepared.test_rows]
        predicted = pipeline.predict(matrix)
        evaluator = (
            evaluation.classification
            if spec.task == TaskKind.CLASSIFICATION
            else evaluation.regression
        )
        return evaluator(train_y, test_y, predicted)
    transformed = pipeline.steps[0][1].transform(matrix)
    estimator = pipeline.steps[-1][1]
    if spec.task == TaskKind.CLUSTERING:
        return evaluation.clustering(
            transformed,
            estimator.labels_,
            estimator.cluster_centers_,
            estimator.inertia_,
            estimator.n_iter_,
        )
    return evaluation.reduction(
        transformed,
        estimator.inverse_transform(estimator.transform(transformed)),
        estimator.explained_variance_,
        estimator.explained_variance_ratio_,
    )


def train_candidate(
    dataset: TabularDataset,
    prepared: PreparedRun,
    model_id: str,
    directory: Path,
    progress: Callable[[str], None] | None = None,
) -> CandidateResult:
    """Fit/evaluate/save once; return only a validated opaque immutable handle.

    The caller owns the new private output directory and accepts this provisional
    result only after worker exit/integrity validation. Failed output is never a
    completed candidate. No source path or split row IDs enter the artifact.
    """
    started = monotonic()
    try:
        pipeline, notes = fit_pipeline(dataset, prepared, model_id, progress)
        if progress:
            progress("evaluating")
        with threadpool_limits(limits=1):
            assessed = _evaluate(dataset, prepared, pipeline)
        if progress:
            progress("validating_artifact")
        spec = prepared.experiment
        fields = input_fields(dataset, prepared.schema, spec.feature_ids)
        schema = fitted_schema(
            pipeline,
            fields,
            raw_records(dataset, spec.feature_ids, prepared.train_rows),
        )
        bundle = save_bundle(
            directory,
            pipeline,
            schema,
            model_id,
            training_count=len(prepared.train_rows),
            test_count=len(prepared.test_rows),
            metrics={
                m.key: {"value": m.value, "reason": m.reason} for m in assessed.metrics
            },
            diagnostics=json.loads(assessed.diagnostics_json),
            warnings=notes,
            acknowledgements=spec.acknowledgements,
        )
        Predictor._from_directory(directory)
    except DomainError:
        raise
    except OSError:
        raise DomainError(
            "STORAGE",
            "The candidate artifact could not be saved.",
            "Check free space and permissions, then retry.",
        ) from None
    except ArtifactError:
        raise DomainError(
            "ARTIFACT",
            "The fitted candidate artifact failed validation.",
            "Retry this candidate in the supported environment.",
        ) from None
    except Exception:
        raise DomainError(
            "CANDIDATE_FAILED",
            "This candidate could not be fitted or evaluated.",
            "Review the data or try another available model.",
        ) from None
    return CandidateResult(
        model_id,
        CandidateStatus.COMPLETED,
        monotonic() - started,
        assessed.metrics,
        assessed.diagnostics_json,
        notes,
        bundle,
    )
