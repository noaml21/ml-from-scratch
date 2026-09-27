"""Keyboard source choices use real workers, registries and local resources."""

import asyncio
from importlib.resources import files
from pathlib import Path

import pytest
from textual.widgets import Checkbox, OptionList, Static

from mlforge.application.service import Service
from mlforge.contracts import DomainError
from mlforge.tui.app import MLForgeApp
from mlforge.tui.screens.dataset import Browse, Examples, Load, LocalTree, Preview
from mlforge.tui.screens.shell import Help


async def wait_for(predicate):
    async with asyncio.timeout(30):
        while not predicate():
            await asyncio.sleep(0.02)


@pytest.mark.parametrize("index", range(5))
async def test_every_packaged_example_uses_ordinary_load(index, monkeypatch):
    service = Service()
    example = service.examples[index]
    source = files("mlforge").joinpath("examples", example.filename)
    original_bytes = source.read_bytes()
    ordinary_load = service.load
    calls = []

    async def observed(path, **kwargs):
        calls.append(Path(path).name)
        return await ordinary_load(path, **kwargs)

    monkeypatch.setattr(service, "load", observed)
    app = MLForgeApp(service)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter", "down", "down", "enter")
        assert isinstance(app.screen, Examples)
        for _ in range(index):
            await pilot.press("down")
        choices = app.screen.query_one("#examples", OptionList)
        assert choices.highlighted == index
        detail = str(app.screen.query_one("#example-detail", Static).content)
        assert "Synthetic" in detail and example.task.value in detail
        await pilot.press("question_mark")
        assert isinstance(app.screen, Help)
        await pilot.press("escape")
        assert app.focused is choices and choices.highlighted == index
        await pilot.press("enter")
        await wait_for(lambda: isinstance(app.screen, Preview))
        state = service.snapshot
        assert state.dataset.rows and state.schema.columns and not state.confirmed
        assert state.dataset.source_format == source.suffix[1:].upper()
        assert calls == [example.filename]
        await pilot.press("escape")
        assert isinstance(app.screen, Examples) and app.focused is choices
    assert source.read_bytes() == original_bytes
    assert not service._coordinator.root.exists()


@pytest.mark.parametrize("filename", ["../mixed.csv", "unknown.csv", "/mixed.csv"])
async def test_examples_reject_unregistered_paths(filename):
    async with Service() as service:
        with pytest.raises(DomainError) as error:
            await service.load_example(filename)
        assert error.value.code == "EXAMPLE" and service.snapshot.dataset is None


async def test_picker_lazy_filter_hidden_parent_and_literal_selection(
    tmp_path, monkeypatch
):
    folder = tmp_path / "folder"
    folder.mkdir()
    source = folder / "[bold] 世界\x1b.csv"
    content = "x,y\n1,001\n2,002\n"
    source.write_text(content)
    (tmp_path / ".hidden.csv").write_text(content)
    (tmp_path / "excluded.txt").write_text("not a dataset")
    (tmp_path / "visible.CSV").write_text(content)
    monkeypatch.chdir(tmp_path)
    original = Path.iterdir
    visits = []

    def listing(path):
        visits.append(path)
        return original(path)

    monkeypatch.setattr(Path, "iterdir", listing)
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter", "enter")
        assert isinstance(app.screen, Browse)
        tree = app.screen.query_one("#files", LocalTree)
        await wait_for(lambda: len(tree.root.children) == 2)
        assert tree.path == tmp_path and app.focused is tree
        assert str(app.screen.query_one("#hidden", Checkbox)._button) == "[ ]"
        assert set(visits) == {tmp_path}  # No recursive startup scan.
        assert {n.data.path.name for n in tree.root.children} == {
            "folder",
            "visible.CSV",
        }
        await pilot.press("shift+tab", "space")
        assert app.focused is app.screen.query_one("#hidden", Checkbox)
        assert str(app.focused._button) == "[x]"
        await wait_for(lambda: len(tree.root.children) == 3)
        assert any(n.data.path.name == ".hidden.csv" for n in tree.root.children)
        await pilot.press("space", "tab")
        await wait_for(lambda: len(tree.root.children) == 2)
        await pilot.press("down", "enter")
        await wait_for(lambda: tree.path == folder and len(tree.root.children) == 1)
        assert str(app.screen.query_one("#directory", Static).content) == str(folder)
        await pilot.press("tab", "enter")
        await wait_for(lambda: tree.path == tmp_path and len(tree.root.children) == 2)
        assert app.focused is tree
        await pilot.press("down", "enter")
        await wait_for(lambda: tree.path == folder and len(tree.root.children) == 1)
        await pilot.press("down")
        await pilot.pause()
        image = app.export_screenshot()
        assert "[bold]" in image and "\\u001b.csv" in image
        await pilot.press("enter")
        await wait_for(lambda: isinstance(app.screen, Preview))
        assert app.service.snapshot.dataset.rows[0][1].raw_text == "001"
    assert source.read_text() == content


async def test_unreadable_directory_recovers_with_parent_and_back(
    tmp_path, monkeypatch
):
    folder = tmp_path / "unreadable"
    folder.mkdir()
    monkeypatch.chdir(folder)
    original = Path.iterdir

    def listing(path):
        if path == folder:
            raise PermissionError("synthetic permission error")
        return original(path)

    monkeypatch.setattr(Path, "iterdir", listing)
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter", "enter")
        await wait_for(
            lambda: "unreadable" in str(app.screen.query_one("#error", Static).content)
        )
        tree = app.screen.query_one("#files", LocalTree)
        assert app.focused is tree
        await pilot.press("tab", "enter")
        await wait_for(lambda: tree.path == tmp_path and len(tree.root.children) == 1)
        assert str(app.screen.query_one("#error", Static).content) == ""
        await pilot.press("escape")
        assert isinstance(app.screen, Load) and app.focused.id == "sources"


@pytest.mark.parametrize("monochrome", [False, True])
async def test_source_visual_evidence(tmp_path, monkeypatch, monochrome):
    destination = Path(".mlforge-build/p06-sources").resolve()
    destination.mkdir(parents=True, exist_ok=True)
    (tmp_path / "synthetic 世界.csv").write_text("x\n1\n")
    (tmp_path / "folder").mkdir()
    monkeypatch.chdir(tmp_path)
    if monochrome:
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.delenv("NO_COLOR", raising=False)
    for width, height in [(100, 30), (80, 24), (140, 40)]:
        suffix = f"{width}-{'mono' if monochrome else 'color'}.svg"
        app = MLForgeApp(Service())
        async with app.run_test(size=(width, height)) as pilot:
            await pilot.press("enter")
            body = app.screen.query_one("#body")
            assert body.region.width <= 100
            assert abs(body.region.x - (width - body.region.width) / 2) <= 1
            app.save_screenshot(f"load-{suffix}", path=str(destination))
            await pilot.press("enter")
            tree = app.screen.query_one("#files", LocalTree)
            await wait_for(lambda: len(tree.root.children) == 2)
            await pilot.pause()
            app.save_screenshot(f"picker-{suffix}", path=str(destination))
            await pilot.press("escape", "down", "down", "enter")
            app.save_screenshot(f"examples-{suffix}", path=str(destination))
