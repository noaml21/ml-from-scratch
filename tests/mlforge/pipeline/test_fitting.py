"""Real six-model fitting and training-only preprocessing sentinels."""

import json
import warnings
from dataclasses import replace
from importlib import resources

import numpy as np
import pytest
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

from mlforge.contracts import DomainError, ExperimentSpec, TaskKind
from mlforge.datasets.importers import load_dataset
from mlforge.datasets.inference import infer_schema
from mlforge.datasets.records import Cell
from mlforge.models import MODELS
from mlforge.prediction.runtime import load_pipeline
from mlforge.preprocessing import input_matrix, prepare_run
from mlforge.tasks import review_warnings
from mlforge.training import fit_pipeline

FILES = {
    TaskKind.CLASSIFICATION: ("classification.csv", "c2", ("c0", "c1"), None),
    TaskKind.REGRESSION: ("regression.tsv", "c2", ("c0", "c1"), None),
    TaskKind.CLUSTERING: ("clustering.csv", None, ("c0", "c1"), 3),
    TaskKind.REDUCTION: ("reduction.jsonl", None, ("c0", "c1", "c2"), 2),
}


def setup(model):
    filename, target, features, option = FILES[model.task]
    resource = resources.files("mlforge").joinpath("examples", filename)
    with resources.as_file(resource) as path:
        dataset = load_dataset(path)
    schema = infer_schema(dataset)
    spec = ExperimentSpec(
        1, dataset.fingerprint, model.task, target, features, (model.id,), option
    )
    spec = replace(
        spec,
        acknowledgements=tuple(w.code for w in review_warnings(dataset, schema, spec)),
    )
    return dataset, prepare_run(dataset, schema, spec)


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.id)
def test_every_model_fits_standard_serializable_pipeline(model):
    import skops.io as sio

    dataset, prepared = setup(model)
    stages = []
    first, notes = fit_pipeline(dataset, prepared, model.id, stages.append)
    second, _ = fit_pipeline(dataset, prepared, model.id)
    matrix = input_matrix(
        dataset,
        prepared.schema,
        prepared.experiment.feature_ids,
        prepared.test_rows or prepared.train_rows,
    )
    operation = "transform" if model.task == TaskKind.REDUCTION else "predict"
    expected = getattr(first, operation)(matrix)
    actual = getattr(second, operation)(matrix)
    np.testing.assert_array_equal(expected, actual)
    restored = load_pipeline(sio.dumps(first), model.id)
    np.testing.assert_array_equal(expected, getattr(restored, operation)(matrix))
    assert stages == ["preprocessing", "training"]
    if model.task != TaskKind.CLASSIFICATION:
        assert np.isfinite(expected).all()
    assert first is not second and first.steps[0][1] is not second.steps[0][1]


def test_holdout_extremes_never_fit_median_or_scaler():
    model = MODELS[0]
    dataset, prepared = setup(model)
    original, _ = fit_pipeline(dataset, prepared, model.id)
    rows = list(dataset.rows)
    for i in prepared.test_rows:
        rows[i] = (Cell("1000000000"), rows[i][1], rows[i][2])
    changed = replace(dataset, rows=tuple(rows))
    after, _ = fit_pipeline(changed, prepared, model.id)
    first = original.steps[0][1].named_transformers_["number"]
    last = after.steps[0][1].named_transformers_["number"]
    np.testing.assert_array_equal(
        first["imputer"].statistics_, last["imputer"].statistics_
    )
    np.testing.assert_array_equal(first["scaler"].mean_, last["scaler"].mean_)
    np.testing.assert_array_equal(first["scaler"].scale_, last["scaler"].scale_)


