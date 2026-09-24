"""Initial real manual-load route; parsing belongs to the application worker."""

import time

from textual import work
from textual.binding import Binding
from textual.widgets import Button, Input, Static

from mlforge.application.state import Activity
from mlforge.contracts import DomainError
from mlforge.tui.screens.shell import Action, Frame


class Welcome(Frame):
    BINDINGS = [Binding("enter", "begin", "Begin")]
    heading = "MLForge"
    help_topic = "welcome"

    def content(self):
        yield Static("Build useful machine learning models locally.", markup=False)
        yield Static("Your data stays on your machine.", classes="muted", markup=False)
        yield Static("Press Enter to begin", id="begin", markup=False)

    def action_begin(self):
        self.app.push_screen(Load())


class Load(Frame):
    heading = "Load dataset"
    help_topic = "load"
    status = "Choose a local file. Your original data stays unchanged."

    def content(self):
        yield Static("Enter a local file path", markup=False)
        yield Input(placeholder="Local CSV, TSV, or JSONL path", id="path")
        yield Static("", id="error", classes="error", markup=False)

    def actions(self):
        yield Action("Load dataset", id="load", variant="primary")
        yield Action("Back", id="back")

    def on_mount(self):
        self.query_one("#path").focus()

    def on_input_submitted(self, event: Input.Submitted):
        self.start_load()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "load":
            self.start_load()
        else:
            self.app.action_back()

    def fail(self, message):
        self.query_one("#error", Static).update(f"Error: {message}")
        self.query_one("#path").focus()

    def start_load(self):
        path = self.query_one("#path", Input).value
        if not path:
            self.fail("Enter a local path, then choose Load dataset.")
            return
        self.query_one("#error", Static).update("")
        self.load(path)

    @work(group="dataset", exclusive=True)
    async def load(self, path):
        await self.app.push_screen(Busy())
        try:
            accepted = await self.app.service.load(path)
            failure = self.app.service.snapshot.failure
            message = (
                f"{failure.message} {failure.action}"
                if failure
                else "Loading stopped. Edit the path or choose Load dataset to retry."
            )
        except DomainError as error:
            accepted = False
            message = f"{error.message} {error.action}"

        def finish():
            if accepted:
                self.app.switch_screen(Preview())
            else:
                self.app.pop_screen()
                self.fail(message)

        self.app.after_modal(finish)


class Busy(Frame):
    heading = "Loading dataset"
    help_topic = "busy"
    status = "Working locally. Help and cancellation remain available."

    def content(self):
        yield Static("Parsing data · 0.0s", id="progress", markup=False)

    def actions(self):
        yield Action("Cancel", id="cancel", variant="primary")

    def on_mount(self):
        self.started = time.monotonic()
        self.query_one("#cancel").focus()
        self.set_interval(0.1, self.update_progress)

    def update_progress(self):
        state = self.app.service.snapshot
        phase = (
            "Stopping…"
            if state.activity == Activity.CANCELLING
            else "Completed"
            if state.activity == Activity.IDLE
            else (state.active.phase if state.active else None) or "Parsing data"
        )
        marker = "·" if int((time.monotonic() - self.started) * 4) % 2 else "•"
        self.query_one("#progress", Static).update(
            f"{marker} {phase} · {time.monotonic() - self.started:.1f}s"
        )

    def on_button_pressed(self, event: Button.Pressed):
        self.app.service.cancel()


class Preview(Frame):
    heading = "Review your dataset"
    help_topic = "preview"
    status = "Review the column types before confirming this dataset."

    def content(self):
        state = self.app.service.snapshot
        yield Static(
            f"{len(state.dataset.rows):,} rows · {len(state.dataset.columns)} columns",
            id="summary",
            markup=False,
        )
        for column, profile in zip(
            state.dataset.columns, state.schema.columns, strict=True
        ):
            yield Static(
                f"{column.name} · {profile.effective.value} · "
                f"{profile.missing_count} missing",
                markup=False,
            )

    def actions(self):
        yield Action("Choose another dataset", id="another", variant="primary")

    def on_button_pressed(self, event: Button.Pressed):
        self.app.action_back()
