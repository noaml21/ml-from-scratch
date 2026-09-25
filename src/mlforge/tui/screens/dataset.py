"""Local source selection; parsing belongs to the application worker."""

from pathlib import Path

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.content import Content
from textual.message import Message
from textual.widgets import Button, Checkbox, DirectoryTree, Input, OptionList, Static
from textual.widgets.option_list import Option

from mlforge.contracts import DomainError
from mlforge.datasets.records import visible_text
from mlforge.tui.screens.prepare import Prepare
from mlforge.tui.screens.preview import Preview
from mlforge.tui.screens.shell import Action, Busy, Frame, operation_message


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

    def show_preparation(self):
        self.app.push_screen(
            Prepare(
                getattr(self, "source_format", None),
                getattr(self, "diagnostic", "PREVIEW"),
            )
        )

    def request_load(self, path, *, example=False):
        self.app.confirm_discard(
            lambda discard: self.load(path, example=example, discard=discard)
        )

    @work(group="dataset", exclusive=True)
    async def load(self, path, *, example=False, discard=False):
        self.source_format = next(
            (
                item.label
                for item in self.app.service.formats
                if item.extension == Path(path).suffix.lower()
            ),
            None,
        )
        await self.app.push_screen(Busy(Path(path).name))
        try:
            accepted = (
                await self.app.service.load_example(path, discard=discard)
                if example
                else await self.app.service.load(path, discard=discard)
            )
            state = self.app.service.snapshot
            self.diagnostic = (
                state.failure.code if state.failure else state.error_code or "PREVIEW"
            )
            message = operation_message(
                state, "Loading stopped. Choose a source or retry the selection."
            )
        except DomainError as error:
            self.diagnostic = error.code
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
        yield Action("Prepare with AI", id="prepare")
        yield Action("Back", id="back")

    def on_mount(self):
        self.query_one("#path").focus()

    def on_input_submitted(self, event: Input.Submitted):
        self.start_load()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "load":
            self.start_load()
        elif event.button.id == "prepare":
            self.show_preparation()
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
        self.request_load(path)


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
        yield Action("Prepare with AI", id="prepare")
        yield Action("Back", id="back")

    def on_mount(self):
        self.query_one("#files").focus()

    def on_checkbox_changed(self, event: Checkbox.Changed):
        tree = self.query_one("#files", LocalTree)
        tree.show_hidden = event.value
        tree.reload()

    def on_local_tree_unreadable(self, event: LocalTree.Unreadable):
        self.diagnostic = "FILE_READ"
        self.fail("Directory is unreadable. Choose Parent folder or go Back.")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected):
        self.request_load(event.path)

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ):
        tree = self.query_one("#files", LocalTree)
        if tree.path != event.path:
            tree.path = event.path
        self.query_one("#directory", Static).update(visible_text(str(event.path)))
        self.query_one("#error", Static).update("")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "prepare":
            self.show_preparation()
        elif event.button.id == "parent":
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
        yield Action("Prepare with AI", id="prepare")
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
        self.request_load(event.option_id, example=True)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "prepare":
            self.show_preparation()
        else:
            self.app.action_back()
