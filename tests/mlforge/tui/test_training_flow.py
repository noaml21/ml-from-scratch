"""Training views use real preparation/estimator children and controlled faults."""

import asyncio
import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from textual.widgets import DataTable, Static

from mlforge.application.service import Service
from mlforge.application.state import Activity
from mlforge.contracts import CandidateStatus, TaskKind
from mlforge.execution.protocol import (
    EventKind,
    Operation,
    Request,
    RunEvent,
    decode,
    read_owned,
)
from mlforge.tui.app import MLForgeApp
from mlforge.tui.screens.configuration import Models
from mlforge.tui.screens.results import Results, SelectedModel
from mlforge.tui.screens.shell import Confirm, Help, ResizeGuard
from mlforge.tui.screens.training import Training


async def until(predicate):
    async with asyncio.timeout(45):
        while not predicate():
            await asyncio.sleep(0.01)


async def configure(app, pilot, task=TaskKind.CLASSIFICATION):
    example = next(e for e in app.service.examples if e.task == task)
    assert await app.service.load_example(example.filename)
    app.service.confirm_schema()
    app.service.choose_task(task)
    assert await app.service.review_configuration()
    if task.supervised:
        app.service.choose_target(
            next(c.column_id for c in app.service.snapshot.review.targets if c.default)
        )
        assert await app.service.review_configuration()
    app.service.acknowledge(tuple(w.code for w in app.service.snapshot.review.warnings))
    assert await app.service.preview_preprocessing()
    await app.push_screen(Models())
    await pilot.pause()


async def start(app, pilot):
    app.screen.query_one("#train").focus()
    await pilot.press("enter")
    await until(lambda: isinstance(app.screen, Training))
    return app.screen


@pytest.fixture
def children(monkeypatch):
    original = asyncio.create_subprocess_exec
    pids = []

    def inject(*modes):
        queue = iter(modes)

        async def spawn(*args, **kwargs):
            request = decode(
                read_owned(Path(args[3]), f"request-{args[4]}.json"), Request
            )
            mode = (
                next(queue) if request.identity.operation == Operation.TRAIN else None
            )
            command = (
                (
                    sys.executable,
                    str(Path(__file__).parents[1] / "execution/fixtures/child.py"),
                    args[3],
                    args[4],
                    mode,
                )
                if mode
                else args
            )
            child = await original(*command, **kwargs)
            pids.append(child.pid)
            return child

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        return pids

    return inject


@pytest.mark.parametrize("task", list(TaskKind))
async def test_actual_training_accepts_all_selected_models(task):
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await configure(app, pilot, task)
        before = app.service.snapshot.configuration
        owner = await start(app, pilot)
        await until(lambda: owner.finished)
        await pilot.pause()
        assert app.service.snapshot.activity == Activity.IDLE
        assert len(app.service.snapshot.results) == (2 if task.supervised else 1)
        assert all(
            c.status == CandidateStatus.COMPLETED for c in app.service.snapshot.results
        )
        assert not app.service.snapshot.run.cancelled
        assert isinstance(app.screen, Results)
        table = app.screen.query_one("#results", DataTable)
        assert all(
            str(table.get_cell(c.model_id, "status")) == "Completed"
            for c in app.service.snapshot.results
        )
        table.focus()
        await pilot.press("question_mark")
        assert isinstance(app.screen, Help) and "evaluated" in app.screen.body_text
        await pilot.press("escape")
        assert app.focused is table
        await pilot.press("escape")
        assert isinstance(app.screen, Models)
        assert app.service.snapshot.configuration == before
    assert not app.service._coordinator.root.exists()


