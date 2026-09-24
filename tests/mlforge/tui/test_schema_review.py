"""Type review invokes accepted worker operations and explicit confirmation."""

import asyncio
from pathlib import Path

import pytest
from textual.widgets import Button, DataTable, Input, OptionList, Static

from mlforge.application.service import Service
from mlforge.contracts import DomainError
from mlforge.datasets.records import ColumnType
from mlforge.tui.app import MLForgeApp
from mlforge.tui.screens.dataset import Load
from mlforge.tui.screens.preview import Preview, TypeReview
from mlforge.tui.screens.shell import Help, ResizeGuard


async def until(predicate):
    async with asyncio.timeout(30):
        while not predicate():
            await asyncio.sleep(0.02)


async def open_preview(app, pilot, path):
    await pilot.press("enter", "down", "enter")
    app.screen.query_one("#path", Input).value = str(path)
    await pilot.press("enter")
    await until(lambda: isinstance(app.screen, Preview))
    await pilot.pause()


@pytest.mark.parametrize("size", [(80, 24), (100, 30)])
async def test_real_override_reset_confirmation_and_invalidation(tmp_path, size):
    path = tmp_path / "synthetic.csv"
    text = "number,zip,label\n1,001,a\n2,002,b\n"
    path.write_text(text)
    app = MLForgeApp(Service())
    async with app.run_test(size=size) as pilot:
        await open_preview(app, pilot, path)
        owner = app.screen
        before = app.service.snapshot
        await pilot.press("enter")  # Table inspection is never confirmation.
        assert isinstance(app.screen, Help) and not app.service.snapshot.confirmed
        await pilot.press("escape", "tab", "tab", "tab", "enter")
        assert isinstance(app.screen, TypeReview)
        assert app.focused.id == "types"
        await pilot.press("down", "enter")  # Number -> Category.
        await until(lambda: app.screen is owner)
        state = app.service.snapshot
        assert state.schema.profile("c0").overridden
        assert state.schema.profile("c0").effective == ColumnType.CATEGORY
        assert (
            state.dataset == before.dataset
            and state.revisions.schema > before.revisions.schema
        )
        assert not state.confirmed and app.focused.id == "change-type"
        await pilot.press("shift+tab", "enter")
        assert app.service.snapshot.confirmed
        assert owner.query_one("#correct", Button).disabled
        assert "Dataset confirmed" in str(owner.query_one("#status", Static).content)
        app.service.choose_task("classification")
        await pilot.press("enter")  # Disabled correct yields focus to Change type.
        assert isinstance(app.screen, TypeReview)
        await pilot.press("end", "enter")
        await until(lambda: app.screen is owner)
        assert not app.service.snapshot.confirmed
        assert app.service.snapshot.configuration.task is None
        assert not app.service.snapshot.schema.profile("c0").overridden
        assert app.service.snapshot.schema.profile("c0").effective == ColumnType.NUMBER
        assert not owner.query_one("#correct", Button).disabled
        await pilot.press("shift+tab", "shift+tab", "shift+tab", "down", "down")
        assert app.focused.id == "columns" and app.focused.cursor_row == 2
        await pilot.press("tab", "tab", "tab", "enter", "home", "enter")
        await until(
            lambda: (
                isinstance(app.screen, TypeReview)
                and bool(str(app.screen.query_one("#error", Static).content))
            )
        )
        assert "2 values" in str(app.screen.query_one("#error", Static).content)
        assert "Data rows: 1, 2" in str(app.screen.query_one("#error", Static).content)
        assert (
            app.service.snapshot.schema.profile("c2").effective == ColumnType.CATEGORY
        )
        assert not app.service.snapshot.schema.profile("c2").overridden
        await pilot.press("escape")
        assert app.screen is owner
        assert owner.query_one("#columns", DataTable).cursor_row == 2
        await pilot.press("tab", "enter")  # Choose another dataset.
        assert isinstance(app.screen, Load)
    assert path.read_text() == text


async def test_schema_error_is_safe_and_unknown_not_offered(tmp_path):
    path = tmp_path / "empty_column.csv"
    path.write_text("empty,other\n,x\n,y\n")
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await open_preview(app, pilot, path)
        with pytest.raises(DomainError) as error:
            await app.service.change_type("c0", "unsupported")
        assert error.value.code == "TYPE"
        await pilot.press("tab", "tab", "tab", "enter")
        choices = app.screen.query_one("#types", OptionList)
        assert "Unknown" not in [
            choices.get_option_at_index(i).id for i in range(choices.option_count)
        ]
        await pilot.press("home", "enter")
        await until(
            lambda: (
                isinstance(app.screen, TypeReview)
                and bool(str(app.screen.query_one("#error", Static).content))
            )
        )
        assert "no present values" in str(
            app.screen.query_one("#error", Static).content
        )
        for size in [(100, 30), (79, 23), (140, 40), (80, 24)]:
            await pilot.resize_terminal(*size)
            await pilot.pause()
            if size[0] < 80:
                assert isinstance(app.screen, ResizeGuard)
            else:
                assert app.focused is choices
        assert app.service.snapshot.schema.profile("c0").effective == ColumnType.UNKNOWN


@pytest.mark.parametrize("monochrome", [False, True])
async def test_schema_visual_evidence(tmp_path, monkeypatch, monochrome):
    if monochrome:
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.delenv("NO_COLOR", raising=False)
    destination = Path(".mlforge-build/p06-schema")
    destination.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "synthetic.csv"
    path.write_text("zip\n001\n002\n")
    for size in [(80, 24), (100, 30)]:
        app = MLForgeApp(Service())
        async with app.run_test(size=size) as pilot:
            await open_preview(app, pilot, path)
            suffix = f"{size[0]}-{'mono' if monochrome else 'color'}.svg"
            app.save_screenshot(f"review-{suffix}", path=str(destination))
            await pilot.press("tab", "tab", "tab", "enter")
            app.save_screenshot(f"types-{suffix}", path=str(destination))
