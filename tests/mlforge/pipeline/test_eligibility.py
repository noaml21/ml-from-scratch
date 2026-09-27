"""Eligibility boundaries and explicit review cannot be bypassed by selection."""

from dataclasses import replace

import pytest

from mlforge.contracts import DomainError, ExperimentSpec
from mlforge.contracts import TaskKind as K
from mlforge.datasets.importers import load_dataset
from mlforge.datasets.inference import infer_schema
from mlforge.datasets.records import Cell, Column, TabularDataset
from mlforge.datasets.records import ColumnType as T
from mlforge.datasets.validation import change_type
from mlforge.tasks import (
    feature_choices,
    goal_reason,
    option_bounds,
    review_warnings,
    target_choices,
    target_reason,
    target_values,
    validate_selection,
)


def dataset(target, *, names=("measurement", "target")):
    return TabularDataset(
        tuple(Column(f"c{i}", n) for i, n in enumerate(names)),
        tuple(
            (Cell(str(i)), Cell(None if y is None else str(y)))
            for i, y in enumerate(target)
        ),
        "CSV",
        "fixture",
    )


def experiment(task=K.CLASSIFICATION, *, target="c1", features=("c0",), option=None):
    return ExperimentSpec(1, "fixture", task, target, features, ("candidate",), option)


@pytest.mark.parametrize(
    "target,task,valid",
    [
        (["a"] * 10 + ["b"] * 10, K.CLASSIFICATION, True),
        (["a"] * 9 + ["b"] * 10, K.CLASSIFICATION, False),
        (["a"] * 16 + ["b"] * 4, K.CLASSIFICATION, False),
        ([str(i) for i in range(21)] * 5, K.CLASSIFICATION, False),
        (["a"] * 20, K.CLASSIFICATION, False),
        (["a"] * 9 + ["b"] * 10 + [None], K.CLASSIFICATION, False),
        ([1, 2] * 10, K.CLASSIFICATION, True),
        ([1.5, 2.5] * 10, K.CLASSIFICATION, False),
        ([1.5, 2.5] * 10, K.REGRESSION, True),
        (["a", "b"] * 10, K.REGRESSION, False),
        ([1] * 20, K.REGRESSION, False),
        ([1] * 19 + [None], K.REGRESSION, False),
    ],
)
def test_target_boundaries(target, task, valid):
    data = dataset(target)
    schema = infer_schema(data)
    assert (target_reason(data, schema, "c1", task) is None) == valid
    all_choices = {
        c.column_id: c for c in target_choices(data, schema, task, show_all=True)
    }
    assert all_choices["c1"].eligible == valid


def test_target_types_and_labels_are_explicit():
    data = dataset([1.5, 2.5] * 10)
    schema = infer_schema(data)
    with pytest.raises(DomainError):
        target_values(data, schema, "c1", K.CLASSIFICATION)
    schema = change_type(data, schema, "c1", T.CATEGORY)
    assert target_reason(data, schema, "c1", K.CLASSIFICATION) is None
    assert target_values(data, schema, "c1", K.CLASSIFICATION)[:2] == ("1.5", "2.5")
    data = dataset(["1.0", "2e0"] * 10)
    schema = infer_schema(data)
    assert target_values(data, schema, "c1", K.CLASSIFICATION)[:2] == ("1", "2")
    data = dataset(["TRUE", "false"] * 10)
    schema = infer_schema(data)
    assert target_values(data, schema, "c1", K.CLASSIFICATION)[:2] == ("true", "false")
    assert all(not c.default for c in target_choices(data, schema, K.CLASSIFICATION))


def test_features_defaults_exclusions_and_override():
    names = ("id", "date", "number", "flag", "category", "constant", "empty", "long")
    data = TabularDataset(
        tuple(Column(f"c{i}", n) for i, n in enumerate(names)),
        tuple(
            tuple(
                Cell(v)
                for v in (
                    str(i),
                    f"2024-01-{i % 28 + 1:02d}",
                    str(i % 7),
                    "true" if i % 2 else "false",
                    "a" if i % 2 else "b",
                    "fixed",
                    "",
                    f"{i}" + ("x" * 201),
                )
            )
            for i in range(30)
        ),
        "CSV",
        "fixture",
    )
    schema = infer_schema(data)
    choices = feature_choices(data, schema, K.CLASSIFICATION, "c4")
    assert [c.default for c in choices] == [
        False,
        False,
        True,
        True,
        False,
        False,
        False,
        False,
    ]
    assert choices[7].eligible and not choices[7].default
    assert all(c.reason for c in choices if not c.eligible)
    unsupervised = feature_choices(data, schema, K.CLUSTERING)
    assert [c.column_id for c in unsupervised if c.eligible] == ["c2"]
    overridden = change_type(data, schema, "c0", T.NUMBER)
    assert feature_choices(data, overridden, K.CLUSTERING)[0].eligible