@pytest.mark.parametrize(
    "modes",
    [
        ("failure-CONVERGENCE", None),
        (None, "failure-CONVERGENCE"),
        ("failure-CONVERGENCE", "failure-CANDIDATE_FAILED"),
        ("malformed", None),
    ],
)
async def test_candidate_failures_are_isolated_and_visible(
    children, modes, monkeypatch
):
    monkeypatch.delenv("NO_COLOR", raising=False)
    pids = children(*modes)
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await configure(app, pilot)
        owner = await start(app, pilot)
        await until(lambda: owner.finished)
        await pilot.pause()
        assert len(app.service.snapshot.results) == 2
        completed = sum(
            c.status == CandidateStatus.COMPLETED for c in app.service.snapshot.results
        )
        assert completed == modes.count(None)
        table = (
            app.screen.query_one("#results", DataTable)
            if completed
            else owner.query_one("#candidates", DataTable)
        )
        for candidate in app.service.snapshot.results:
            if candidate.status == CandidateStatus.FAILED:
                assert str(table.get_cell(candidate.model_id, "status")) == "Failed"
                if not completed:
                    assert str(table.get_cell(candidate.model_id, "reason"))
                else:
                    assert candidate.error_message or candidate.error_code
        if completed:
            assert "Failed —" in str(
                app.screen.query_one("#failure-summary", Static).content
            )
            assert "Only completed model" in str(
                app.screen.query_one("#recommendation", Static).content
            )
            failed_row = next(
                i
                for i, model_id in enumerate(app.screen.shown)
                if any(
                    c.model_id == model_id and c.status == CandidateStatus.FAILED
                    for c in app.service.snapshot.results
                )
            )
            table.move_cursor(row=failed_row, column=1)
            table.focus()
            await pilot.press("enter")
            assert isinstance(app.screen, Results)
            assert app.service.snapshot.selected is None
            assert "current model" in str(
                app.screen.query_one("#error", Static).content
            )
            await pilot.press("question_mark")
            assert isinstance(app.screen, Help) and app.screen.body_text
            await pilot.press("escape")
            table.move_cursor(row=0)
            await pilot.press("enter")
            assert isinstance(app.screen, SelectedModel)
            await pilot.press("escape")
        if not completed:
            assert "No model completed" in str(
                owner.query_one("#progress", Static).content
            )
            assert "Error:" in str(owner.query_one("#error", Static).content)
        assert app.service.snapshot.activity == Activity.IDLE
        assert app.screen.query_one("#back").display
        destination = Path(".mlforge-build/p07-training")
        destination.mkdir(parents=True, exist_ok=True)
        for width, height in [(80, 24), (100, 30)]:
            await pilot.resize_terminal(width, height)
            await pilot.pause()
            assert table.max_scroll_x == 0
            app.save_screenshot(
                f"failure-{modes[0]}-{modes[1]}-{width}.svg", path=str(destination)
            )
        if not completed:
            table.focus()
            await pilot.press("question_mark")
            assert isinstance(app.screen, Help) and app.screen.body_text
            await pilot.press("escape")
            await pilot.press("ctrl+q")
            await until(lambda: app.service.snapshot.activity == Activity.CLOSED)
    for pid in pids:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


