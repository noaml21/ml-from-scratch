"""Bounded literal views over accepted canonical data; no inference in widgets."""

from rich.text import Text
from textual import work
from textual.widgets import Button, DataTable, OptionList, Static
from textual.widgets.option_list import Option

from mlforge.contracts import DomainError
from mlforge.datasets.records import ColumnType, preview, visible_text
from mlforge.tui.help import CATALOG
from mlforge.tui.screens.prepare import Prepare
from mlforge.tui.screens.shell import Action, Busy, Frame, operation_message

WARNINGS = {
    "MIXED_KINDS": "Mixed scalar kinds; review the type before continuing.",
    "LEADING_ZEROS": "Leading zeros are preserved as text.",
    "PRECISION": "Large integers require text to preserve precision.",
    "HIGH_CARDINALITY": "Many distinct values; review this column's role.",
    "LONG_TEXT": "Long text; review this column's role.",
}


def snippet(value, width=24):
    """Cell-width truncation is presentation only; help retains the full value."""
    text = Text(value, no_wrap=True)
    text.truncate(width, overflow="ellipsis")
    return text


class Preview(Frame):
    heading = "Review your dataset"
    help_topic = "preview"
    status = "Arrows: inspect tables · Tab: switch controls · ?: full details"

    def content(self):
        state = self.app.service.snapshot
        self.dataset, self.schema = state.dataset, state.schema
        self.view = preview(self.dataset, self.schema, text_limit=80)
        yield Static(
            f"{self.view['row_count']:,} rows · {self.view['column_count']} columns",
            id="summary",
            markup=False,
        )
        yield Static(
            f"{self.dataset.source_format} · Full-table type inference · "
            f"{self.dataset.ignored_blank_records} blank records ignored",
            classes="muted",
            markup=False,
        )
        yield DataTable(id="columns", cursor_type="row", zebra_stripes=False)
        yield Static("", id="column-note", markup=False)
        yield Static(self.view["label"], id="preview-label", markup=False)
        yield DataTable(id="rows", cursor_type="cell", zebra_stripes=False)

    def on_mount(self):
        columns = self.query_one("#columns", DataTable)
        for label, key, width in [
            ("", "marker", 1),
            ("Column", "name", 18),
            ("Type", "type", 10),
            ("Missing", "missing", 14),
            ("Unique", "unique", 6),
            ("Samples", "samples", 10),
        ]:
            columns.add_column(Text(label), key=key, width=width)
        for column in self.view["columns"]:
            columns.add_row(
                "",
                snippet(column["name"], 18),
                column["type"] + (" *" if column["overridden"] else ""),
                Text(
                    f"{column['missing_count']} ({column['missing_percent']:.1f}%)",
                    justify="right",
                ),
                Text(str(column["distinct_count"]), justify="right"),
                snippet(" · ".join(column["samples"]), 10),
                key=column["id"],
            )
        rows = self.query_one("#rows", DataTable)
        rows.add_column(Text("Row"), key="row", width=5)
        rows.fixed_columns = 1
        for column in self.view["columns"]:
            rows.add_column(snippet(column["name"], 20), key=column["id"], width=20)
        for i, row in enumerate(self.view["rows"]):
            rows.add_row(
                Text(str(i + 1), justify="right"),
                *(
                    Text("Missing", style="italic")
                    if cell is None
                    else snippet(cell, 20)
                    for cell in row
                ),
                key=str(i),
            )
        rows.move_cursor(column=1)
        columns.focus()
        self.refresh_schema()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        if event.data_table.id != "columns":
            return
        for column in self.dataset.columns:
            event.data_table.update_cell(
                column.id, "marker", ">" if column.id == event.row_key.value else ""
            )
        profile = self.schema.profile(event.row_key.value)
        warnings = " ".join(WARNINGS[code] for code in profile.warnings)
        note = self.query_one("#column-note", Static)
        note.set_class(bool(warnings), "warning")
        note.update(
            snippet(
                "Warning: " + warnings
                if warnings
                else "? shows full column details and samples.",
                max(20, self.app.size.width - 4),
            )
        )

    def context_help(self, focused):
        if not isinstance(focused, DataTable):
            return None
        if focused.id == "columns":
            index = focused.cursor_row
            column, profile = self.dataset.columns[index], self.schema.columns[index]
            shown = self.view["columns"][index]
            samples = (
                "\n".join(visible_text(value) for value in profile.samples) or "None"
            )
            warnings = "\n".join(WARNINGS[code] for code in profile.warnings) or "None"
            return (
                "Column details",
                f"{visible_text(column.name)}\n"
                f"Effective type: {profile.effective.value}\n"
                f"Detected type: {profile.detected.value}\n"
                f"Override: {'Yes' if profile.overridden else 'No'}\n"
                f"Missing: {profile.missing_count} ({shown['missing_percent']:.1f}%)\n"
                f"Distinct nonmissing values: {profile.distinct_count}\n"
                f"First three distinct present samples:\n{samples}\n\n"
                f"Warnings:\n{warnings}\n\n{CATALOG['preview'][1]}",
            )
        row, col = focused.cursor_coordinate
        if col == 0:
            return "Data row", f"Logical data row {row + 1}. {self.view['label']}."
        cell = self.dataset.rows[row][col - 1]
        column = self.dataset.columns[col - 1]
        value = "Missing value" if cell.missing else visible_text(cell.raw_text)
        return (
            "Full cell value",
            f"Data row {row + 1} · {visible_text(column.name)}\n"
            f"{'Missing' if cell.missing else 'Present'} · Source kind: "
            f"{cell.source_kind.value}\n\n{value}",
        )

    def on_data_table_cell_selected(self, event: DataTable.CellSelected):
        self.app.action_help()

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        self.app.action_help()

    def refresh_schema(self):
        state = self.app.service.snapshot
        self.schema = state.schema
        self.view = preview(self.dataset, self.schema, text_limit=80)
        columns = self.query_one("#columns", DataTable)
        for column in self.view["columns"]:
            for key, value in {
                "type": column["type"] + (" *" if column["overridden"] else ""),
                "missing": (
                    f"{column['missing_count']} ({column['missing_percent']:.1f}%)"
                ),
                "unique": str(column["distinct_count"]),
                "samples": snippet(" · ".join(column["samples"]), 10),
            }.items():
                columns.update_cell(column["id"], key, value)
        overrides = sum(p.overridden for p in self.schema.columns)
        warnings = sum(bool(p.warnings) for p in self.schema.columns)
        self.query_one("#summary", Static).update(
            f"{len(self.dataset.rows):,} rows · {len(self.dataset.columns)} columns · "
            f"{overrides} overrides · {warnings} columns with notes"
        )
        self.query_one("#correct", Button).disabled = state.confirmed
        self.query_one("#status", Static).update(
            "[x] Dataset confirmed. Chosen types accepted; ready to choose a goal."
            if state.confirmed
            else self.status
        )
        self.on_data_table_row_highlighted(
            DataTable.RowHighlighted(
                columns,
                columns.cursor_row,
                columns.ordered_rows[columns.cursor_row].key,
            )
        )

    def actions(self):
        yield Action("Looks correct", id="correct", variant="primary")
        yield Action("Change type", id="change-type")
        yield Action("Preview is not correct", id="prepare")
        yield Action("Choose another dataset", id="another")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "change-type":
            index = self.query_one("#columns", DataTable).cursor_row
            self.app.push_screen(TypeReview(self, self.dataset.columns[index].id))
        elif event.button.id == "correct":
            self.app.service.confirm_schema()
            self.refresh_schema()
        elif event.button.id == "prepare":
            self.app.push_screen(Prepare(self.dataset.source_format))
        else:
            self.app.return_to_load()


