"""Real evaluated results, keyboard journeys and terminal diagnostics."""

import asyncio
import csv
import hashlib
import json
from importlib.resources import files
from pathlib import Path

import numpy as np
import pytest
from sklearn.model_selection import train_test_split
from textual.widgets import DataTable, Static

from mlforge.application.service import Service
from mlforge.contracts import TaskKind
from mlforge.tui.app import MLForgeApp
from mlforge.tui.screens.configuration import (
    Features,
    Goal,
    Models,
    Preprocessing,
    Target,
)
from mlforge.tui.screens.preview import Preview
from mlforge.tui.screens.results import Inspection, Results, SelectedModel, number
from mlforge.tui.screens.shell import Confirm, Help, ResizeGuard


async def until(predicate):
    async with asyncio.timeout(60):
        while not predicate():
            await asyncio.sleep(0.01)


async def activate(app, pilot, identifier):
    for _ in range(20):
        if app.focused and app.focused.id == identifier:
            await pilot.press("enter")
            return
        await pilot.press("tab")
    raise AssertionError(f"Unreachable action: {identifier}")


def screenshot(app, name):
    folder = Path(".mlforge-build/p07-results")
    folder.mkdir(parents=True, exist_ok=True)
    app.save_screenshot(name + ".svg", path=str(folder))