@pytest.mark.parametrize(
    "route,monochrome",
    [
        ("cancel-first", False),
        ("cancel-second", False),
        ("back", False),
        ("quit", False),
        ("resize", False),
        ("grandchild", False),
        ("cancel-second", True),
    ],
)
async def test_real_cancel_timer_overlays_and_cleanup(
    children, route, monochrome, monkeypatch
):
    if monochrome:
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.delenv("NO_COLOR", raising=False)
    capture_name = f"{route}-{'mono' if monochrome else 'color'}"
    modes = (
        (None, "ignore")
        if route == "cancel-second"
        else ("grandchild" if route == "grandchild" else "ignore", None)
    )
    pids = children(*modes)
    app = MLForgeApp(Service())
    destination = Path(".mlforge-build/p07-training")
    destination.mkdir(parents=True, exist_ok=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await configure(app, pilot)
        owner = await start(app, pilot)
        model = (
            "classification.forest"
            if route == "cancel-second"
            else "classification.logistic"
        )
        await until(
            lambda: (
                app.service.snapshot.active is not None
                and app.service.snapshot.active.identity.model_id == model
                and app.service.snapshot.active.sequence >= 0
            )
        )
        if route == "grandchild":
            pids.append(
                int((app.service._coordinator.root / "grandchild.pid").read_text())
            )
        active = app.service.snapshot.active
        before = app.service.snapshot
        assert not app.service._event(
            RunEvent(
                replace(active.identity, revision=active.identity.revision + 1),
                1,
                EventKind.FAILED,
                error_code="PROTOCOL",
            )
        )
        assert not app.service._event(RunEvent(active.identity, 0, EventKind.STARTED))
        assert app.service.snapshot is before
        if route == "cancel-second":
            for width, height in [(100, 30), (140, 40), (80, 24)]:
                await pilot.resize_terminal(width, height)
                await pilot.pause()
                assert app.screen is owner and app.focused.id == "cancel"
                assert app.service.snapshot.activity == Activity.RUNNING
                app.save_screenshot(
                    f"{capture_name}-running-{width}.svg", path=str(destination)
                )
        first = str(owner.query_one("#progress", Static).content)
        await asyncio.sleep(0.25)
        await pilot.pause()
        assert str(owner.query_one("#progress", Static).content) != first
        await pilot.press("question_mark")
        assert isinstance(app.screen, Help)
        assert "Background work is running" in str(
            app.screen.query_one("#background-status", Static).content
        )
        await pilot.press("escape")
        assert app.focused.id == "cancel"
        app.save_screenshot(f"{capture_name}-running-80.svg", path=str(destination))
        if route == "quit":
            await pilot.press("ctrl+q")
            assert isinstance(app.screen, Confirm) and app.focused.id == "keep"
            await pilot.press("tab", "enter")
            await until(lambda: app.service.snapshot.activity == Activity.CLOSED)
        elif route == "back":
            await pilot.press("escape")
            assert isinstance(app.screen, Confirm) and app.focused.id == "keep"
            await pilot.press("enter")
            assert (
                app.screen is owner
                and app.service.snapshot.activity == Activity.RUNNING
            )
            await pilot.press("escape", "tab", "enter")
            await until(lambda: isinstance(app.screen, Models))
            assert app.service.snapshot.activity == Activity.IDLE
        else:
            if route == "resize":
                await pilot.resize_terminal(79, 23)
                await pilot.pause()
                assert isinstance(app.screen, ResizeGuard)
                await pilot.press("escape")
            else:
                await pilot.press("enter")
            assert app.service.snapshot.activity == Activity.CANCELLING
            # A message-queue pause does not advance the 100ms presentation timer.
            await until(
                lambda: (
                    "Stopping training"
                    in str(owner.query_one("#progress", Static).content)
                )
            )
            assert app.service.snapshot.activity == Activity.CANCELLING
            app.save_screenshot(
                f"{capture_name}-stopping-80.svg", path=str(destination)
            )
            await until(lambda: owner.finished)
            if route == "resize":
                assert isinstance(app.screen, ResizeGuard)
                await pilot.resize_terminal(80, 24)
            await pilot.pause()
            assert app.service.snapshot.run.cancelled
            count = 1 if route == "cancel-second" else 0
            assert len(app.service.snapshot.results) == count
            assert f"Cancelled — {count} models completed." in str(
                app.screen.query_one("#run-context", Static).content
                if count
                else owner.query_one("#progress", Static).content
            )
            assert app.service.snapshot.activity == Activity.IDLE
            if count:
                assert isinstance(app.screen, Results)
                assert "Cancelled" in str(
                    app.screen.query_one("#run-context", Static).content
                )
                await pilot.press("enter")
                assert isinstance(app.screen, SelectedModel)
                selected = app.service.snapshot.results[0]
                assert app.service.snapshot.selected is selected
                await pilot.press("escape", "escape")
                assert isinstance(app.screen, Models)
                app.screen.query_one("#review-results").focus()
                await pilot.press("enter")
                assert isinstance(app.screen, Results)
                assert app.service.snapshot.selected is selected
            app.save_screenshot(
                f"{capture_name}-cancelled-80.svg", path=str(destination)
            )
    assert not app.service._coordinator.root.exists()
    for pid in pids:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
