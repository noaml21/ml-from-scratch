"""Local source selection; parsing belongs to the application worker."""

import time
from pathlib import Path

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.content import Content
from textual.message import Message
from textual.widgets import Button, Checkbox, DirectoryTree, Input, OptionList, Static
from textual.widgets.option_list import Option

from mlforge.application.state import Activity
from mlforge.contracts import DomainError
from mlforge.datasets.records import visible_text
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
    status = "Choose a source. All data stays on your machine."

    def content(self):
        yield OptionList(
            Option("Browse local files", id="browse"),
            Option("Enter a path", id="path"),
            Option("Example dataset", id="examples"),
            id="sources",
            markup=False,
        )

    def actions(self):
        yield Action("Back", id="back")

    def on_mount(self):
        self.query_one("#sources").focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        screen = {"browse": Browse, "path": PathEntry, "examples": Examples}[
            event.option_id
        ]
        self.app.push_screen(screen())

    def on_button_pressed(self, event: Button.Pressed):
        self.app.action_back()


class Source(Frame):
    help_topic = "load"
    primary_id = "path"

    def fail(self, message):
        self.query_one("#error", Static).update(f"Error: {message}")
        self.query_one(f"#{self.primary_id}").focus()

    @work(group="dataset", exclusive=True)
    async def load(self, path, *, example=False):
        await self.app.push_screen(Busy(Path(path).name))
        try:
            accepted = (
                await self.app.service.load_example(path)
                if example
                else await self.app.service.load(path)
            )
            failure = self.app.service.snapshot.failure
            message = (
                f"{failure.message} {failure.action}"
                if failure
                else "Loading stopped. Choose a source or retry the selection."
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


class PathEntry(Source):
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


class LocalTree(DirectoryTree):
    """Native lazy directory loading, literal labels and explicit read errors."""

    class Unreadable(Message):
        pass

    def __init__(self, path, extensions, **kwargs):
        self.extensions = extensions
        self.show_hidden = False
        super().__init__(path, **kwargs)

    def filter_paths(self, paths):
        for path in paths:
            if not self.show_hidden and path.name.startswith("."):
                continue
            try:
                if path.is_dir() or path.suffix.lower() in self.extensions:
                    yield path
            except OSError:
                continue

    def _directory_content(self, location, worker):
        try:
            for path in location.iterdir():
                if worker.is_cancelled:
                    break
                yield path
        except OSError:
            self.post_message(self.Unreadable())

    def render_label(self, node, base_style, style):
        path = node.data.path if node.data else Path("")
        prefix = (
            ("[-] " if node.is_expanded else "[+] ") if node.allow_expand else "    "
        )
        return Text(
            prefix + visible_text(path.name or str(path)), style=base_style + style
        )


class HiddenFiles(Checkbox):
    """Keep checked state explicit even when terminal color is unavailable."""

    @property
    def _button(self):
        return Content("[x]" if self.value else "[ ]")


class Browse(Source):
    heading = "Browse local files"
    primary_id = "files"
    status = "Enter opens a folder or loads a file. Parent folder goes up one level."

    def content(self):
        yield Static(visible_text(str(Path.cwd())), id="directory", markup=False)
        yield HiddenFiles("Show hidden files", id="hidden")
        yield LocalTree(
            Path.cwd(),
            tuple(item.extension for item in self.app.service.formats),
            id="files",
        )
        yield Static("", id="error", classes="error", markup=False)

    def actions(self):
        yield Action("Parent folder", id="parent", variant="primary")
        yield Action("Back", id="back")

    def on_mount(self):
        self.query_one("#files").focus()

    def on_checkbox_changed(self, event: Checkbox.Changed):
        tree = self.query_one("#files", LocalTree)
        tree.show_hidden = event.value
        tree.reload()

    def on_local_tree_unreadable(self, event: LocalTree.Unreadable):
        self.fail("Directory is unreadable. Choose Parent folder or go Back.")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected):
        self.load(event.path)

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ):
        tree = self.query_one("#files", LocalTree)
        if tree.path != event.path:
            tree.path = event.path
        self.query_one("#directory", Static).update(visible_text(str(event.path)))
        self.query_one("#error", Static).update("")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "parent":
            tree = self.query_one("#files", LocalTree)
            tree.path = tree.path.parent
            self.query_one("#directory", Static).update(visible_text(str(tree.path)))
            self.query_one("#error", Static).update("")
            tree.focus()
        else:
            self.app.action_back()


class Examples(Source):
    heading = "Example dataset"
    primary_id = "examples"
    status = "Synthetic data. Examples use the same import and schema checks."

    def content(self):
        yield OptionList(
            *(
                Option(item.label, id=item.filename)
                for item in self.app.service.examples
            ),
            id="examples",
            markup=False,
        )
        yield Static("", id="example-detail", classes="muted", markup=False)
        yield Static("", id="error", classes="error", markup=False)

    def actions(self):
        yield Action("Back", id="back")

    def on_mount(self):
        self.query_one("#examples").focus()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted):
        example = next(
            e for e in self.app.service.examples if e.filename == event.option_id
        )
        format_name = Path(example.filename).suffix[1:].upper()
        self.query_one("#example-detail", Static).update(
            f"Synthetic · {example.task.value} · {format_name}"
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        self.load(event.option_id, example=True)

    def on_button_pressed(self, event: Button.Pressed):
        self.app.action_back()


class Busy(Frame):
    heading = "Loading dataset"
    help_topic = "busy"
    status = "Working locally. Help and cancellation remain available."

    def __init__(self, filename):
        super().__init__()
        self.filename = visible_text(filename)

    def content(self):
        yield Static(self.filename, markup=False)
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
