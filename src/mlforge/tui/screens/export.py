"""Export form and success guidance; the application owns building and publication."""

import json
import shlex
from pathlib import Path

from textual import work
from textual.widgets import Button, Input, Static, TextArea

from mlforge.contracts import DomainError, TaskKind
from mlforge.tui.screens.shell import Action, Busy, Frame, operation_message

FIELD_ERRORS = {
    "PACKAGE_NAME": "module",
    "PACKAGE_VERSION": "version",
    "EXPORT_EXISTS": "destination",
    "EXPORT_IO": "destination",
    "OWNERSHIP": "destination",
}


def python_minor(candidate):
    version = json.loads(candidate.bundle.metadata_json)["python_version"]
    return ".".join(version.split(".")[:2])


def install_path(path):
    """A short relative path when commands run from the current folder."""
    path, here = Path(path), Path.cwd()
    return str(path.relative_to(here)) if path.is_relative_to(here) else str(path)


def usage_text(path, module_name, task, fields, minor):
    example = {}
    for field in fields:
        if field.kind == "Number":
            example[field.name] = field.minimum if field.minimum is not None else None
        elif field.categories:
            example[field.name] = field.categories[0]
        else:
            example[field.name] = None
    call = "transform" if task == TaskKind.REDUCTION else "predict"
    output = {
        TaskKind.CLASSIFICATION: '{"prediction": "<label>", "warnings": [...]}',
        TaskKind.REGRESSION: '{"prediction": <number>, "warnings": [...]}',
        TaskKind.CLUSTERING: '{"cluster": <arbitrary group ID>, "warnings": [...]}',
        TaskKind.REDUCTION: '{"components": [<float>, ...], "warnings": [...]}',
    }[task]
    return "\n".join(
        [
            f"Created: {path}",
            "",
            f"From {Path.cwd()}, install into a fresh Python {minor} "
            "virtual environment on Linux x86_64:",
            f"  python{minor} -m venv model-env",
            "  . model-env/bin/activate",
            f"  python -m pip install {shlex.quote(install_path(path))}",
            "",
            "Use it from Python:",
            f"  from {module_name} import Predictor",
            "  model = Predictor()",
            f"  result = model.{call}({example!r})",
            f"  # {output}",
            "",
            "Use None for a missing value. Batch calls use "
            f"model.{call}_many([...]) with up to 1,000 records.",
        ]
    )


class ExportPackage(Frame):
    stage = "Export"
    heading = "Export package"
    help_topic = "export"
    status = "Builds locally without network access. Nothing is uploaded."

    def __init__(self, fields):
        super().__init__()
        self.fields = tuple(fields)
        self.attempts = 0

    def content(self):
        state = self.app.service.snapshot
        options = state.export_options
        yield Static("Destination folder", classes="field-name", markup=False)
        yield Input(str(Path.cwd() / "exports"), id="destination")
        yield Static("", id="error-destination", classes="error", markup=False)
        yield Static("Python module name", classes="field-name", markup=False)
        yield Input(options.module_name if options else "my_model", id="module")
        yield Static(
            "3–50 lowercase letters, digits or underscores; start with a letter.",
            classes="muted",
            markup=False,
        )
        yield Static("", id="error-module", classes="error", markup=False)
        yield Static("Version", classes="field-name", markup=False)
        yield Input(options.version if options else "1.0.0", id="version")
        yield Static("", id="error-version", classes="error", markup=False)
        yield Static(
            "The wheel contains the fitted model, input names, learned categories "
            "and labels, never your original rows. Learned values can still reveal "
            "information about the data. It supports Python "
            f"{python_minor(state.selected)} on Linux x86_64 with exact pinned "
            "dependencies. Existing files are never replaced.",
            classes="muted",
            markup=False,
        )
        yield Static("", id="error", classes="error", markup=False)

    def actions(self):
        yield Action("Build wheel", id="build", variant="primary")
        yield Action("Back to model", id="back")

    def on_mount(self):
        self.query_one("#destination").focus()

    def on_input_submitted(self, event: Input.Submitted):
        self.build()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "build":
            self.build()
        else:
            self.app.action_back()

    @work(group="export", exclusive=True)
    async def build(self):
        values = {
            name: self.query_one(f"#{name}", Input).value
            for name in ("destination", "module", "version")
        }
        for name in ("error-destination", "error-module", "error-version", "error"):
            self.query_one(f"#{name}", Static).update("")
        await self.app.push_screen(Busy(values["module"], heading="Building wheel"))
        code = None
        try:
            path = await self.app.service.export(
                values["destination"], values["module"], values["version"]
            )
            state = self.app.service.snapshot
            code = state.failure.code if state.failure else state.error_code
            message = operation_message(state, "Export stopped. Nothing was published.")
        except DomainError as error:
            path, code = None, error.code
            message = f"{error.message} {error.action}"

        def finish():
            self.app.pop_screen()
            self.attempts += 1
            if path is not None:
                state = self.app.service.snapshot
                self.app.push_screen(
                    ExportDone(
                        usage_text(
                            path,
                            values["module"],
                            state.selected.bundle.task,
                            self.fields,
                            python_minor(state.selected),
                        )
                    )
                )
                return
            field = FIELD_ERRORS.get(code)
            self.query_one(f"#error-{field}" if field else "#error", Static).update(
                f"Error: {message}"
            )
            self.query_one(f"#{field}" if field else "#build").focus()

        self.app.after_modal(finish)


class ExportDone(Frame):
    stage = "Export"
    heading = "Package created"
    help_topic = "export-done"
    status = "The exact evaluated pipeline was exported without retraining."

    def __init__(self, usage):
        super().__init__()
        self.usage = usage

    def content(self):
        yield TextArea(self.usage, read_only=True, id="usage", soft_wrap=True)

    def actions(self):
        yield Action("Back to results", id="results", variant="primary")
        yield Action("Quit", id="quit")

    def on_mount(self):
        self.query_one("#results").focus()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "quit":
            self.app.action_quit()
            return
        self.app.return_to_results()
