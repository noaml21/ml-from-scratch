"""Real Textual keyboard shell over the authoritative application service."""

import asyncio
import os
import sys
from pathlib import Path

import pytest
from textual.widgets import Input, Static

from mlforge.application.service import Service
from mlforge.application.state import Activity
from mlforge.tui.app import MLForgeApp
from mlforge.tui.screens.dataset import Busy, Load, PathEntry, Preview, Welcome
from mlforge.tui.screens.shell import Confirm, Help, ResizeGuard


async def wait_screen(app, screen):
    async with asyncio.timeout(30):
        while not isinstance(app.screen, screen):
            await asyncio.sleep(0.02)


@pytest.mark.parametrize("size", [(100, 30), (80, 24)])
async def test_welcome_keyboard_help_focus_and_literal_input(size):
    service = Service()
    app = MLForgeApp(service)
    async with app.run_test(size=size) as pilot:
        assert isinstance(app.screen, Welcome)
        assert "Press Enter" in str(app.screen.query_one("#begin", Static).content)
        await pilot.press("enter", "down", "enter")
        assert isinstance(app.screen, PathEntry)
        field = app.screen.query_one("#path", Input)
        assert app.focused is field
        assert app.screen.active_bindings["f1"].binding.show
        assert "question_mark" not in app.screen.active_bindings
        await pilot.press("q", "b", "?", "space")
        assert field.value == "qb? "
        await pilot.press("f1")
        assert isinstance(app.screen, Help)
        await pilot.press("escape")
        assert app.focused is field and field.value == "qb? "
        await pilot.press("tab")
        assert app.focused.id == "load"
        await pilot.press("question_mark")
        assert isinstance(app.screen, Help)
        await pilot.press("escape")
        assert app.focused.id == "load"
        await pilot.press("tab")
        assert app.focused.id == "back"
        await pilot.press("tab")
        assert app.focused is field
        await pilot.press("tab")
        await pilot.press("shift+tab")
        assert app.focused is field
        await pilot.press("escape")
        assert app.focused.id == "load"
        await pilot.press("escape")
        assert isinstance(app.screen, Load)
        await pilot.press("escape")
        assert isinstance(app.screen, Welcome)
        root = service._coordinator.root
        await pilot.press("ctrl+q")
    assert service.snapshot.activity == Activity.CLOSED and not root.exists()


@pytest.mark.parametrize("size", [(100, 30), (80, 24)])
async def test_real_load_error_retry_summary_and_source_unchanged(tmp_path, size):
    source = tmp_path / "synthetic 世界.csv"
    content = "[bold]literal[/bold],zip\n1,001\n2,002\n"
    source.write_text(content)
    service = Service()
    app = MLForgeApp(service)
    async with app.run_test(size=size) as pilot:
        await pilot.press("enter", "down", "enter")
        field = app.screen.query_one("#path", Input)
        field.value = str(tmp_path / "missing.csv")
        await pilot.press("enter")
        async with asyncio.timeout(30):
            while not (
                isinstance(app.screen, PathEntry)
                and str(app.screen.query_one("#error", Static).content)
            ):
                await asyncio.sleep(0.02)
        assert app.focused is field
        assert "missing.csv" in field.value
        field.value = str(source)
        await pilot.press("enter")
        await wait_screen(app, Preview)
        assert service.snapshot.dataset.rows[0][1].raw_text == "001"
        assert not service.snapshot.confirmed
        assert "2 rows · 2 columns" in str(
            app.screen.query_one("#summary", Static).content
        )
        assert any(
            "[bold]literal[/bold]" in str(widget.content)
            for widget in app.screen.query(Static)
        )
        await pilot.pause()  # The accepted screen must finish its first paint.
        assert "[bold]literal[/bold]" in app.export_screenshot()
        await pilot.press("escape")
        assert isinstance(app.screen, PathEntry) and field.value == str(source)
    assert source.read_text() == content
    assert service.snapshot.activity == Activity.CLOSED


