"""Try forms run the selected evaluated pipeline through the shared runtime."""

import asyncio
import csv
import hashlib
import os
from pathlib import Path

import pytest
from textual.widgets import Checkbox, Input, Select, Static

from mlforge.application.service import Service
from mlforge.contracts import TaskKind
from mlforge.prediction.runtime import Predictor
from mlforge.tui.app import MLForgeApp
from mlforge.tui.screens.results import Results, SelectedModel
from mlforge.tui.screens.shell import Busy, Help, ResizeGuard
from mlforge.tui.screens.trial import Trial, output_text


async def until(predicate):
    async with asyncio.timeout(60):
        while not predicate():
            await asyncio.sleep(0.01)


async def activate(app, pilot, identifier):
    for _ in range(30):
        if app.focused and app.focused.id == identifier:
            await until(lambda: not app.focused.has_class("-active"))
            await pilot.press("enter")
            return
        await pilot.press("tab")
    raise AssertionError(f"Unreachable action: {identifier}")


def screenshot(app, name):
    if os.environ.get("NO_COLOR"):
        name += "-mono"
    folder = Path(".mlforge-build/p08-try")
    folder.mkdir(parents=True, exist_ok=True)
    app.save_screenshot(name + ".svg", path=str(folder))


async def selected_model(app, pilot, tmp_path, task):
    source = tmp_path / "try.csv"
    with source.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["x", "z", "colour", "flag", "target"])
        for i in range(40):
            target = i * 1.5 if task == TaskKind.REGRESSION else ["no", "yes"][i % 2]
            writer.writerow(
                [i % 11, i // 4 + 0.5 * (i % 3), ["red", "blue"][i % 2], i % 3 == 0]
                + [target]
            )
    service = app.service
    assert await service.load(source)
    service.confirm_schema()
    service.choose_task(task)
    if task.supervised:
        service.choose_target("c4")
    service.choose_features(
        ("c0", "c1", "c2", "c3") if task.supervised else ("c0", "c1")
    )
    if not task.supervised:
        service.choose_option(2 if task == TaskKind.CLUSTERING else 1)
    assert await service.review_configuration()
    service.acknowledge(tuple(w.code for w in service.snapshot.review.warnings))
    assert await service.train(), service.snapshot.failure
    await app.push_screen(Results())
    await pilot.pause()
    await pilot.press("enter")
    await until(lambda: isinstance(app.screen, SelectedModel))


def text(screen, selector):
    return str(screen.query_one(selector, Static).content)


async def predict(app, pilot):
    screen = app.screen
    attempts = screen.attempts
    await activate(app, pilot, "predict")
    await until(lambda: screen.attempts == attempts + 1 and app.screen is screen)
    await pilot.pause()


@pytest.mark.parametrize("task", list(TaskKind))
async def test_try_form_errors_missing_warnings_and_exact_runtime(
    task, tmp_path, monkeypatch
):
    mono = task == TaskKind.REGRESSION  # One task proves markers without color.
    monkeypatch.delenv("NO_COLOR", raising=False)
    if mono:
        monkeypatch.setenv("NO_COLOR", "1")
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await selected_model(app, pilot, tmp_path, task)
        selected = app.service.snapshot.selected
        run_id = app.service.snapshot.run.id
        model = Path(selected.bundle.directory) / "model.skops"
        digest = hashlib.sha256(model.read_bytes()).hexdigest()
        await activate(app, pilot, "try")
        await until(lambda: isinstance(app.screen, Trial))
        await pilot.pause()
        screen = app.screen
        names = [f.name for f in screen.fields]
        assert names == (
            ["x", "z", "colour", "flag"] if task.supervised else ["x", "z"]
        )
        assert "target" not in {str(s.content) for s in screen.query(".field-name")}
        assert app.focused is screen.query_one("#value-0", Input)
        assert "training range 0 to 10" in text(screen, ".try-field .muted")

        # ? is text inside a field; F1 explains it and restores focus.
        await pilot.press("question_mark")
        assert screen.query_one("#value-0", Input).value == "?"
        await pilot.press("f1")
        assert isinstance(app.screen, Help) and "not clipping" in app.screen.body_text
        await pilot.press("escape")
        assert app.focused is screen.query_one("#value-0", Input)
        await pilot.press("backspace")
        # A blank number is a field error from the shared runtime, not a guess.
        await predict(app, pilot)
        assert "Error: Enter a number, or choose Missing." == text(screen, "#error-0")
        assert app.focused is screen.query_one("#value-0", Input)
        assert text(screen, "#result") == ""
        screenshot(app, f"{task}-try-error-80")

        # Missing everywhere uses fitted defaults and says so.
        for index in range(len(names)):
            screen.query_one(f"#missing-{index}", Checkbox).focus()
            await pilot.press("space")
            assert screen.query_one(f"#value-{index}").disabled
            assert str(app.focused._button) == "[x]"  # Readable without color.
        await predict(app, pilot)
        record = dict.fromkeys(names)
        predictor = Predictor._from_directory(selected.bundle.directory)
        run = (
            predictor.transform_many
            if task == TaskKind.REDUCTION
            else predictor.predict_many
        )
        row = app.service.snapshot.prediction.data[0]
        assert row == run([record])[0]
        assert text(screen, "#result") == output_text(task, row)
        assert text(screen, "#error-0") == ""
        assert text(screen, "#warnings").count("Missing input uses") == len(names)

        # Values outside the fitted range are used as entered, with a warning.
        screen.query_one("#missing-0", Checkbox).focus()
        await pilot.press("space")
        screen.query_one("#value-0", Input).focus()
        await pilot.press(*"1000")
        record["x"] = "1000"
        if task.supervised:
            screen.query_one("#missing-2", Checkbox).focus()
            await pilot.press("space")
            screen.query_one("#value-2", Input).focus()
            await pilot.press(*"atlantis")
            record["colour"] = "atlantis"
            screen.query_one("#missing-3", Checkbox).focus()
            await pilot.press("space")
            select = screen.query_one("#value-3", Select)
            select.focus()
            await pilot.press("enter", "down", "enter")
            await until(lambda: select.value is not Select.NULL)
            record["flag"] = select.value
        await predict(app, pilot)
        row = app.service.snapshot.prediction.data[0]
        assert row == run([record])[0]
        warnings = text(screen, "#warnings")
        assert "Warning: x: Input is outside the fitted data range." in warnings
        assert ("colour: Unknown category" in warnings) == task.supervised
        assert text(screen, "#result") == output_text(task, row)
        screenshot(app, f"{task}-try-result-80")
        # A28: 100x30 -> 80x24 -> 79x23 -> 100x30 keeps input, output and focus.
        result = text(screen, "#result")
        for size in [(100, 30), (80, 24), (79, 23), (100, 30)]:
            await pilot.resize_terminal(*size)
            await pilot.pause()
            assert isinstance(app.screen, ResizeGuard) == (size[0] < 80)
        assert app.screen is screen and app.focused is screen.query_one("#predict")
        assert screen.query_one("#value-0", Input).value == "1000"
        assert text(screen, "#result") == result
        screenshot(app, f"{task}-try-result-100")

        assert app.focused is screen.query_one("#predict")
        await pilot.press("b")
        await until(lambda: isinstance(app.screen, SelectedModel))
        state = app.service.snapshot
        assert state.run.id == run_id and state.selected is selected
        assert hashlib.sha256(model.read_bytes()).hexdigest() == digest
        assert not any(isinstance(s, Busy) for s in app.screen_stack)