@pytest.mark.parametrize("task", list(TaskKind))
async def test_complete_keyboard_journey_and_exact_inspection(task, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    app = MLForgeApp(Service())
    index = next(i for i, e in enumerate(app.service.examples) if e.task == task)
    source = files("mlforge").joinpath("examples", app.service.examples[index].filename)
    original = source.read_bytes()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter", "down", "down", "enter")
        await pilot.press(*(["down"] * index), "enter")
        await until(lambda: isinstance(app.screen, Preview))
        await activate(app, pilot, "correct")
        await until(lambda: isinstance(app.screen, Goal))
        await pilot.pause()
        await pilot.press(*(["down"] * list(TaskKind).index(task)), "enter")
        await until(
            lambda: isinstance(app.screen, Target if task.supervised else Features)
        )
        await pilot.pause()
        if task.supervised:
            assert app.service.snapshot.configuration.target_id is None
            await pilot.press("enter")
            await until(lambda: isinstance(app.screen, Features))
        else:
            assert not any(isinstance(s, Target) for s in app.screen_stack)
        await activate(app, pilot, "continue")
        await until(lambda: isinstance(app.screen, Preprocessing))
        await activate(app, pilot, "continue")
        await until(lambda: isinstance(app.screen, Models))
        await activate(app, pilot, "train")
        await until(lambda: isinstance(app.screen, Results))
        await pilot.pause()
        result_screen = app.screen
        state = app.service.snapshot
        run = state.run
        configuration = state.configuration
        accepted = {c.model_id: c for c in state.results}
        hashes = {
            key: hashlib.sha256(
                (Path(c.bundle.directory) / "model.skops").read_bytes()
            ).hexdigest()
            for key, c in accepted.items()
        }
        table = result_screen.query_one("#results", DataTable)
        assert table.max_scroll_x == 0
        assert result_screen.shown == tuple(
            c.model_id for c in app.service.ranked_results
        )
        assert app.service.snapshot.selected is None
        for c in state.results:
            for metric in app.service.primary_metrics:
                value = next(m for m in c.metrics if m.key == metric.key)
                assert str(table.get_cell(c.model_id, metric.key)).strip() == number(
                    value.value
                )
        recommendation = str(result_screen.query_one("#recommendation", Static).content)
        assert (
            "Recommended based on test performance" in recommendation
        ) == task.supervised
        if not task.supervised:
            assert recommendation == ""
            assert "no test split" in str(
                result_screen.query_one("#provenance", Static).content
            )
        # Move into metric cells using only the keyboard; help preserves cursor/focus.
        await pilot.press("right", "right", "question_mark")
        assert isinstance(app.screen, Help)
        assert (
            "independent future validation" in app.screen.body_text
            if task.supervised
            else "predictive accuracy" in app.screen.body_text
            or "predictive performance" in app.screen.body_text
        )
        screenshot(app, f"{task}-metric-help-80")
        await pilot.press("escape")
        assert app.focused is table and table.cursor_column == 3
        for width, height in [(80, 24), (100, 30), (140, 40)]:
            await pilot.resize_terminal(width, height)
            await pilot.pause()
            assert app.screen is result_screen and app.focused is table
            screenshot(app, f"{task}-results-{width}")
        await pilot.resize_terminal(79, 23)
        await pilot.pause()
        assert isinstance(app.screen, ResizeGuard)
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        assert app.focused is table and table.cursor_column == 3
        await pilot.press("enter")
        assert isinstance(app.screen, SelectedModel)
        selected = app.service.snapshot.selected
        assert selected is accepted[result_screen.shown[0]]
        for width, height in [(80, 24), (100, 30), (140, 40)]:
            await pilot.resize_terminal(width, height)
            await pilot.pause()
            screenshot(app, f"{task}-selected-{width}")
        await activate(app, pilot, "inspect")
        assert isinstance(app.screen, Inspection)
        inspection = app.screen
        diagnostics = json.loads(selected.diagnostics_json)
        if task == TaskKind.CLASSIFICATION:
            assert inspection.tables["confusion"][0][1:] == diagnostics["labels"]
            assert inspection.tables["confusion"][1][0][1:] == tuple(
                diagnostics["confusion_matrix"][0]
            )
        elif task == TaskKind.REGRESSION:
            assert (
                "Residual count",
                diagnostics["residuals"]["count"],
            ) in inspection.tables["residuals"][1]
        elif task == TaskKind.CLUSTERING:
            assert inspection.tables["centers"][1][0][2:] == tuple(
                diagnostics["centers"][0]
            )
        else:
            assert inspection.tables["components"][1][0] == tuple(
                diagnostics["per_component"][0][k]
                for k in ("component", "variance", "variance_ratio")
            )
        for width, height in [(80, 24), (100, 30), (140, 40)]:
            await pilot.resize_terminal(width, height)
            await pilot.pause()
            screenshot(app, f"{task}-inspect-{width}")
        focused = app.focused
        await pilot.press("question_mark")
        assert isinstance(app.screen, Help)
        await pilot.press("escape")
        assert app.focused is focused and app.service.snapshot.selected is selected
        await pilot.press("escape", "escape")
        assert app.screen is result_screen
        assert "[x]" in str(table.get_cell(selected.model_id, "marker"))
        assert app.service.snapshot.run is run
        assert hashes == {
            key: hashlib.sha256(
                (Path(c.bundle.directory) / "model.skops").read_bytes()
            ).hexdigest()
            for key, c in accepted.items()
        }
        await pilot.press("escape")
        assert isinstance(app.screen, Models)
        assert app.service.snapshot.configuration == configuration
        assert app.service.snapshot.selected is selected
        await pilot.press("ctrl+q")
        assert isinstance(app.screen, Confirm) and app.focused.id == "keep"
        assert "not saved" in app.screen.body_text
        await pilot.press("escape")
        if task.supervised:
            choices = app.screen.query_one("#choices")
            choices.focus()
            await pilot.press("space")
            assert isinstance(app.screen, Confirm) and app.focused.id == "keep"
            await pilot.press("enter")
            assert app.service.snapshot.selected is selected
            await pilot.press("space", "tab", "enter")
            assert app.service.snapshot.selected is None
            assert not app.service.snapshot.results
    assert source.read_bytes() == original
    assert not app.service._coordinator.root.exists()


async def evaluated_rows(app, tmp_path, rows, task):
    source = tmp_path / "edge.csv"
    with source.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["x", "z", "target"])
        writer.writerows(rows)
    service = app.service
    assert await service.load(source)
    service.confirm_schema()
    service.choose_task(task)
    if task.supervised:
        service.choose_target("c2")
    service.choose_features(("c0", "c1"))
    if task == TaskKind.CLUSTERING:
        service.choose_option(2)
    assert await service.review_configuration()
    service.acknowledge(tuple(w.code for w in service.snapshot.review.warnings))
    assert await service.train(), service.snapshot.failure
    await app.push_screen(Results())


