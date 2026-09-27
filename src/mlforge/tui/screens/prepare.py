"""Local structural guidance through application commands; never contact AI."""

from textual import work
from textual.widgets import Button, Input, Static, TextArea

from mlforge.contracts import DomainError
from mlforge.datasets.records import visible_text
from mlforge.tui.screens.shell import Action, Frame


class Prepare(Frame):
    heading = "Prepare with AI"
    help_topic = "prepare"
    status = "Generated locally. No data included or sent. Tab moves to Copy/Save."

    def __init__(self, source_format=None, diagnostic="PREVIEW"):
        super().__init__()
        self.source_format, self.diagnostic = source_format, diagnostic

    def content(self):
        self.prompt = self.app.service.preparation_text(
            self.source_format, self.diagnostic
        )
        yield Static(
            "You decide what to share externally. MLForge contacts no service.",
            classes="muted",
            markup=False,
        )
        yield TextArea(
            self.prompt,
            read_only=True,
            soft_wrap=True,
            show_line_numbers=False,
            id="prompt",
        )
        yield Static(
            "Copy depends on terminal support. Select text or Save if unavailable.",
            classes="muted",
            markup=False,
        )
        yield Static("", id="message", markup=False)

    def on_mount(self):
        self.query_one("#prompt").focus()

    def actions(self):
        yield Action("Copy prompt", id="copy", variant="primary")
        yield Action("Save prompt as .txt", id="save")
        yield Action("Back", id="back")
        yield Action("Choose another dataset", id="another")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "copy":
            message = self.query_one("#message", Static)
            try:
                self.app.copy_to_clipboard(self.prompt)
            except (OSError, RuntimeError, NotImplementedError):
                message.add_class("message-error")
                message.update(
                    "Error: Clipboard unavailable. Select the text or save it as .txt."
                )
            else:
                message.remove_class("message-error")
                message.update(
                    "Copy requested. If your terminal blocks clipboard access, "
                    "use Save."
                )
        elif event.button.id == "save":
            self.app.push_screen(SavePrompt(self.source_format, self.diagnostic))
        elif event.button.id == "another":
            self.app.return_to_load()
        else:
            self.app.action_back()


class SavePrompt(Frame):
    heading = "Save preparation prompt"
    help_topic = "prepare"
    status = "Choose a new .txt file. Existing files are never overwritten."

    def __init__(self, source_format, diagnostic):
        super().__init__()
        self.source_format, self.diagnostic = source_format, diagnostic
        self.saving = False

    def content(self):
        yield Static("Destination", markup=False)
        yield Input(value="mlforge-preparation.txt", id="destination")
        yield Static("", id="message", markup=False)

    def on_mount(self):
        self.query_one("#destination").focus()

    def actions(self):
        yield Action("Save prompt", id="write", variant="primary")
        yield Action("Back", id="back")

    def on_input_submitted(self, event: Input.Submitted):
        self.save()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "write":
            self.save()
        else:
            self.app.action_back()

    @work(group="save-prompt")
    async def save(self):
        if self.saving:
            return
        self.saving = True
        field = self.query_one("#destination", Input)
        destination = field.value
        field.disabled = True
        self.query_one("#write", Button).disabled = True
        self.query_one("#back", Button).disabled = True
        self.query_one("#status", Static).update(
            "Saving prompt… Back is unavailable until publication finishes."
        )
        try:
            path = await self.app.service.save_preparation(
                destination, self.source_format, self.diagnostic
            )
            message = f"[x] Saved prompt: {visible_text(str(path))}"
        except DomainError as error:
            message = f"Error: {error.message} {error.action}"

        def finish():
            self.saving = False
            field.disabled = False
            self.query_one("#write", Button).disabled = False
            self.query_one("#back", Button).disabled = False
            output = self.query_one("#message", Static)
            output.set_class(message.startswith("Error:"), "message-error")
            output.set_class(message.startswith("[x]"), "message-success")
            output.update(message)
            self.query_one("#status", Static).update(self.status)
            field.focus()

        self.app.after_modal(finish)
