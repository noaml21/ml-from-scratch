"""Actual child faults/cancel and overlay races during dataset operations."""

import asyncio
import os
import sys
from pathlib import Path

import pytest
from textual.widgets import Input, Static

from mlforge.application.service import Service
from mlforge.application.state import Activity
from mlforge.tui.app import MLForgeApp
from mlforge.tui.screens.dataset import Busy, PathEntry
from mlforge.tui.screens.preview import Preview, TypeReview
from mlforge.tui.screens.shell import Help, ResizeGuard


async def until(predicate):
    async with asyncio.timeout(30):
        while not predicate():
            await asyncio.sleep(0.02)


@pytest.mark.parametrize("mode", ["malformed", "crash", "ignore"])
async def test_real_fault_or_cancel_returns_to_path_and_reaps(
    tmp_path, monkeypatch, mode
):
    original = asyncio.create_subprocess_exec
    pids = []

    async def spawn(*args, **kwargs):
        child = await original(
            sys.executable,
            str(Path(__file__).parents[1] / "execution/fixtures/child.py"),
            args[3],
            args[4],
            mode,
            **kwargs,
        )
        pids.append(child.pid)
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter", "down", "enter")
        field = app.screen.query_one("#path", Input)
        field.value = str(tmp_path / "synthetic.csv")
        await pilot.press("enter")
        if mode == "ignore":
            await until(
                lambda: (
                    app.service.snapshot.active
                    and app.service.snapshot.active.sequence >= 0
                )
            )
            assert isinstance(app.screen, Busy)
            await pilot.press("question_mark")
            assert isinstance(app.screen, Help)
            await pilot.press("escape", "enter")
            assert app.service.snapshot.activity == Activity.CANCELLING
        await until(lambda: isinstance(app.screen, PathEntry))
        assert app.focused is field and field.value.endswith("synthetic.csv")
        message = str(app.screen.query_one("#error", Static).content)
        assert "Error:" in message and "Traceback" not in message
        assert app.service.snapshot.dataset is None
        assert app.service.snapshot.activity == Activity.IDLE
    for pid in pids:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


@pytest.mark.parametrize("overlay", ["help", "resize"])
async def test_completed_type_change_waits_for_overlay(tmp_path, monkeypatch, overlay):
    source = tmp_path / "synthetic.csv"
    source.write_text("x\n1\n2\n")
    service = Service()
    app = MLForgeApp(service)
    ready, release = asyncio.Event(), asyncio.Event()
    original = service.change_type

    async def held(*args, **kwargs):
        accepted = await original(*args, **kwargs)
        ready.set()
        await release.wait()
        return accepted

    monkeypatch.setattr(service, "change_type", held)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter", "down", "enter")
        app.screen.query_one("#path", Input).value = str(source)
        await pilot.press("enter")
        await until(lambda: isinstance(app.screen, Preview))
        await pilot.pause()
        owner = app.screen
        await pilot.press("tab", "tab", "tab", "enter")
        assert isinstance(app.screen, TypeReview)
        await pilot.press("down", "enter")
        await asyncio.wait_for(ready.wait(), 30)
        if overlay == "help":
            await pilot.press("question_mark")
        else:
            await pilot.resize_terminal(79, 23)
            await pilot.pause()
            assert isinstance(app.screen, ResizeGuard)
        screen, focused = app.screen, app.focused
        release.set()
        await pilot.pause()
        assert app.screen is screen and app.focused is focused
        if overlay == "help":
            await pilot.press("escape")
        else:
            await pilot.resize_terminal(80, 24)
        await until(lambda: app.screen is owner)
        assert app.focused.id == "change-type"
        assert owner.schema.profile("c0").overridden