def test_train_all_missing_uses_zero_and_warns():
    model = MODELS[0]
    dataset, prepared = setup(model)
    rows = list(dataset.rows)
    for i in prepared.train_rows:
        rows[i] = (Cell(""), rows[i][1], rows[i][2])
    dataset = replace(dataset, rows=tuple(rows))
    # Effective type was confirmed from full data; training-only emptiness matters.
    pipeline, notes = fit_pipeline(dataset, prepared, model.id)
    assert (
        pipeline.steps[0][1].named_transformers_["number"]["imputer"].statistics_[0]
        == 0
    )
    assert "TRAIN_ALL_MISSING:c0" in notes


def test_constant_training_and_insufficient_groups_fail_before_model_fit(monkeypatch):
    model = MODELS[0]
    dataset, prepared = setup(model)
    rows = list(dataset.rows)
    for i in prepared.train_rows:
        rows[i] = (Cell("1"), Cell("1"), rows[i][2])

    def forbidden(*args, **kwargs):
        raise AssertionError("Estimator fit ran before constant gate")

    monkeypatch.setattr(LogisticRegression, "fit", forbidden)
    with pytest.raises(DomainError, match="constant or empty"):
        fit_pipeline(replace(dataset, rows=tuple(rows)), prepared, model.id)
    model = MODELS[4]
    dataset, prepared = setup(model)
    dataset = replace(
        dataset,
        rows=tuple(
            (Cell(str(i % 2)), Cell(str(i % 2))) for i in range(len(dataset.rows))
        ),
    )
    with pytest.raises(DomainError, match="fewer distinct"):
        fit_pipeline(dataset, prepared, model.id)


def test_convergence_warning_fails_candidate_and_stale_environment_refused(monkeypatch):
    model = MODELS[0]
    dataset, prepared = setup(model)
    original = LogisticRegression.fit

    def not_converged(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        warnings.warn("private solver details", ConvergenceWarning)
        return result

    monkeypatch.setattr(LogisticRegression, "fit", not_converged)
    with pytest.raises(DomainError) as caught:
        fit_pipeline(dataset, prepared, model.id)
    assert caught.value.code == "CONVERGENCE" and "private" not in str(caught.value)
    environment = json.loads(prepared.environment_json)
    environment["python_minor"] = "0.0"
    with pytest.raises(DomainError, match="environment changed"):
        fit_pipeline(
            dataset,
            replace(prepared, environment_json=json.dumps(environment)),
            model.id,
        )
    with pytest.raises(DomainError, match="not part"):
        fit_pipeline(dataset, prepared, MODELS[2].id)


def test_category_vocabulary_uses_train_only_and_unknown_holdout_predicts():
    model = MODELS[0]
    resource = resources.files("mlforge").joinpath("examples", "mixed.csv")
    with resources.as_file(resource) as path:
        dataset = load_dataset(path)
    schema = infer_schema(dataset)
    spec = ExperimentSpec(
        1, dataset.fingerprint, model.task, "c7", ("c1", "c2", "c4", "c5"), (model.id,)
    )
    prepared = prepare_run(dataset, schema, spec)
    rows = list(dataset.rows)
    for i in prepared.test_rows:
        row = list(rows[i])
        row[4] = Cell("only in test")
        rows[i] = tuple(row)
    dataset = replace(dataset, rows=tuple(rows))
    pipeline, _ = fit_pipeline(dataset, prepared, model.id)
    encoder = pipeline.steps[0][1].named_transformers_["category"]["encoder"]
    assert "v:only in test" not in encoder.categories_[0]
    assert len(
        pipeline.predict(
            input_matrix(dataset, schema, spec.feature_ids, prepared.test_rows)
        )
    ) == len(prepared.test_rows)


def test_rank_deficient_pca_is_explained():
    model = MODELS[-1]
    dataset, prepared = setup(model)
    dataset = replace(
        dataset,
        rows=tuple(
            (Cell(str(i)), Cell(str(i * 2)), Cell(str(i * 3)))
            for i in range(len(dataset.rows))
        ),
    )
    pipeline, notes = fit_pipeline(dataset, prepared, model.id)
    assert "PCA_RANK_DEFICIENT" in notes
    assert pipeline.steps[-1][1].explained_variance_ratio_[1] < 1e-10
