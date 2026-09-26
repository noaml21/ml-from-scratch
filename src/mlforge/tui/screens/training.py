"""Live presentation of one application-owned training run; no process control."""

import time

from rich.text import Text
from textual import work
from textual.widgets import Button, DataTable, Static

from mlforge.application.state import Activity
from mlforge.contracts import CandidateStatus, DomainError
from mlforge.datasets.records import visible_text
from mlforge.tui.screens.results import Results
from mlforge.tui.screens.shell import Action, Frame


class Training(Frame):
    stage = "Training"
    heading = "Training models"
    help_topic = "training"
    status = "Working locally · Help, Cancel and quit remain available"

    def __init__(self, *, discard=False):
        super().__init__()
        self.discard = discard
        self.back_when_stopped = False
        self.finished = False
        self.finished_at = None
        self.start_error = ""

    def content(self):
        yield Static("Preparing data", id="progress", markup=False)
        yield Static("", id="run-summary", markup=False)
        yield DataTable(id="candidates", cursor_type="row", zebra_stripes=False)
        yield Static("", id="error", classes="error", markup=False)

    def actions(self):
        yield Action("Cancel", id="cancel", variant="primary")
        yield Action("Back to models", id="back")

    def on_mount(self):
        self.started = time.monotonic()
        state = self.app.service.snapshot
        self.previous_run_id = state.run.id if state.run else None
        self.model_ids = state.configuration.model_ids
        self.names = {m.id: m.name for m in self.app.service.models}
        table = self.query_one("#candidates", DataTable)
        for title, key, width in [
            ("", "marker", 1),
            ("Model", "model", 26),
            ("Status", "status", 10),
            ("Reason", "reason", 24),
        ]:
            table.add_column(Text(title), key=key, width=width)
        for model_id in self.model_ids:
            table.add_row("", self.names[model_id], "Pending", "", key=model_id)
        self.query_one("#back").display = False
        self.query_one("#cancel").focus()
        self.set_interval(0.1, self.update_progress)
        self.perform()

    @property
    def current_run(self):
        run = self.app.service.snapshot.run
        return run if run and run.id != self.previous_run_id else None

    @work(group="training", exclusive=True)
    async def perform(self):
        try:
            await self.app.service.train(discard=self.discard)
        except DomainError as error:
            self.start_error = f"{error.message} {error.action}"
        self.finished = True
        self.finished_at = time.monotonic()
        self.app.after_modal(self.finish)

    def finish(self):
        self.update_progress()
        if self.back_when_stopped:
            self.app.pop_screen()
            return
        if self.app.service.ranked_results:
            self.app.switch_screen(Results())
            return
        self.query_one("#cancel").display = False
        self.query_one("#back").display = True
        self.query_one("#back").focus()

    def update_progress(self):
        state = self.app.service.snapshot
        run = self.current_run
        active = (
            state.active
            if run and state.active and state.active.identity.run_id == run.id
            else None
        )
        candidates = {c.model_id: c for c in run.candidates} if run else {}
        completed = sum(
            c.status == CandidateStatus.COMPLETED for c in candidates.values()
        )
        failed = sum(c.status == CandidateStatus.FAILED for c in candidates.values())
        busy = not self.finished
        phase = {
            "preparing": "Preparing data",
            "preprocessing": "Preparing model inputs",
            "training": "Training "
            + (
                self.names[active.identity.model_id]
                if active and active.identity.model_id
                else "model"
            ),
            "evaluating": "Evaluating",
            "validating_artifact": "Validating artifact",
        }.get(
            active.phase if active else None,
            (
                "Starting " + self.names[active.identity.model_id]
                if active and active.identity.model_id
                else "Preparing data"
            ),
        )
        if state.activity == Activity.CANCELLING:
            phase = "Stopping training…"
        if self.finished:
            phase = (
                f"Cancelled — {completed} models completed."
                if run and run.cancelled
                else "Training finished with failures"
                if completed and (failed or state.failure)
                else "Training complete"
                if completed
                else "No model completed"
            )
        elapsed = (self.finished_at or time.monotonic()) - self.started
        marker = ("·" if int(elapsed * 4) % 2 else "•") + " " if busy else ""
        self.query_one("#progress", Static).update(f"{marker}{phase} · {elapsed:.1f}s")
        self.query_one("#run-summary", Static).update(
            f"{completed} completed · {failed} failed · "
            f"{len(self.model_ids) - len(candidates)} not completed"
        )
        table = self.query_one("#candidates", DataTable)
        for model_id in self.model_ids:
            candidate = candidates.get(model_id)
            status = (
                (
                    "Completed"
                    if candidate.status == CandidateStatus.COMPLETED
                    else "Failed"
                )
                if candidate
                else (
                    "Running"
                    if active and active.identity.model_id == model_id and busy
                    else "Pending"
                    if busy
                    else "Stopped"
                    if run and run.cancelled
                    else "Not run"
                )
            )
            reason = (
                (candidate.error_message or candidate.error_code or "")
                if candidate
                else ""
            )
            table.update_cell(model_id, "status", status)
            shown_reason = Text(visible_text(reason), no_wrap=True)
            shown_reason.truncate(24, overflow="ellipsis")
            table.update_cell(model_id, "reason", shown_reason)
        message = self.start_error
        if state.failure:
            message = f"{state.failure.message} {state.failure.action}"
        self.query_one("#error", Static).update(f"Error: {message}" if message else "")
        self.query_one("#status", Static).update(
            "Review model status or go Back to adjust choices."
            if self.finished
            else self.status
        )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        for model_id in self.model_ids:
            event.data_table.update_cell(
                model_id, "marker", ">" if model_id == event.row_key.value else ""
            )

    def context_help(self, focused):
        if not isinstance(focused, DataTable):
            return None
        model_id = self.model_ids[focused.cursor_row]
        run = self.current_run
        candidate = (
            next((c for c in run.candidates if c.model_id == model_id), None)
            if run
            else None
        )
        return self.names[model_id], (
            f"{candidate.status.value.capitalize()} · "
            f"{candidate.elapsed:.2f}s\n"
            + visible_text(
                candidate.error_message
                or candidate.error_code
                or (
                    "Evaluated candidate accepted."
                    if candidate.status == CandidateStatus.COMPLETED
                    else "No completed model was accepted."
                )
            )
            if candidate
            else "This model has not produced an accepted result yet."
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        self.app.action_help()

    def cancel_and_back(self):
        self.back_when_stopped = True
        self.app.service.cancel()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel":
            self.app.service.cancel()
        else:
            self.app.action_back()
