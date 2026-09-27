"""Typed Try form. The application runs the selected bundle's shared runtime."""

from textual import work
from textual.containers import Horizontal, Vertical
from textual.suggester import SuggestFromList
from textual.widgets import Button, Checkbox, Input, Select, Static

from mlforge.contracts import DomainError, TaskKind
from mlforge.datasets.records import visible_text
from mlforge.tui.screens.shell import (
    Action,
    Busy,
    Frame,
    Toggle,
    operation_message,
)

KNOWN_SHOWN = 8


def number(value):
    return format(value, ".6g")


def field_hint(field):
    if field.kind == "Number":
        if field.minimum is None:
            return "Number · no observed training values; Missing uses the fallback."
        return (
            f"Number · training range {number(field.minimum)} to "
            f"{number(field.maximum)}; other values get a warning, not clipping."
        )
    if field.kind == "Boolean":
        return "Boolean · choose true or false."
    known = [visible_text(value) for value in field.categories]
    shown = ", ".join(known[:KNOWN_SHOWN])
    more = f" (+{len(known) - KNOWN_SHOWN} more)" if len(known) > KNOWN_SHOWN else ""
    return (
        f"Category · known: {shown}{more}. New text is allowed."
        if known
        else "Category · new text uses the fitted unknown-category encoding."
    )


def output_text(task, row):
    if task == TaskKind.CLASSIFICATION:
        return f"Prediction: {visible_text(row['prediction'])}"
    if task == TaskKind.REGRESSION:
        return f"Prediction: {number(row['prediction'])}"
    if task == TaskKind.CLUSTERING:
        return f"Cluster {row['cluster']} · cluster IDs are arbitrary labels."
    return "Components: " + " · ".join(
        f"PC{index} {number(value)}"
        for index, value in enumerate(row["components"], start=1)
    )


class Trial(Frame):
    stage = "Results"
    heading = "Try the model"
    help_topic = "try"
    status = "Uses the exact evaluated pipeline; trying never retrains."

    def __init__(self, fields, task):
        super().__init__()
        self.fields, self.goal = tuple(fields), task
        self.attempts = 0

    def content(self):
        yield Static(
            "Enter one value per input, or mark it Missing.",
            classes="muted",
            markup=False,
        )
        for index, field in enumerate(self.fields):
            with Vertical(classes="try-field"):
                yield Static(
                    visible_text(field.name), classes="field-name", markup=False
                )
                yield Static(field_hint(field), classes="muted", markup=False)
                with Horizontal(classes="try-row"):
                    if field.kind == "Boolean":
                        yield Select(
                            [("true", "true"), ("false", "false")],
                            prompt="Choose true or false",
                            id=f"value-{index}",
                        )
                    else:
                        yield Input(
                            placeholder="Number" if field.kind == "Number" else "Text",
                            id=f"value-{index}",
                            suggester=SuggestFromList(
                                field.categories, case_sensitive=True
                            )
                            if field.categories
                            else None,
                        )
                    yield Toggle("Missing", id=f"missing-{index}")
                yield Static("", id=f"error-{index}", classes="error", markup=False)
        yield Static("", id="result", classes="result", markup=False)
        yield Static("", id="warnings", classes="warning", markup=False)
        yield Static("", id="error", classes="error", markup=False)

    def actions(self):
        yield Action("Predict", id="predict", variant="primary")
        yield Action("Back to model", id="back")

    def on_mount(self):
        self.query_one("#value-0").focus()

    def context_help(self, focused):
        index = self._index(focused)
        if index is None:
            return None
        field = self.fields[index]
        return (
            visible_text(field.name),
            field_hint(field)
            + "\n\nMissing uses the default learned from training rows. The value "
            "is sent exactly as entered to the same runtime used by the exported "
            "package; nothing is retrained.",
        )

    def _index(self, widget):
        name = getattr(widget, "id", None) or ""
        prefix, _, number = name.partition("-")
        if prefix in ("value", "missing") and number.isdigit():
            return int(number)
        return None

    def record(self):
        values = {}
        for index, field in enumerate(self.fields):
            if self.query_one(f"#missing-{index}", Checkbox).value:
                values[field.name] = None
                continue
            control = self.query_one(f"#value-{index}")
            value = control.value
            values[field.name] = "" if value is Select.NULL else value
        return values

    def on_checkbox_changed(self, event: Checkbox.Changed):
        index = self._index(event.checkbox)
        if index is not None:
            self.query_one(f"#value-{index}").disabled = event.value

    def on_input_submitted(self, event: Input.Submitted):
        self.predict()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "predict":
            self.predict()
        else:
            self.app.action_back()

    @work(group="predict", exclusive=True)
    async def predict(self):
        record = self.record()
        for index in range(len(self.fields)):
            self.query_one(f"#error-{index}", Static).update("")
        for name in ("result", "warnings", "error"):
            self.query_one(f"#{name}", Static).update("")
        await self.app.push_screen(Busy("Selected model", heading="Predicting"))
        try:
            prediction = await self.app.service.predict([record])
            state = self.app.service.snapshot
            failure = state.failure
            message = operation_message(state, "Prediction stopped. Retry or go Back.")
        except DomainError as error:
            prediction, failure = None, None
            message = f"{error.message} {error.action}"

        def finish():
            self.app.pop_screen()
            self.attempts += 1
            if prediction is not None:
                row = prediction.data[0]
                self.query_one("#result", Static).update(output_text(self.goal, row))
                self.query_one("#warnings", Static).update(
                    "\n".join(
                        "Warning: "
                        + (visible_text(w["field"]) + ": " if w["field"] else "")
                        + w["message"]
                        for w in row["warnings"]
                    )
                )
                self.query_one("#predict").focus()
                return
            names = [field.name for field in self.fields]
            if failure is not None and failure.column in names:
                index = names.index(failure.column)
                self.query_one(f"#error-{index}", Static).update(
                    f"Error: {failure.message}"
                )
                control = self.query_one(f"#value-{index}")
                target = (
                    self.query_one(f"#missing-{index}") if control.disabled else control
                )
                target.focus()
                target.scroll_visible()
            else:
                self.query_one("#error", Static).update(f"Error: {message}")
                self.query_one("#predict").focus()

        self.app.after_modal(finish)