def test_goal_and_option_boundaries():
    for rows, task, valid in [
        (9, K.CLUSTERING, False),
        (10, K.CLUSTERING, True),
        (2, K.REDUCTION, False),
        (3, K.REDUCTION, True),
    ]:
        data = dataset(list(range(rows)))
        schema = infer_schema(data)
        assert (goal_reason(data, schema, task) is None) == valid
    assert option_bounds(K.REDUCTION, 20, 2) == (1, 1, 1)
    assert option_bounds(K.REDUCTION, 20, 4) == (1, 3, 2)
    assert option_bounds(K.CLUSTERING, 20, 2) == (2, 10, 3)
    assert option_bounds(K.CLASSIFICATION, 20, 2) is None
    data = dataset(list(range(20)))
    schema = infer_schema(data)
    for option in (1, 11, True, None):
        with pytest.raises(DomainError):
            validate_selection(
                data,
                schema,
                experiment(
                    K.CLUSTERING, target=None, features=("c0", "c1"), option=option
                ),
            )
    assert (
        validate_selection(
            data,
            schema,
            experiment(K.CLUSTERING, target=None, features=("c0", "c1"), option=3),
        )
        == ()
    )
    with pytest.raises(DomainError):
        validate_selection(
            data,
            schema,
            experiment(K.REDUCTION, target=None, features=("c0",), option=1),
        )


def test_warning_acknowledgements_and_no_silent_deduplication():
    data = dataset([str(i % 2) for i in range(20)], names=("prediction", "target"))
    # Deliberately identical selected feature rows and target values.
    data = replace(data, rows=tuple((row[1], row[1]) for row in data.rows))
    original = data.rows
    schema = infer_schema(data)
    spec = experiment()
    warnings = review_warnings(data, schema, spec)
    assert {w.code for w in warnings} == {
        "EQUAL_TARGET:c0",
        "LEAKAGE_NAME:c0",
        "DUPLICATE_ROWS",
    }
    with pytest.raises(DomainError) as caught:
        validate_selection(data, schema, spec)
    assert caught.value.code == "ACKNOWLEDGEMENT"
    accepted = replace(spec, acknowledgements=tuple(w.code for w in warnings))
    assert validate_selection(data, schema, accepted) == warnings
    assert data.rows is original


def test_unknown_and_excluded_columns_cannot_bypass_selection():
    data = dataset(["a", "b"] * 10)
    schema = infer_schema(data)
    with pytest.raises(DomainError):
        validate_selection(data, schema, experiment(features=("absent",)))
    with pytest.raises(DomainError):
        validate_selection(data, schema, experiment(target="absent"))
    with pytest.raises(ValueError):
        experiment(features=("c1",))


def test_high_cardinality_needs_review_and_long_targets_stay_inspectable():
    data = dataset(["a", "b"] * 10)
    data = replace(
        data,
        rows=tuple((Cell(f"category_{i}"), row[1]) for i, row in enumerate(data.rows)),
    )
    schema = infer_schema(data)
    choices = feature_choices(data, schema, K.CLASSIFICATION, "c1")
    assert choices[0].eligible and not choices[0].default
    warnings = review_warnings(data, schema, experiment())
    assert {w.code for w in warnings} == {"HIGH_CARDINALITY:c0"}
    with pytest.raises(DomainError, match="Review"):
        validate_selection(data, schema, experiment())
    long = dataset(["a" * 201, "b" * 201] * 10)
    schema = infer_schema(long)
    assert "c1" not in {
        c.column_id for c in target_choices(long, schema, K.CLASSIFICATION)
    }
    assert next(
        c
        for c in target_choices(long, schema, K.CLASSIFICATION, show_all=True)
        if c.column_id == "c1"
    ).eligible


def test_mixed_target_requires_acknowledgement_or_explicit_override(tmp_path):
    path = tmp_path / "mixed.jsonl"
    path.write_text(
        "".join(
            f'{{"x":{i},"target":' + ("true" if i % 2 else '"class_b"') + "}\n"
            for i in range(20)
        )
    )
    data = load_dataset(path)
    schema = infer_schema(data)
    assert {w.code for w in review_warnings(data, schema, experiment())} == {
        "MIXED_KINDS:c1"
    }
    with pytest.raises(DomainError, match="Review"):
        validate_selection(data, schema, experiment())
    changed = change_type(data, schema, "c1", T.CATEGORY)
    assert validate_selection(data, changed, experiment()) == ()
