"""Real accepted dataset preview, literal full detail and keyboard navigation."""

import asyncio
import csv
from pathlib import Path

import pytest
from textual.widgets import DataTable, Input

from mlforge.application.service import Service
from mlforge.datasets.records import ColumnType, preview, visible_text
from mlforge.tui.app import MLForgeApp
from mlforge.tui.screens.preview import Preview
from mlforge.tui.screens.shell import Help, ResizeGuard


async def load(pilot, app, source):
    await pilot.press("enter", "down", "enter")
    app.screen.query_one("#path", Input).value = str(source)
    await pilot.press("enter")
    async with asyncio.timeout(30):
        while not isinstance(app.screen, Preview):
            await asyncio.sleep(0.02)
    await pilot.pause()


@pytest.mark.parametrize("size", [(100, 30), (80, 24)])
async def test_full_table_profiles_first_50_rows_and_literal_detail(tmp_path, size):
    source = tmp_path / "table.csv"
    values = [[str(i % 3), f"{i:03}", ""] for i in range(60)]
    values[-1][0] = "tail conflict"
    values[0][2] = "[bold]世界[/bold]\x1b[31m" + "a" * 4000
    values[1][2] = "NA"
    with source.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["value", "zip", "notes"])
        writer.writerows(values)
    original = source.read_bytes()
    app = MLForgeApp(Service())
    async with app.run_test(size=size) as pilot:
        await load(pilot, app, source)
        state = app.service.snapshot
        view = app.screen.view
        assert view["columns"][0]["type"] == "Category"  # Tail outside preview.
        assert view["columns"][1]["type"] == "Category"  # Leading zeros.
        assert view["columns"][2]["missing_count"] == 58
        assert view["columns"][2]["distinct_count"] == 2
        assert "First 50 of 60 rows" in str(
            app.screen.query_one("#preview-label").content
        )
        columns, rows = (
            app.screen.query_one("#columns", DataTable),
            app.screen.query_one("#rows", DataTable),
        )
        assert rows.row_count == 50 and columns.row_count == 3
        assert app.focused is columns and not state.confirmed
        assert str(rows.get_cell("0", "c1")) == "000"
        assert str(rows.get_cell("2", "c2")) == "Missing"
        assert str(rows.get_cell("1", "c2")) == "NA"
        assert str(rows.get_cell("0", "c2")).endswith("…")
        await pilot.press("down", "down", "question_mark")
        assert isinstance(app.screen, Help)
        assert "Missing: 58 (96.7%)" in app.screen.body_text
        assert visible_text(values[0][2]) in app.screen.body_text
        await pilot.press("escape")
        assert app.focused is columns and columns.cursor_row == 2
        await pilot.press("tab", "right", "right", "question_mark")
        assert isinstance(app.screen, Help)
        assert visible_text(values[0][2]) in app.screen.body_text
        assert "\x1b" not in app.screen.body_text
        await pilot.press(
            "tab", "end"
        )  # Scrollable complete detail, close stays reachable.
        await pilot.press("escape")
        assert app.focused is rows and rows.cursor_column == 3
        await pilot.press("ctrl+end")
        assert rows.cursor_row == 49
        assert app.service.snapshot.dataset == state.dataset
    assert source.read_bytes() == original


async def test_wide_table_scroll_resize_help_preserves_selection(tmp_path):
    source = tmp_path / "wide.tsv"
    source.write_text(
        "\t".join(f"column{i}" for i in range(100))
        + "\n"
        + "\t".join("001" for _ in range(100))
        + "\n"
    )
    app = MLForgeApp(Service())
    async with app.run_test(size=(100, 30)) as pilot:
        await load(pilot, app, source)
        await pilot.press("tab")
        table = app.focused
        for _ in range(99):
            table.action_cursor_right()
        await pilot.pause()
        assert table.cursor_column == 100 and table.scroll_x > 0
        point = table.cursor_coordinate
        for width, height in [(80, 24), (79, 23), (140, 40), (100, 30)]:
            await pilot.resize_terminal(width, height)
            await pilot.pause()
            if width < 80:
                assert isinstance(app.screen, ResizeGuard)
            else:
                assert app.focused is table and table.cursor_coordinate == point
        await pilot.press("question_mark")
        assert "column99" in app.screen.body_text and "001" in app.screen.body_text
        await pilot.press("escape")
        assert app.focused is table and table.cursor_coordinate == point


async def test_overridden_profile_and_bounded_projection_do_not_mutate_data(tmp_path):
    source = tmp_path / "numbers.csv"
    source.write_text("zip\n1\n1.0\n2\n")
    async with Service() as service:
        assert await service.load(source)
        assert await service.change_type("c0", ColumnType.CATEGORY)
        original = service.snapshot.dataset
        schema = service.snapshot.schema
        full = preview(original, schema)
        short = preview(original, schema, text_limit=1)
        assert short["columns"][0]["overridden"]
        assert short["columns"][0]["detected"] == "Number"
        assert short["columns"][0]["type"] == "Category"
        assert full["columns"][0]["samples"] == ["1", "1.0", "2"]
        assert short["columns"][0]["samples"] == ["1", "1…", "2"]
        assert full["rows"][1][0] == "1.0" and short["rows"][1][0] == "1…"
        assert service.snapshot.dataset == original


@pytest.mark.parametrize("monochrome", [False, True])
async def test_preview_visual_captures(tmp_path, monkeypatch, monochrome):
    if monochrome:
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.delenv("NO_COLOR", raising=False)
    destination = Path(".mlforge-build/p06-preview").resolve()
    destination.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "synthetic.jsonl"
    source.write_text(
        '{"amount": 1, "zip": "001", "notes": "世界"}\n'
        '{"notes": null, "zip": "002", "amount": 2}\n'
    )
    for size in [(100, 30), (80, 24), (140, 40)]:
        app = MLForgeApp(Service())
        async with app.run_test(size=size) as pilot:
            await load(pilot, app, source)
            suffix = f"{size[0]}-{'mono' if monochrome else 'color'}.svg"
            app.save_screenshot(f"preview-{suffix}", path=str(destination))
            await pilot.press("down", "question_mark")
            app.save_screenshot(f"detail-{suffix}", path=str(destination))
