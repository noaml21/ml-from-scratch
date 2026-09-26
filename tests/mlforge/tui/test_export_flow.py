"""Export form publishes the selected evaluated bundle and guides installation."""

import asyncio
import csv
import hashlib
import os
import zipfile
from pathlib import Path

import pytest
from textual.widgets import Input, Static, TextArea

from mlforge.application.service import Service
from mlforge.contracts import TaskKind
from mlforge.tui.app import MLForgeApp
from mlforge.tui.screens.export import ExportDone, ExportPackage
from mlforge.tui.screens.results import Results, SelectedModel
from mlforge.tui.screens.shell import Busy, Confirm, Help


async def until(predicate):
    async with asyncio.timeout(120):
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
    folder = Path(__file__).resolve().parents[3] / ".mlforge-build/p08-export"
    folder.mkdir(parents=True, exist_ok=True)
    app.save_screenshot(name + ".svg", path=str(folder))


async def selected_model(app, pilot, tmp_path, task):
    source = tmp_path / "private-rows.csv"
    with source.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["x", "z", "colour", "target"])
        for i in range(40):
            writer.writerow(
                [i % 11, i // 4 + 0.5 * (i % 3), ["red", "blue"][i % 2]]
                + [["no", "yes"][i % 2]]
            )
    service = app.service
    assert await service.load(source)
    service.confirm_schema()
    service.choose_task(task)
    if task.supervised:
        service.choose_target("c3")
    service.choose_features(("c0", "c1", "c2") if task.supervised else ("c0", "c1"))
    if not task.supervised:
        service.choose_option(1)
    assert await service.review_configuration()
    service.acknowledge(tuple(w.code for w in service.snapshot.review.warnings))
    assert await service.train(), service.snapshot.failure
    await app.push_screen(Results())
    await pilot.pause()
    await pilot.press("enter")
    await until(lambda: isinstance(app.screen, SelectedModel))


def text(screen, selector):
    return str(screen.query_one(selector, Static).content)


async def fill(app, pilot, identifier, value):
    field = app.screen.query_one(f"#{identifier}", Input)
    field.focus()
    field.value = ""
    await pilot.press(*value)


async def build(app, pilot):
    screen = app.screen
    attempts = screen.attempts
    await activate(app, pilot, "build")
    await until(lambda: screen.attempts == attempts + 1)
    await pilot.pause()
    assert not any(isinstance(s, Busy) for s in app.screen_stack)


@pytest.mark.parametrize("task", [TaskKind.CLASSIFICATION, TaskKind.REDUCTION])
async def test_export_errors_retry_success_and_usage(task, tmp_path, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    if task == TaskKind.REDUCTION:  # One flow proves markers without color.
        monkeypatch.setenv("NO_COLOR", "1")
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await selected_model(app, pilot, tmp_path, task)
        selected = app.service.snapshot.selected
        model = Path(selected.bundle.directory) / "model.skops"
        digest = hashlib.sha256(model.read_bytes()).hexdigest()
        await activate(app, pilot, "export")
        await until(lambda: isinstance(app.screen, ExportPackage))
        await pilot.pause()
        screen = app.screen
        destination = screen.query_one("#destination", Input)
        assert destination.value == str(work / "exports")
        assert app.focused is destination
        assert screen.query_one("#module", Input).value == "my_model"
        assert screen.query_one("#version", Input).value == "1.0.0"
        notes = " ".join(str(s.content) for s in screen.query(".muted"))
        assert "never your original rows" in notes and "Linux x86_64" in notes
        await pilot.press("f1")
        assert isinstance(app.screen, Help) and "never replaced" in app.screen.body_text
        await pilot.press("escape")
        assert app.focused is destination
        screenshot(app, f"{task}-export-form-80")

        # Syntax and reserved names are field errors; nothing is created.
        await fill(app, pilot, "module", "My-Model")
        await build(app, pilot)
        assert text(screen, "#error-module").startswith("Error: Choose a valid")
        assert app.focused is screen.query_one("#module", Input)
        await fill(app, pilot, "module", "numpy")
        await build(app, pilot)
        assert text(screen, "#error-module").startswith("Error: Choose a valid")
        await fill(app, pilot, "module", "churn_model")
        await fill(app, pilot, "version", "1.02")
        await build(app, pilot)
        assert text(screen, "#error-version").startswith("Error: Use a three-part")
        assert text(screen, "#error-module") == ""
        await fill(app, pilot, "version", "1.0.0")
        assert not (work / "exports").exists() or not any((work / "exports").iterdir())

        # An unwritable folder fails safely and keeps the selection for retry.
        locked = tmp_path / "locked"
        locked.mkdir(mode=0o500)
        await fill(app, pilot, "destination", str(locked / "nested"))
        await build(app, pilot)
        assert "Choose a writable destination" in text(screen, "#error-destination")
        assert app.focused is destination
        assert app.service.snapshot.selected is selected
        screenshot(app, f"{task}-export-error-80")

        # An existing wheel is never replaced.
        wheel = work / "exports" / "churn_model-1.0.0-py3-none-any.whl"
        wheel.parent.mkdir(exist_ok=True)
        wheel.write_bytes(b"user file")
        await fill(app, pilot, "destination", "exports")
        await build(app, pilot)
        assert "already exists" in text(screen, "#error-destination")
        assert wheel.read_bytes() == b"user file"
        wheel.unlink()

        await build(app, pilot)
        assert isinstance(app.screen, ExportDone), text(screen, "#error")
        assert app.service.snapshot.exported_path == str(wheel)
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            content = b"".join(archive.read(n) for n in names)
        assert "churn_model/model.skops" in names
        assert b"private-rows" not in content and str(tmp_path).encode() not in content
        usage = app.screen.query_one("#usage", TextArea).text
        assert f"Created: {wheel}" in usage
        assert f"python -m pip install \\\n    {wheel}" in usage
        assert "from churn_model import Predictor" in usage
        call = "transform" if task == TaskKind.REDUCTION else "predict"
        assert f"result = model.{call}({{'x': 0.0, 'z':" in usage
        assert hashlib.sha256(model.read_bytes()).hexdigest() == digest
        assert app.service.snapshot.selected is selected
        assert not [p for p in wheel.parent.iterdir() if p.name.startswith(".mlforge")]
        screenshot(app, f"{task}-export-done-80")
        await pilot.resize_terminal(100, 30)
        await pilot.pause()
        screenshot(app, f"{task}-export-done-100")

        await activate(app, pilot, "results")
        await until(lambda: isinstance(app.screen, Results))
        # Exported sessions quit without the unexported-results warning.
        await pilot.press("q")
        await pilot.pause()
        assert not any(isinstance(s, Confirm) for s in app.screen_stack)
    os.chmod(locked, 0o700)
