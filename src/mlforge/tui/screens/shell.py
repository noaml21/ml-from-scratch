"""Shared screen structure, help/confirmation and size guard."""

from textual import events
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Static


class Action(Button):
    """Compact action with a focus marker that remains visible without color."""

    def __init__(self, label, **kwargs):
        self.caption = label
        super().__init__(f"  {label}", **kwargs)

    def on_focus(self, event: events.Focus):
        self.label = f"> {self.caption}"

    def on_blur(self, event: events.Blur):
        self.label = f"  {self.caption}"


class Frame(Screen):
    BINDINGS = [
        Binding("tab", "app.focus_next", "Next"),
        Binding("shift+tab", "app.focus_previous", "Previous"),
    ]
    help_topic = "welcome"
    heading = ""
    status = ""

    @property
    def active_bindings(self):
        def order(item):
            action = item[1].binding.action
            if "quit" in action:
                return 4
            if "back" in action:
                return 3
            if "help" in action:
                return 2
            return 0 if "focus" in action else 1

        return dict(sorted(super().active_bindings.items(), key=order))

    def content(self):
        return ()

    def actions(self):
        return ()

    def compose(self):
        yield Static(
            "MLForge · [Dataset] / Goal / Training / Results / Export",
            id="stage",
            markup=False,
        )
        with VerticalScroll(id="body", can_focus=False):
            yield Static(self.heading, classes="heading", markup=False)
            yield from self.content()
        with Horizontal(id="actions"):
            yield from self.actions()
        yield Static(self.status, id="status", markup=False)
        yield Footer()


class Help(ModalScreen):
    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, title, text):
        super().__init__()
        self.title_text, self.body_text = title, text

    def compose(self):
        with Container(classes="dialog"):
            yield Static(self.title_text, classes="heading", markup=False)
            with VerticalScroll(classes="dialog-body", can_focus=True):
                yield Static(self.body_text, markup=False)
            with Horizontal(classes="dialog-actions"):
                yield Action("Close", id="close", variant="primary")

    def on_mount(self):
        self.query_one("#close").focus()

    def action_close(self):
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed):
        self.action_close()


class Confirm(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "keep", "Keep running")]

    def __init__(self, title, text, accept="Cancel and quit", keep="Keep running"):
        super().__init__()
        self.title_text, self.body_text = title, text
        self.accept_text, self.keep_text = accept, keep

    def compose(self):
        with Container(classes="dialog"):
            yield Static(self.title_text, classes="heading", markup=False)
            with VerticalScroll(classes="dialog-body"):
                yield Static(self.body_text, markup=False)
            with Horizontal(classes="dialog-actions"):
                yield Action(self.keep_text, id="keep", variant="primary")
                yield Action(self.accept_text, id="accept")

    def on_mount(self):
        self.query_one("#keep").focus()

    def action_keep(self):
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(event.button.id == "accept")


class ResizeGuard(Screen):
    BINDINGS = [Binding("escape", "cancel", "Cancel work")]

    def compose(self):
        yield Static("Resize to at least 80 × 24", classes="heading", markup=False)
        yield Static("", id="dimensions", markup=False)
        yield Static("Esc: cancel active work · Ctrl+Q: quit", markup=False)

    def on_mount(self):
        self.update_dimensions()

    def update_dimensions(self):
        size = self.app.size
        self.query_one("#dimensions", Static).update(
            f"Current size: {size.width} × {size.height}. Your work is preserved."
        )

    def action_cancel(self):
        self.app.service.cancel()
