"""A shared deterministic row split precedes every learned transformation."""

import json
from dataclasses import replace

import numpy as np
import pytest
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from mlforge import preprocessing
from mlforge.contracts import DomainError, ExperimentSpec, TaskKind
from mlforge.datasets.inference import infer_schema
from mlforge.datasets.records import Cell, Column, TabularDataset
from mlforge.prediction.runtime import normalize_record
from mlforge.preprocessing import (
    input_fields,
    input_matrix,
    matrix_limit,
    prepare_run,
    raw_records,
)


def fixture(task=TaskKind.CLASSIFICATION, n=41):
    dataset = TabularDataset(
        tuple(Column(f"c{i}", name) for i, name in enumerate(("x", "city", "target"))),
        tuple(
            (
                Cell(str(i)),
                Cell("North" if i % 2 else "South"),
                Cell(str(i % 2) if task == TaskKind.CLASSIFICATION else str(i * 2 + 1)),
            )
            for i in range(n)
        ),
        "CSV",
        "fixture",
    )
    schema = infer_schema(dataset)
    spec = ExperimentSpec(
        1, dataset.fingerprint, task, "c2", ("c0", "c1"), ("model_a", "model_b")
    )
    return dataset, schema, spec


@pytest.mark.parametrize("task", [TaskKind.CLASSIFICATION, TaskKind.REGRESSION])
def test_split_shared_repeatable_complete_and_no_fit(task, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Preparation fitted a transform")

    for cls in (SimpleImputer, OneHotEncoder, StandardScaler):
        monkeypatch.setattr(cls, "fit", forbidden)
    dataset, schema, spec = fixture(task)
    original = dataset.rows
    prepared = prepare_run(dataset, schema, spec)
    assert len(prepared.train_rows) == 32 and len(prepared.test_rows) == 9
    assert set(prepared.train_rows).isdisjoint(prepared.test_rows)
    assert set(prepared.train_rows) | set(prepared.test_rows) == set(range(41))
    reordered = prepare_run(
        dataset, schema, replace(spec, model_ids=("model_b", "model_a"))
    )
    repeated = prepare_run(dataset, schema, spec)
    assert prepared.train_rows == reordered.train_rows == repeated.train_rows
    assert prepared.test_rows == reordered.test_rows == repeated.test_rows
    if task == TaskKind.CLASSIFICATION:
        assert {dataset.rows[i][2].raw_text for i in prepared.train_rows} == {"0", "1"}
        assert {dataset.rows[i][2].raw_text for i in prepared.test_rows} == {"0", "1"}
    policy = json.loads(prepared.policy_json)
    assert [f["name"] for f in policy["fields"]] == ["x", "city"]
    assert (
        "median" in policy["numeric_missing"]
        and "Random splits" in policy["split_caution"]
    )
    assert json.loads(prepared.environment_json)["python_minor"] in {"3.12", "3.13"}
    assert dataset.rows is original


def test_holdout_validation_does_not_learn_ranges_or_vocabulary():
    dataset, schema, spec = fixture()
    first = prepare_run(dataset, schema, spec)
    rows = list(dataset.rows)
    for i in first.test_rows:
        rows[i] = (Cell(str(10000 + i)), Cell("test-only category"), rows[i][2])
    changed = replace(dataset, rows=tuple(rows))
    after = prepare_run(changed, infer_schema(changed), spec)
    assert after.train_rows == first.train_rows and after.test_rows == first.test_rows
    assert after.policy_json == first.policy_json  # no fitted ranges or categories
    assert "test-only category" not in after.policy_json


def test_canonical_input_normalizes_identically_to_prediction():
    dataset, schema, spec = fixture()
    rows = list(dataset.rows)
    rows[0] = (Cell(""), Cell(""), rows[0][2])
    dataset = replace(dataset, rows=tuple(rows))
    schema = infer_schema(dataset)
    fields = input_fields(dataset, schema, spec.feature_ids)
    records = raw_records(dataset, spec.feature_ids, (0, 1))
    assert records[0] == {"x": None, "city": None}
    matrix = input_matrix(dataset, schema, spec.feature_ids, (0, 1))
    assert np.isnan(matrix[0, 0]) and np.isnan(matrix[0, 1])
    assert list(matrix[1]) == normalize_record(records[1], fields)[0]
    assert all("target" not in row for row in records)


@pytest.mark.parametrize(
    "task,option", [(TaskKind.CLUSTERING, 3), (TaskKind.REDUCTION, 1)]
)
def test_unsupervised_uses_all_rows_without_target(task, option):
    dataset, schema, _ = fixture(TaskKind.REGRESSION)
    spec = ExperimentSpec(1, "fixture", task, None, ("c0", "c2"), ("model",), option)
    prepared = prepare_run(dataset, schema, spec)
    assert prepared.train_rows == tuple(range(41)) and prepared.test_rows == ()
    assert (
        json.loads(prepared.policy_json)["scope"]
        == "Exploration on this dataset; no test split"
    )


def test_bounds_before_allocation_and_stale_inputs(monkeypatch):
    assert matrix_limit(20000, [{"type": "Category"}] * 16) == 512
    with pytest.raises(DomainError, match="512"):
        matrix_limit(20, [{"type": "Category"}] * 17)
    with pytest.raises(DomainError, match="128 MiB"):
        matrix_limit(40000, [{"type": "Category"}] * 16)
    dataset, schema, spec = fixture()
    with pytest.raises(DomainError, match="no longer match"):
        prepare_run(dataset, schema, replace(spec, dataset_fingerprint="old"))
    with pytest.raises(DomainError, match="no longer match"):
        prepare_run(dataset, replace(schema, columns=schema.columns[::-1]), spec)
    monkeypatch.setattr(preprocessing, "MAX_MATRIX_BYTES", 1)

    def forbidden(*args, **kwargs):
        raise AssertionError("Allocated before checking bounds")

    monkeypatch.setattr(np, "asarray", forbidden)
    with pytest.raises(DomainError, match="128 MiB"):
        input_matrix(dataset, schema, spec.feature_ids, (0, 1))


def test_impossible_or_corrupt_split_is_not_silently_repaired(monkeypatch):
    dataset, schema, spec = fixture()

    def impossible(*args, **kwargs):
        raise ValueError("private data must not be echoed")

    monkeypatch.setattr(preprocessing, "train_test_split", impossible)
    with pytest.raises(DomainError) as caught:
        prepare_run(dataset, schema, spec)
    assert caught.value.code == "SPLIT" and "private" not in str(caught.value)
    monkeypatch.setattr(
        preprocessing, "train_test_split", lambda *args, **kwargs: ([0, 1], [1, 2])
    )
    with pytest.raises(DomainError, match="exactly once"):
        prepare_run(dataset, schema, spec)
