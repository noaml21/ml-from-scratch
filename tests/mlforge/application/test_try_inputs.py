"""Try inputs come from the selected fitted schema; runtime errors identify fields."""

import math

import pytest

from mlforge.contracts import DomainError, TaskKind


def training_values(app, name):
    state = app.snapshot
    index = next(i for i, c in enumerate(state.dataset.columns) if c.name == name)
    cells = (state.dataset.rows[row][index] for row in state.prepared.train_rows)
    return [float(cell.raw_text) for cell in cells if not cell.missing]


async def test_prediction_fields_follow_selected_fitted_schema(trained_app):
    app = trained_app
    state = app.snapshot
    fields = await app.prediction_fields()
    by_id = {c.id: c.name for c in state.dataset.columns}
    assert [f.name for f in fields] == [
        by_id[i] for i in state.run.experiment.feature_ids
    ]
    number = {f.name: f for f in fields}["x"]
    assert number.kind == "Number" and number.categories == ()
    observed = training_values(app, "x")
    assert (number.minimum, number.maximum) == (min(observed), max(observed))
    if state.run.experiment.task.supervised:
        city, flag = ({f.name: f for f in fields}[name] for name in ("city", "flag"))
        assert city.kind == "Category" and set(city.categories) == {
            "north",
            "south",
            "m:",
        }
        assert flag.kind == "Boolean" and set(flag.categories) == {"false", "true"}
        assert city.minimum is None and city.maximum is None
    app.choose_models((), discard=True)
    with pytest.raises(DomainError):
        await app.prediction_fields()


async def test_try_errors_warnings_and_task_outputs(trained_app):
    app = trained_app
    task = app.snapshot.run.experiment.task
    candidate = app.snapshot.selected
    fields = await app.prediction_fields()
    record = {f.name: None for f in fields}

    for field, value, fragment in [
        ("x", "", "choose Missing"),
        ("x", "1e400", "supported range"),
        ("x", "twelve", "choose Missing"),
    ] + ([("flag", "maybe", "true or false")] if task.supervised else []):
        assert await app.predict([{**record, field: value}]) is None
        failure = app.snapshot.failure
        assert (failure.code, failure.row, failure.column) == (
            "PREDICT_INPUT",
            0,
            field,
        )
        assert fragment in failure.message
        assert not value or value not in failure.message + failure.action
        assert app.snapshot.selected is candidate and app.snapshot.prediction is None

    beyond = {**record, "x": "1000", "z": "2.5"}
    if task.supervised:
        beyond.update(city="atlantis", flag="true")
    result = (await app.predict([record, beyond])).data
    assert app.snapshot.failure is None
    missing = {w["code"] for w in result[0]["warnings"]}
    assert missing == {"MISSING_IMPUTED"}
    codes = {(w["code"], w["field"]) for w in result[1]["warnings"]}
    assert ("OUTSIDE_TRAINING_RANGE", "x") in codes
    assert (("UNKNOWN_CATEGORY", "city") in codes) == task.supervised
    for row in result:
        if task == TaskKind.CLASSIFICATION:
            assert row["prediction"] in {"no", "yes"}
        elif task == TaskKind.REGRESSION:
            assert math.isfinite(row["prediction"])
        elif task == TaskKind.CLUSTERING:
            assert 0 <= row["cluster"] < app.snapshot.run.experiment.option
        else:
            assert len(row["components"]) == app.snapshot.run.experiment.option
