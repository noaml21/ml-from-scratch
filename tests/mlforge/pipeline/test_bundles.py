"""Exact evaluated pipeline retention, artifact metadata and leakage boundaries."""

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import numpy as np
import pytest
from sklearn.compose import ColumnTransformer

from mlforge import training
from mlforge.contracts import CandidateStatus, DomainError, ExperimentSpec, TaskKind
from mlforge.datasets.importers import load_dataset
from mlforge.datasets.inference import infer_schema
from mlforge.datasets.records import Cell
from mlforge.export.wheel import export_wheel
from mlforge.prediction import runtime
from mlforge.prediction.runtime import Predictor
from mlforge.preprocessing import input_matrix, prepare_run, raw_records
from mlforge.tasks import review_warnings


def test_evaluate_save_retains_exact_single_fit(
    prepared_candidate, tmp_path, monkeypatch
):
    dataset, prepared, model = prepared_candidate
    captured, sizes = [], []
    original_fit = training.fit_pipeline
    original_transform = ColumnTransformer.fit_transform

    def observe_transform(self, x, *args, **kwargs):
        sizes.append(len(x))
        return original_transform(self, x, *args, **kwargs)

    def observe_fit(*args, **kwargs):
        pipeline, notes = original_fit(*args, **kwargs)
        captured.append(pipeline)

        # Any later fit, including serialization/validation, is a regression.
        def forbidden(*args, **kwargs):
            raise AssertionError("Evaluated pipeline was refitted")

        monkeypatch.setattr(type(pipeline.steps[-1][1]), "fit", forbidden)
        return pipeline, notes

    monkeypatch.setattr(ColumnTransformer, "fit_transform", observe_transform)
    monkeypatch.setattr(training, "fit_pipeline", observe_fit)
    stages = []
    result = training.train_candidate(
        dataset, prepared, model.id, tmp_path / "bundle", stages.append
    )
    assert result.status == CandidateStatus.COMPLETED
    assert sizes == [len(prepared.train_rows)]
    assert stages == ["preprocessing", "training", "evaluating", "validating_artifact"]
    with pytest.raises(FrozenInstanceError):
        result.bundle.model_id = "other"
    meta = json.loads(result.bundle.metadata_json)
    assert meta["training_count"] == len(prepared.train_rows)
    assert meta["test_count"] == len(prepared.test_rows)
    assert meta["metrics"] == {
        m.key: {"value": m.value, "reason": m.reason} for m in result.metrics
    }
    assert meta["diagnostics"] == json.loads(result.diagnostics_json)
    assert meta["review_acknowledgements"] == list(prepared.experiment.acknowledgements)
    assert "train_rows" not in meta and str(tmp_path) not in result.bundle.metadata_json
    rows = prepared.test_rows or prepared.train_rows
    matrix = input_matrix(
        dataset, prepared.schema, prepared.experiment.feature_ids, rows
    )
    operation = "transform" if model.task == TaskKind.REDUCTION else "predict"
    expected = getattr(captured[0], operation)(matrix)
    predictor = Predictor._from_directory(result.bundle.directory)
    records = raw_records(dataset, prepared.experiment.feature_ids, rows)
    actual = getattr(predictor, operation + "_many")(records)
    key = (
        "components"
        if operation == "transform"
        else "cluster"
        if model.task == TaskKind.CLUSTERING
        else "prediction"
    )
    np.testing.assert_array_equal(expected, [row[key] for row in actual])


def test_evaluated_metadata_repeats_deterministically(prepared_candidate, tmp_path):
    dataset, prepared, model = prepared_candidate
    first = training.train_candidate(dataset, prepared, model.id, tmp_path / "first")
    second = training.train_candidate(dataset, prepared, model.id, tmp_path / "second")
    assert first.metrics == second.metrics
    assert first.diagnostics_json == second.diagnostics_json
    a, b = (
        json.loads(first.bundle.metadata_json),
        json.loads(second.bundle.metadata_json),
    )
    # skops ZIP timestamps may change; model bytes are not a determinism promise.
    a.pop("model_sha256")
    b.pop("model_sha256")
    assert a == b