async def test_resize_preserves_field_help_and_focus():
    app = MLForgeApp(Service())
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("enter", "down", "enter")
        field = app.screen.query_one("#path", Input)
        field.value = "unsubmitted 世界 file.csv"
        for size in [(80, 24), (79, 23), (100, 30)]:
            await pilot.resize_terminal(*size)
            await pilot.pause()
            if size == (79, 23):
                assert isinstance(app.screen, ResizeGuard)
            else:
                assert isinstance(app.screen, PathEntry)
                assert app.focused is field
        assert field.value == "unsubmitted 世界 file.csv"
        await pilot.press("f1")
        modal = app.screen
        await pilot.resize_terminal(79, 23)
        await pilot.pause()
        assert isinstance(app.screen, ResizeGuard)
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        assert app.screen is modal
        await pilot.press("escape")
        assert app.focused is field


async def test_below_minimum_quit_cleans_session():
    service = Service()
    app = MLForgeApp(service)
    async with app.run_test(size=(60, 15)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ResizeGuard)
        root = service._coordinator.root
        await pilot.press("ctrl+q")
    assert not root.exists() and service.snapshot.activity == Activity.CLOSED


@pytest.mark.parametrize("monochrome", [False, True])
async def test_shell_capture_evidence(monochrome, monkeypatch):
    if monochrome:
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.delenv("NO_COLOR", raising=False)
    destination = Path(".mlforge-build/p06-shell")
    destination.mkdir(parents=True, exist_ok=True)
    for width, height in [(100, 30), (80, 24)]:
        suffix = f"{width}-{'mono' if monochrome else 'color'}.svg"
        app = MLForgeApp(Service())
        async with app.run_test(size=(width, height)) as pilot:
            app.save_screenshot(f"welcome-{suffix}", path=str(destination))
            await pilot.press("enter", "down", "enter")
            app.save_screenshot(f"path-{suffix}", path=str(destination))
            await pilot.press("f1")
            app.save_screenshot(f"help-{suffix}", path=str(destination))


async def test_live_work_help_cancel_and_quit_default_keep(tmp_path, monkeypatch):
    original = asyncio.create_subprocess_exec
    pids = []

    async def spawn(*args, **kwargs):
        child = await original(
            sys.executable,
            str(Path(__file__).parents[1] / "execution/fixtures/child.py"),
            args[3],
            args[4],
            "ignore",
            **kwargs,
        )
        pids.append(child.pid)
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    service = Service()
    app = MLForgeApp(service)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter", "down", "enter")
        field = app.screen.query_one("#path", Input)
        field.value = str(tmp_path / "synthetic.csv")
        await pilot.press("enter")
        async with asyncio.timeout(10):
            while not (
                service.snapshot.active and service.snapshot.active.sequence >= 0
            ):
                await asyncio.sleep(0.02)
        assert isinstance(app.screen, Busy)
        await pilot.press("question_mark")
        assert isinstance(app.screen, Help)
        await pilot.press("escape")
        assert app.focused.id == "cancel"
        await pilot.press("ctrl+q")
        assert isinstance(app.screen, Confirm) and app.focused.id == "keep"
        await pilot.press("escape")
        assert service.snapshot.activity == Activity.RUNNING
        await pilot.press("ctrl+q", "tab", "enter")
        async with asyncio.timeout(5):
            while service.snapshot.activity != Activity.CLOSED:
                await asyncio.sleep(0.02)
    assert not service._coordinator.root.exists()
    for pid in pids:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


@pytest.mark.parametrize("overlay", ["help", "resize"])
async def test_completed_parse_waits_for_overlay_without_stealing_focus(
    tmp_path, monkeypatch, overlay
):
    source = tmp_path / "synthetic.csv"
    source.write_text("x\n1\n2\n")
    service = Service()
    original = service.load
    ready, release = asyncio.Event(), asyncio.Event()

    async def held(*args, **kwargs):
        result = await original(*args, **kwargs)
        ready.set()
        await release.wait()
        return result

    monkeypatch.setattr(service, "load", held)
    app = MLForgeApp(service)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("enter", "down", "enter")
        app.screen.query_one("#path", Input).value = str(source)
        await pilot.press("enter")
        await asyncio.wait_for(ready.wait(), 30)
        if overlay == "help":
            await pilot.press("question_mark")
        else:
            await pilot.resize_terminal(79, 23)
            await pilot.pause()
        screen, focused = app.screen, app.focused
        release.set()
        await pilot.pause()
        assert app.screen is screen and app.focused is focused
        if overlay == "help":
            await pilot.press("escape")
        else:
            await pilot.resize_terminal(80, 24)
        await wait_screen(app, Preview)
        assert service.snapshot.dataset.rows[0][0].raw_text == "1"
