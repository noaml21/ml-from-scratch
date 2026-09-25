"""Real preparation entry, explicit clipboard request, safe save and recovery."""

import asyncio
import os
from pathlib import Path

import pytest
from textual.widgets import Input, Static, TextArea

from mlforge.application.service import Service
from mlforge.application.state import Activity
from mlforge.tui.app import MLForgeApp
from mlforge.tui.screens.dataset import Load, PathEntry
from mlforge.tui.screens.prepare import Prepare, SavePrompt
from mlforge.tui.screens.preview import Preview
from mlforge.tui.screens.shell import Confirm, Help, ResizeGuard


async def until(predicate):
    async with asyncio.timeout(30):
        while not predicate():
            await asyncio.sleep(0.02)


async def rejected_preview(app, pilot, path):
    await pilot.press("enter", "down", "enter")
    app.screen.query_one("#path", Input).value = str(path)
    await pilot.press("enter")
    await until(lambda: isinstance(app.screen, Preview))
    await pilot.pause()
    await pilot.press("tab", "tab", "tab", "tab", "enter")
    assert isinstance(app.screen, Prepare)


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
async def test_rejected_preview_copy_save_privacy_keyboard_and_resize(
    tmp_path, monkeypatch, size
):
    source = tmp_path / "private_file.csv"
    source.write_text("private_column\n[bold]private_value\x1b[31m\n")
    original = source.read_bytes()
    app = MLForgeApp(Service())
    requests = []
    monkeypatch.setattr(app, "copy_to_clipboard", requests.append)
    async with app.run_test(size=size) as pilot:
        await rejected_preview(app, pilot, source)
        prepare = app.screen
        text = prepare.query_one("#prompt", TextArea)
        prompt = text.text
        assert text.read_only and not requests
        assert (
            "private_" not in prompt
            and str(tmp_path) not in prompt
            and "\x1b" not in prompt
        )
        assert "PREVIEW" in prompt and "CSV" in prompt
        await pilot.press("q", "b", "?", "f1")
        assert isinstance(app.screen, Help)
        await pilot.press("escape")
        assert app.focused is text and text.text == prompt
        await pilot.press("tab", "enter")
        assert requests == [prompt]
        assert "Copy requested" in str(prepare.query_one("#message", Static).content)
        await pilot.press("tab", "enter")
        assert isinstance(app.screen, SavePrompt)
        field = app.screen.query_one("#destination", Input)
        destination = tmp_path / "prompt 世界.txt"
        field.value = str(destination)
        for width, height in [(140, 40), (79, 23), (80, 24)]:
            await pilot.resize_terminal(width, height)
            await pilot.pause()
            if width < 80:
                assert isinstance(app.screen, ResizeGuard)
            else:
                assert app.focused is field and field.value == str(destination)
        await pilot.press("enter")
        await until(lambda: not app.screen.saving)
        assert destination.read_text() == prompt
        assert destination.stat().st_mode & 0o777 == 0o600
        assert str(destination) in str(app.screen.query_one("#message", Static).content)
        await pilot.press("enter")
        await until(lambda: not app.screen.saving)
        assert "already exists" in str(app.screen.query_one("#message", Static).content)
        assert app.focused is field and destination.read_text() == prompt
        await pilot.press("escape", "escape")
        assert app.screen is prepare and text.text == prompt
        await pilot.press("tab", "enter")  # Back to the inspected data.
        assert isinstance(app.screen, Preview) and not app.service.snapshot.confirmed
    assert source.read_bytes() == original
    assert not list(tmp_path.glob(".mlforge-prompt-*"))


@pytest.mark.parametrize(
    "error", [OSError("private clipboard failure"), NotImplementedError()]
)
async def test_clipboard_failure_retains_text_and_save(tmp_path, monkeypatch, error):
    source = tmp_path / "data.csv"
    source.write_text("x\n1\n")
    app = MLForgeApp(Service())

    def fail(text):
        raise error

    monkeypatch.setattr(app, "copy_to_clipboard", fail)
    async with app.run_test(size=(80, 24)) as pilot:
        await rejected_preview(app, pilot, source)
        prompt = app.screen.prompt
        await pilot.press("tab", "enter")
        message = str(app.screen.query_one("#message", Static).content)
        assert "Clipboard unavailable" in message and "private" not in message
        assert app.screen.query_one("#prompt", TextArea).text == prompt
        await pilot.press("tab", "enter")
        assert isinstance(app.screen, SavePrompt)


@pytest.mark.parametrize(
    "name,content,code",
    [
        ("bad.csv", 'a,b\n"unfinished,1\n', "CSV_QUOTES"),
        ("bad.tsv", "a\tb\n1\n", "ROW_WIDTH"),
        ("bad.jsonl", '{"a": 1}\n{"b": 2}\n', "JSON_KEYS"),
        ("bad.xlsx", "not supported", "FORMAT"),
        ("gone.csv", None, "FILE_READ"),
        ("https://example.invalid/data.csv", None, "LOCAL_FILE"),
    ],
)
async def test_import_errors_offer_private_preparation_and_retry(
    tmp_path, name, content, code
):
    path = name if "://" in name else tmp_path / name
    if content is not None:
        path.write_text(content)
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter", "down", "enter")
        field = app.screen.query_one("#path", Input)
        field.value = str(path)
        await pilot.press("enter")
        await until(
            lambda: (
                isinstance(app.screen, PathEntry)
                and bool(str(app.screen.query_one("#error", Static).content))
            )
        )
        assert app.focused is field and field.value == str(path)
        await pilot.press("tab", "tab", "enter")
        assert isinstance(app.screen, Prepare)
        assert code in app.screen.prompt and name not in app.screen.prompt
        await pilot.press("tab", "tab", "tab", "tab", "enter")
        assert isinstance(app.screen, Load)