@pytest.mark.parametrize("constant", [False, True])
async def test_real_regression_negative_or_undefined_r2(tmp_path, constant):
    _, test = train_test_split(np.arange(30), test_size=6, random_state=42)
    rows = [
        (
            i if i in test else None,
            i % 7,
            200 + (0 if constant else i) if i in test else i % 3,
        )
        for i in range(30)
    ]
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await evaluated_rows(app, tmp_path, rows, TaskKind.REGRESSION)
        await pilot.pause()
        table = app.screen.query_one("#results", DataTable)
        ranked = app.service.ranked_results
        assert all("TRAIN_ALL_MISSING:c0" in c.warnings for c in ranked)
        assert "imputation used zero" in str(
            app.screen.query_one("#row-detail", Static).content
        )
        maes = [next(m.value for m in c.metrics if m.key == "mae") for c in ranked]
        assert maes == sorted(maes)
        for candidate in ranked:
            metric = next(m for m in candidate.metrics if m.key == "r2")
            assert metric.value is None if constant else metric.value < 0
            assert str(table.get_cell(candidate.model_id, "r2")).strip() == (
                "N/A" if constant else number(metric.value)
            )
        table.move_cursor(column=4)
        await pilot.press("question_mark")
        assert (
            "undefined" in app.screen.body_text
            if constant
            else "Negative values" in app.screen.body_text
        )
        await pilot.press("escape", "enter")
        await activate(app, pilot, "inspect")
        assert "residuals" in app.screen.tables
        screenshot(app, f"regression-{'undefined' if constant else 'negative'}-80")


async def test_real_sampled_silhouette_na(tmp_path):
    included = np.random.RandomState(42).choice(2001, 2000, replace=False)
    omitted = next(i for i in range(2001) if i not in included)
    rows = [
        (100 if i == omitted else 0, 1 if i == omitted else 0, i % 2)
        for i in range(2001)
    ]
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await evaluated_rows(app, tmp_path, rows, TaskKind.CLUSTERING)
        await pilot.pause()
        candidate = app.service.ranked_results[0]
        metric = next(m for m in candidate.metrics if m.key == "silhouette")
        assert metric.value is None and metric.reason
        assert str(app.screen.query_one("#recommendation", Static).content) == ""
        assert "N/A:" in str(app.screen.query_one("#row-detail", Static).content)
        await pilot.press("enter")
        await activate(app, pilot, "inspect")
        assert json.loads(candidate.diagnostics_json)["silhouette_sampled"]
        screenshot(app, "silhouette-na-inspect-80")


async def test_old_result_screen_cannot_select_after_configuration_edit(tmp_path):
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await evaluated_rows(
            app,
            tmp_path,
            [(i, i % 5, i % 2) for i in range(30)],
            TaskKind.CLASSIFICATION,
        )
        await pilot.pause()
        owner = app.screen
        app.service.choose_features(("c0",), discard=True)
        await pilot.press("enter")
        assert app.screen is owner and app.service.snapshot.selected is None
        assert "current model" in str(owner.query_one("#error", Static).content)
        # A new completed run with the same model IDs must not revive this screen.
        assert await app.service.review_configuration()
        app.service.acknowledge(
            tuple(w.code for w in app.service.snapshot.review.warnings)
        )
        assert await app.service.train()
        await pilot.press("enter")
        assert app.screen is owner and app.service.snapshot.selected is None


async def test_one_model_monochrome_selection_and_literal_labels(tmp_path, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    app = MLForgeApp(Service())
    rows = [(i, i % 7, "[red]世界\x1b[31m" if i % 2 else "ordinary") for i in range(30)]
    async with app.run_test(size=(80, 24)) as pilot:
        # Train a real run, then explicitly choose a single candidate for a new run.
        await evaluated_rows(app, tmp_path, rows, TaskKind.CLASSIFICATION)
        app.service.choose_models(("classification.logistic",), discard=True)
        assert await app.service.train()
        await app.switch_screen(Results())
        await pilot.pause()
        owner = app.screen
        table = owner.query_one("#results", DataTable)
        assert "Only completed model" in str(
            owner.query_one("#recommendation", Static).content
        )
        assert "Recommended" not in str(
            owner.query_one("#recommendation", Static).content
        )
        await pilot.press("enter")
        selected = app.service.snapshot.selected
        screenshot(app, "classification-mono-selected-80")
        await activate(app, pilot, "inspect")
        confusion = app.screen.query_one("#confusion", DataTable)
        assert any(
            "[red]世界" in str(confusion.get_cell_at((i, 0)))
            for i in range(confusion.row_count)
        )
        assert all(
            "\x1b" not in str(confusion.get_cell_at((i, 0)))
            for i in range(confusion.row_count)
        )
        screenshot(app, "classification-mono-inspect-80")
        await pilot.press("escape", "escape")
        assert app.screen is owner
        await activate(app, pilot, "select-model")
        await pilot.press("escape")
        assert app.service.snapshot.selected is selected
        table.focus()
        for width, height in [(80, 24), (100, 30), (140, 40)]:
            await pilot.resize_terminal(width, height)
            await pilot.pause()
            assert "[x]" in str(table.get_cell(selected.model_id, "marker"))
            screenshot(app, f"classification-mono-results-{width}")
