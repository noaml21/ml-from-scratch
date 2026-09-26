"""Full-screen presentation and navigation over one application service."""

from textual import events, work
from textual.app import App
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import Input, TextArea

from mlforge.application.service import Service
from mlforge.application.state import Activity
from mlforge.contracts import CandidateStatus
from mlforge.tui.help import CATALOG
from mlforge.tui.screens.dataset import Load, Welcome
from mlforge.tui.screens.results import Results
from mlforge.tui.screens.shell import Confirm, Help, ResizeGuard


class MLForgeApp(App):
    TITLE = "MLForge"
    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = "theme.tcss"
    BINDINGS = [
        Binding("question_mark", "letter_help", "Help"),
        Binding("f1", "help", "Help"),
        Binding("b", "letter_back", "Back"),
        Binding("escape", "back", "Back", show=False),
        Binding("q", "letter_quit", "Quit", show=False),
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", "Quit", priority=True, show=False),
    ]

    def __init__(self, service: Service):
        super().__init__()
        self.service = service
        self._guard = None
        self._pending = None
        self._quitting = False
        self.register_theme(
            Theme(
                name="mlforge",
                primary="#66D9C3",
                accent="#66D9C3",
                foreground="#E6EEF3",
                background="#101820",
                surface="#182630",
                panel="#223642",
                success="#66D9C3",
                warning="#F3C477",
                error="#FF8A91",
                text_alpha=1,
                variables={
                    "text": "#E6EEF3",
                    "text-muted": "#AEC0CC",
                    "text-disabled": "#AEC0CC",
                    "border": "#526975",
                    "block-cursor-foreground": "#E6EEF3",
                    "block-cursor-background": "#244247",
                    "footer-background": "#182630",
                    "footer-foreground": "#E6EEF3",
                    "footer-key-foreground": "#66D9C3",
                },
            )
        )
        self.theme = "mlforge"

    async def on_mount(self):
        await self.service.__aenter__()
        await self.push_screen(Welcome())
        self._resize()

    async def on_unmount(self):
        await self.service.close()

    def check_action(self, action, parameters):
        editing = isinstance(self.focused, (Input, TextArea))
        if action in {"focus_next", "focus_previous"}:
            return not isinstance(self.screen, Welcome) and bool(
                self.screen.focus_chain
            )
        if action.startswith("letter_"):
            if editing or isinstance(self.screen, (ModalScreen, ResizeGuard)):
                return False
            if action == "letter_back" and isinstance(self.screen, Welcome):
                return False
        if action == "help":
            return editing and not isinstance(self.screen, (ModalScreen, ResizeGuard))
        return True

    def action_letter_help(self):
        self.action_help()

    def action_help(self):
        if isinstance(self.screen, (ModalScreen, ResizeGuard)):
            return
        detail = getattr(self.screen, "context_help", lambda _: None)(self.focused)
        if detail is not None:
            self.push_screen(Help(*detail), lambda _: self._resume())
            return
        topic = getattr(self.focused, "id", None)
        if topic not in CATALOG:
            topic = getattr(self.screen, "help_topic", "welcome")
        self.push_screen(Help(*CATALOG[topic]), lambda _: self._resume())

    def confirm_discard(self, change):
        if not self.service.snapshot.results:
            change(False)
        else:
            self.push_screen(
                Confirm(
                    "Discard current results?",
                    "Changing data or experiment choices discards current results.",
                    accept="Discard results",
                    keep="Keep results",
                ),
                lambda accepted: change(True) if accepted else None,
            )

    def return_to_load(self):
        """Return to the existing chooser without replacing accepted session state."""
        while not isinstance(self.screen, (Load, Welcome)):
            self.pop_screen()

    def return_to_results(self):
        """Leave Try/Export guidance without changing the accepted selection."""
        while not isinstance(self.screen, Results):
            self.pop_screen()

    def action_letter_back(self):
        self.action_back()

    def action_back(self):
        if isinstance(self.focused, (Input, TextArea)):
            self.screen.focus_next()
            return
        if isinstance(self.screen, (ModalScreen, ResizeGuard, Welcome)):
            return
        if self.service.snapshot.activity == Activity.SAVING:
            return
        if self.service.snapshot.activity != Activity.IDLE:
            self.push_screen(
                Confirm(
                    "Stop this operation?",
                    "Cancel and wait for owned work to stop before going back.",
                    accept="Cancel and go back",
                ),
                lambda accepted: self._cancel_back(accepted),
            )
        else:
            self.pop_screen()

    def _cancel_back(self, accepted):
        if accepted:
            self.screen.cancel_and_back()
        self._resume()

    def action_letter_quit(self):
        self.action_quit()

    def action_quit(self):
        if self._quitting or isinstance(self.screen, Confirm):
            return
        state = self.service.snapshot
        if state.activity == Activity.SAVING:
            self.push_screen(
                Confirm(
                    "Finish save and quit?",
                    "The prompt save and temporary-file cleanup "
                    "will finish before closing.",
                    accept="Finish and quit",
                    keep="Stay here",
                ),
                self._confirm_quit,
            )
        elif state.activity not in (Activity.IDLE, Activity.CLOSED):
            self.push_screen(
                Confirm(
                    "Quit MLForge?",
                    "The current operation will stop and owned temporary files "
                    "will be cleaned up before leaving.",
                ),
                self._confirm_quit,
            )
        elif (
            any(c.status == CandidateStatus.COMPLETED for c in state.results)
            and not state.exported_path
        ):
            self.push_screen(
                Confirm(
                    "Quit without exporting?",
                    "This session is not saved. Your unexported models will be lost.",
                    accept="Quit",
                    keep="Stay here",
                ),
                self._confirm_quit,
            )
        else:
            self.close_session()

    def _confirm_quit(self, accepted):
        if accepted:
            self.close_session()
        else:
            self._resume()

    @work(group="quit", exclusive=True)
    async def close_session(self):
        self._quitting = True
        await self.service.close()
        self.exit()

    def on_resize(self, event: events.Resize):
        if self.is_running and self.screen_stack:
            self.call_after_refresh(self._resize)

    def _resize(self):
        if self._quitting:
            return
        small = self.size.width < 80 or self.size.height < 24
        if small and self._guard is None:
            self._guard = ResizeGuard()
            self.push_screen(self._guard)
        elif self._guard is self.screen:
            if small:
                self._guard.update_dimensions()
            else:
                self._guard = None
                self.pop_screen()
                self.call_after_refresh(self._resume)

    def after_modal(self, callback):
        """Do not replace help or its focused content when background work finishes."""
        if self._quitting:
            return
        if isinstance(self.screen, (ModalScreen, ResizeGuard)):
            self._pending = callback
        else:
            callback()

    def _resume(self):
        self._resize()
        if self._pending and not isinstance(self.screen, (ModalScreen, ResizeGuard)):
            callback, self._pending = self._pending, None
            callback()