def test_evaluation_or_storage_failure_never_returns_completed_bundle(
    prepared_candidate, tmp_path, monkeypatch
):
    dataset, prepared, model = prepared_candidate

    def invalid(*args):
        raise ValueError("private source value must never escape")

    monkeypatch.setattr(training, "_evaluate", invalid)
    with pytest.raises(DomainError) as error:
        training.train_candidate(dataset, prepared, model.id, tmp_path / "failed")
    assert error.value.code == "CANDIDATE_FAILED" and "private" not in str(error.value)
    assert not (tmp_path / "failed").exists()
    monkeypatch.undo()
    (tmp_path / "occupied").mkdir()
    with pytest.raises(DomainError) as error:
        training.train_candidate(dataset, prepared, model.id, tmp_path / "occupied")
    assert error.value.code == "STORAGE"


def test_holdout_ranges_categories_and_fallback_never_enter_bundle(tmp_path):
    source = tmp_path / "table.csv"
    source.write_text(
        "number,other,category,label\n"
        + "".join(f"{i},{i % 3},known,class_{i % 2}\n" for i in range(60))
    )
    dataset = load_dataset(source)
    # Category needs variation to be selectable.
    rows = list(dataset.rows)
    rows[0] = (*rows[0][:2], Cell("second"), rows[0][3])
    dataset = replace(dataset, rows=tuple(rows))
    schema = infer_schema(dataset)
    spec = ExperimentSpec(
        1,
        dataset.fingerprint,
        TaskKind.CLASSIFICATION,
        "c3",
        ("c0", "c1", "c2"),
        ("classification.logistic",),
    )
    prepared = prepare_run(dataset, schema, spec)
    rows = list(dataset.rows)
    for i in prepared.train_rows:
        rows[i] = (Cell(""), *rows[i][1:])
    for i in prepared.test_rows:
        rows[i] = (Cell("1000000"), Cell("999999"), Cell("holdout_only"), rows[i][3])
    dataset = replace(dataset, rows=tuple(rows))
    result = training.train_candidate(
        dataset, prepared, spec.model_ids[0], tmp_path / "bundle"
    )
    fields = json.loads((Path(result.bundle.directory) / "schema.json").read_text())[
        "fields"
    ]
    assert fields[0]["minimum"] is fields[0]["maximum"] is None
    assert fields[1]["maximum"] == 2
    assert "holdout_only" not in fields[2]["categories"]
    assert "TRAIN_ALL_MISSING:c0" in result.warnings
    predictor = Predictor._from_directory(result.bundle.directory)
    output = predictor.predict(
        {"number": None, "other": 999999, "category": "holdout_only"}
    )
    assert {n["code"] for n in output["warnings"]} == {
        "MISSING_IMPUTED",
        "OUTSIDE_TRAINING_RANGE",
        "UNKNOWN_CATEGORY",
    }


def test_legal_large_vocabulary_exceeds_old_cap_and_exports(tmp_path, monkeypatch):
    source = tmp_path / "large.csv"
    source.write_text(
        "signal,segment,label\n"
        + "".join(
            f"{i % 2},segment_{i:04d}_" + "x" * 3000 + f",class_{i % 2}\n"
            for i in range(1000)
        )
    )
    dataset = load_dataset(source)
    schema = infer_schema(dataset)
    spec = ExperimentSpec(
        1,
        dataset.fingerprint,
        TaskKind.CLASSIFICATION,
        "c2",
        ("c0", "c1"),
        ("classification.logistic",),
    )
    spec = replace(
        spec,
        acknowledgements=tuple(w.code for w in review_warnings(dataset, schema, spec)),
    )
    assert {"HIGH_CARDINALITY:c1", "LONG_TEXT:c1"} <= set(spec.acknowledgements)
    prepared = prepare_run(dataset, schema, spec)
    result = training.train_candidate(
        dataset, prepared, spec.model_ids[0], tmp_path / "bundle"
    )
    resource = Path(result.bundle.directory) / "schema.json"
    assert 2 * 1024**2 < resource.stat().st_size < runtime.MAX_EXPANDED
    records = raw_records(dataset, spec.feature_ids, prepared.test_rows[:2])
    predictor = Predictor._from_directory(result.bundle.directory)
    assert all(
        row["prediction"] in {"class_0", "class_1"}
        for row in predictor.predict_many(records)
    )
    assert export_wheel(
        result.bundle, tmp_path / "exports", "large_model", "1.0.0", records
    ).is_file()
    # The replacement cap is still enforced before parsing or deserializing.
    monkeypatch.setattr(runtime, "MAX_EXPANDED", resource.stat().st_size - 1)
    with pytest.raises(runtime.ArtifactError, match="RESOURCE_LIMIT"):
        Predictor._from_directory(result.bundle.directory)