@pytest.mark.parametrize(
    "destination",
    [
        "bad.csv",
        "missing/prompt.txt",
        "~mlforge_missing_user_928374/prompt.txt",
        "bad\x00/prompt.txt",
    ],
)
async def test_invalid_save_path_is_recoverable(tmp_path, monkeypatch, destination):
    monkeypatch.chdir(tmp_path)
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await app.push_screen(SavePrompt("CSV", "PREVIEW"))
        field = app.screen.query_one("#destination", Input)
        field.value = destination
        await pilot.press("enter")
        await until(lambda: not app.screen.saving)
        assert "Error:" in str(app.screen.query_one("#message", Static).content)
        assert app.focused is field and field.value == destination
        assert app.service.snapshot.activity == Activity.IDLE
    assert not list(tmp_path.glob(".mlforge-prompt-*"))


async def test_save_disk_failure_and_quit_waits_for_owned_writer(tmp_path, monkeypatch):
    import threading

    from mlforge.application import service as module

    destination = tmp_path / "prompt.txt"
    app = MLForgeApp(Service())
    original = module.save_prompt
    started, release = threading.Event(), threading.Event()

    def held(*args):
        started.set()
        assert release.wait(10)
        return original(*args)

    monkeypatch.setattr(module, "save_prompt", held)
    async with app.run_test(size=(80, 24)) as pilot:
        await app.push_screen(SavePrompt("CSV", "PREVIEW"))
        app.screen.query_one("#destination", Input).value = str(destination)
        await pilot.press("enter")
        await until(started.is_set)
        assert app.service.snapshot.activity == Activity.SAVING
        await pilot.resize_terminal(79, 23)
        await pilot.pause()
        assert "finish save" in str(
            app.screen.query_one("#resize-actions", Static).content
        )
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        await pilot.press("ctrl+q")
        assert isinstance(app.screen, Confirm) and app.focused.id == "keep"
        await pilot.press("tab", "enter")
        await pilot.pause()
        assert app.service.snapshot.activity != Activity.CLOSED
        release.set()
        await until(lambda: app.service.snapshot.activity == Activity.CLOSED)
    assert destination.exists() and not list(tmp_path.glob(".mlforge-prompt-*"))
    assert not app.service._coordinator.root.exists()

    def fail(fd):
        raise OSError("private disk failure")

    monkeypatch.setattr(module, "save_prompt", original)
    monkeypatch.setattr(os, "fsync", fail)
    async with Service() as service:
        from mlforge.contracts import DomainError

        with pytest.raises(DomainError) as error:
            await service.save_preparation(tmp_path / "failed.txt", "CSV")
        assert error.value.code == "PROMPT_SAVE"
        assert service.snapshot.activity == Activity.IDLE
    assert not (tmp_path / "failed.txt").exists()
    assert not list(tmp_path.glob(".mlforge-prompt-*"))


async def test_selected_input_uses_readable_canonical_pair(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await app.push_screen(SavePrompt("CSV", "PREVIEW"))
        await pilot.press("ctrl+shift+a")
        field = app.focused
        assert app.get_css_variables()["text"] == "#E6EEF3"
        style = field.get_component_rich_style("input--selection")
        assert style.color.triplet == (230, 238, 243)
        assert style.bgcolor.triplet == (36, 66, 71)
        assert field.styles.background_tint.a == 0

        def luminance(rgb):
            parts = [v / 255 for v in rgb]
            linear = [
                v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
                for v in parts
            ]
            return sum(v * w for v, w in zip(linear, (0.2126, 0.7152, 0.0722)))

        contrast = (luminance(style.color.triplet) + 0.05) / (
            luminance(style.bgcolor.triplet) + 0.05
        )
        assert contrast >= 4.5
        await pilot.pause()
        svg = app.export_screenshot()
        assert 'fill="#244247"' in svg
        destination = Path(".mlforge-build/p06-prepare")
        destination.mkdir(parents=True, exist_ok=True)
        app.save_screenshot("input-selection-80.svg", path=str(destination))


@pytest.mark.parametrize("monochrome", [False, True])
async def test_prepare_visual_evidence(tmp_path, monkeypatch, monochrome):
    if monochrome:
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.delenv("NO_COLOR", raising=False)
    destination = Path(".mlforge-build/p06-prepare")
    destination.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "synthetic.csv"
    source.write_text("x\n1\n")
    for size in [(80, 24), (100, 30), (140, 40)]:
        app = MLForgeApp(Service())
        async with app.run_test(size=size) as pilot:
            await rejected_preview(app, pilot, source)
            suffix = f"{size[0]}-{'mono' if monochrome else 'color'}.svg"
            app.save_screenshot(f"prepare-{suffix}", path=str(destination))
            await pilot.press("tab", "tab", "enter")
            app.screen.query_one("#destination", Input).value = str(
                tmp_path / "missing" / "prompt.txt"
            )
            await pilot.press("enter")
            await until(lambda: not app.screen.saving)
            await pilot.pause()
            app.save_screenshot(f"save-error-{suffix}", path=str(destination))