class TypeReview(Frame):
    heading = "Change column type"
    help_topic = "types"
    status = (
        "Enter applies a type. Reset restores detection; source values never change."
    )

    def __init__(self, owner, column_id):
        super().__init__()
        self.owner, self.column_id = owner, column_id

    def content(self):
        state = self.app.service.snapshot
        column = next(c for c in state.dataset.columns if c.id == self.column_id)
        profile = state.schema.profile(self.column_id)
        yield Static(visible_text(column.name), markup=False)
        yield Static(
            f"Detected: {profile.detected.value} · Current: {profile.effective.value}",
            markup=False,
        )
        yield OptionList(
            *(
                Option(
                    f"{'[x]' if kind == profile.effective else '[ ]'} {kind.value}",
                    id=kind.value,
                )
                for kind in ColumnType
                if kind != ColumnType.UNKNOWN
            ),
            Option("Reset to detected type", id="reset"),
            id="types",
            markup=False,
        )
        yield Static(
            "Category keeps lexical text; mixed JSON scalar kinds become strings.",
            classes="muted",
            markup=False,
        )
        yield Static("", id="error", classes="error", markup=False)

    def on_mount(self):
        choices = self.query_one("#types", OptionList)
        profile = self.app.service.snapshot.schema.profile(self.column_id)
        kinds = [kind for kind in ColumnType if kind != ColumnType.UNKNOWN]
        choices.highlighted = (
            kinds.index(profile.effective) if profile.effective in kinds else len(kinds)
        )
        choices.focus()

    def actions(self):
        yield Action("Back", id="back")

    def on_button_pressed(self, event: Button.Pressed):
        self.app.action_back()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        kind = None if event.option_id == "reset" else event.option_id
        self.app.confirm_discard(lambda discard: self.apply_type(kind, discard=discard))

    @work(group="schema", exclusive=True)
    async def apply_type(self, kind, *, discard=False):
        await self.app.push_screen(
            Busy("Checking every present value", heading="Checking column type")
        )
        try:
            accepted = await self.app.service.change_type(
                self.column_id, kind, discard=discard
            )
            message = operation_message(
                self.app.service.snapshot, "Change stopped. Choose a type or go Back."
            )
        except DomainError as error:
            accepted, message = False, f"{error.message} {error.action}"

        def finish():
            self.app.pop_screen()
            if accepted:
                self.app.pop_screen()
                self.owner.refresh_schema()
            else:
                self.query_one("#error", Static).update(f"Error: {message}")
                self.query_one("#types").focus()

        self.app.after_modal(finish)
