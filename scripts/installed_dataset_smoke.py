"""Dataset and training Pilot/PTY gates in isolated application installations."""

import asyncio
import base64
import codecs
import errno
import fcntl
import hashlib
import json
import os
import pty
import re
import select
import signal
import struct
import subprocess
import sys
import termios
import time
import unicodedata
from importlib.resources import files
from pathlib import Path

from textual.widgets import DataTable, Input, Static, TextArea

import mlforge
from mlforge.application.service import Service
from mlforge.application.state import Activity
from mlforge.contracts import TaskKind
from mlforge.datasets.records import ColumnType
from mlforge.tui.app import MLForgeApp
from mlforge.tui.screens.configuration import (
    Features,
    Goal,
    Models,
    Preprocessing,
    Target,
)
from mlforge.tui.screens.dataset import Browse, Load, PathEntry
from mlforge.tui.screens.export import ExportDone, ExportPackage
from mlforge.tui.screens.prepare import Prepare, SavePrompt
from mlforge.tui.screens.preview import Preview, TypeReview
from mlforge.tui.screens.results import Inspection, Results, SelectedModel
from mlforge.tui.screens.shell import Help, ResizeGuard
from mlforge.tui.screens.trial import Trial


async def until(predicate):
    async with asyncio.timeout(30):
        while not predicate():
            await asyncio.sleep(0.02)


async def activate(app, pilot, identifier):
    """Reach actions through the actual keyboard focus order."""
    for _ in range(20):
        if app.focused is not None and app.focused.id == identifier:
            await pilot.press("enter")
            return
        await pilot.press("tab")
    raise AssertionError(f"Unreachable action: {identifier}")


async def quit_app(app, pilot):
    await pilot.press("ctrl+q")
    await until(lambda: app.service.snapshot.activity == Activity.CLOSED)
    assert not app.service._coordinator.root.exists()


async def pilot_journey(evidence):
    examples = Service().examples
    for index, example in enumerate(examples):
        resource = files("mlforge").joinpath("examples", example.filename)
        original = resource.read_bytes()
        app = MLForgeApp(Service())
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("enter", "down", "down", "enter")
            await pilot.press(*(["down"] * index), "enter")
            await until(lambda: isinstance(app.screen, Preview))
            assert len(app.service.snapshot.dataset.rows) >= 60
            assert not app.service.snapshot.confirmed
            await activate(app, pilot, "correct")
            assert app.service.snapshot.confirmed
            await until(lambda: isinstance(app.screen, Goal))
            await pilot.press("escape")
            assert isinstance(app.screen, Preview)
            await quit_app(app, pilot)
        assert resource.read_bytes() == original

    source = Path("synthetic 世界.csv")
    original = "number,private_zip,private_label\n1,001,a\n2,002,b\n"
    source.write_text(original)
    for size in [(80, 24), (100, 30), (140, 40)]:
        app = MLForgeApp(Service())
        async with app.run_test(size=size) as pilot:
            await pilot.press("enter", "enter")
            assert isinstance(app.screen, Browse)
            await pilot.press("escape")
            assert isinstance(app.screen, Load)
            await pilot.press("down", "enter")
            await pilot.press(*source.name, "enter")
            await until(lambda: isinstance(app.screen, Preview))
            owner = app.screen
            await pilot.pause()
            await pilot.press("enter")
            assert isinstance(app.screen, Help)
            await pilot.press("escape")
            assert app.focused.id == "columns"
            await activate(app, pilot, "change-type")
            assert isinstance(app.screen, TypeReview)
            await pilot.press("down", "enter")
            await until(lambda: app.screen is owner)
            assert app.service.snapshot.schema.profile("c0").effective == (
                ColumnType.CATEGORY
            )
            await activate(app, pilot, "change-type")
            await pilot.press("end", "enter")
            await until(lambda: app.screen is owner)
            assert not app.service.snapshot.schema.profile("c0").overridden
            await activate(app, pilot, "correct")
            assert app.service.snapshot.confirmed
            await until(lambda: isinstance(app.screen, Goal))
            await pilot.press("escape")
            assert isinstance(app.screen, Preview)
            await activate(app, pilot, "prepare")
            assert isinstance(app.screen, Prepare)
            prompt = app.screen.query_one("#prompt", TextArea)
            assert prompt.read_only
            assert "private_" not in prompt.text and source.name not in prompt.text
            await pilot.press("f1", "escape")
            assert app.focused is prompt
            for width, height in [(79, 23), (80, 24), size]:
                await pilot.resize_terminal(width, height)
                await pilot.pause()
                if width < 80:
                    assert isinstance(app.screen, ResizeGuard)
                else:
                    assert app.focused is prompt
            app.save_screenshot(f"prepare-{size[0]}.svg", path=str(evidence))
            await activate(app, pilot, "save")
            assert isinstance(app.screen, SavePrompt)
            field = app.screen.query_one("#destination", Input)
            destination = Path(f"prompt-{size[0]}.txt")
            await pilot.press("ctrl+a", "ctrl+k", *destination.name, "enter")
            await until(lambda: not app.screen.saving)
            assert destination.read_text() == prompt.text
            assert destination.stat().st_mode & 0o777 == 0o600
            await pilot.press("enter")
            await until(lambda: not app.screen.saving)
            assert "already exists" in str(app.screen.query_one("#message").content)
            assert app.focused is field and destination.read_text() == prompt.text
            await quit_app(app, pilot)
        assert source.read_text() == original
    assert not list(Path.cwd().glob(".mlforge-prompt-*"))

    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("enter", "down", "enter", *"missing.csv", "enter")
        await until(
            lambda: (
                isinstance(app.screen, PathEntry)
                and "Error:" in str(app.screen.query_one("#error", Static).content)
            )
        )
        await activate(app, pilot, "prepare")
        assert isinstance(app.screen, Prepare) and "FILE_READ" in app.screen.prompt
        await activate(app, pilot, "another")
        assert isinstance(app.screen, Load)
        await quit_app(app, pilot)
    return {"examples": len(examples), "sizes": [80, 100, 140], "status": "passed"}


async def settle(screen):
    """Wait for one completed Try/Export attempt on that screen."""
    attempts = screen.attempts
    async with asyncio.timeout(180):
        while screen.attempts == attempts:
            await asyncio.sleep(0.05)


async def try_and_export(app, pilot, owner, selected, task, evidence):
    """Try the selected model, then export it; consumer parity runs later."""
    await pilot.press("enter")
    assert isinstance(app.screen, SelectedModel)
    await activate(app, pilot, "try")
    await until(lambda: isinstance(app.screen, Trial))
    await pilot.pause()
    trial = app.screen
    record = {}
    for index, field in enumerate(trial.fields):
        if index == 0:
            assert field.kind == "Number" and app.focused.id == "value-0"
            await pilot.press(*"1000")
            record[field.name] = "1000"
        else:
            trial.query_one(f"#missing-{index}").focus()
            await pilot.press("space")
            record[field.name] = None
    await activate(app, pilot, "predict")
    await settle(trial)
    await pilot.pause()
    prediction = app.service.snapshot.prediction
    assert prediction is not None and app.service.snapshot.selected is selected
    shown = str(trial.query_one("#warnings", Static).content)
    assert "outside the fitted data range" in shown and "Missing input" in shown
    app.save_screenshot(f"{task}-try-80.svg", path=str(evidence))
    await pilot.press("b")
    await until(lambda: isinstance(app.screen, SelectedModel))
    await activate(app, pilot, "export")
    await until(lambda: isinstance(app.screen, ExportPackage))
    await pilot.pause()
    form = app.screen
    module = f"{task.value}_model"
    form.query_one("#module", Input).value = module
    await activate(app, pilot, "build")
    await settle(form)
    await pilot.pause()
    assert isinstance(app.screen, ExportDone), form.query_one("#error", Static).content
    wheel = Path(app.service.snapshot.exported_path)
    assert wheel.parent == Path.cwd() / "exports" and wheel.is_file()
    assert f"from {module} import Predictor" in app.screen.query_one(TextArea).text
    app.save_screenshot(f"{task}-export-done-80.svg", path=str(evidence))
    await activate(app, pilot, "results")
    await until(lambda: app.screen is owner)
    return {
        "try": {"records": [record], "expected": prediction.data},
        "export": {"wheel": str(wheel), "module": module},
    }


async def training_pilot_journey(evidence):
    completed = []
    for task in TaskKind:
        app = MLForgeApp(Service())
        index = next(i for i, e in enumerate(app.service.examples) if e.task == task)
        resource = files("mlforge").joinpath(
            "examples", app.service.examples[index].filename
        )
        original = resource.read_bytes()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("enter", "down", "down", "enter")
            await pilot.press(*(["down"] * index), "enter")
            await until(lambda: isinstance(app.screen, Preview))
            await activate(app, pilot, "correct")
            await until(lambda: isinstance(app.screen, Goal))
            await pilot.pause()
            await pilot.press(*(["down"] * list(TaskKind).index(task)), "enter")
            await until(
                lambda: isinstance(app.screen, Target if task.supervised else Features)
            )
            await pilot.pause()
            if task.supervised:
                assert app.service.snapshot.configuration.target_id is None
                await pilot.press("enter")
                await until(lambda: isinstance(app.screen, Features))
            else:
                assert not any(
                    isinstance(screen, Target) for screen in app.screen_stack
                )
            await activate(app, pilot, "continue")
            await until(lambda: isinstance(app.screen, Preprocessing))
            await activate(app, pilot, "continue")
            await until(lambda: isinstance(app.screen, Models))
            await activate(app, pilot, "train")
            await until(lambda: isinstance(app.screen, Results))
            await pilot.pause()
            run = app.service.snapshot.run
            ranked = app.service.ranked_results
            assert len(ranked) == (2 if task.supervised else 1)
            hashes = {
                c.model_id: hashlib.sha256(
                    (Path(c.bundle.directory) / "model.skops").read_bytes()
                ).hexdigest()
                for c in ranked
            }
            owner = app.screen
            table = owner.query_one("#results", DataTable)
            await pilot.press("right", "right", "question_mark")
            assert isinstance(app.screen, Help)
            await pilot.press("escape")
            assert app.focused is table and table.cursor_column == 3
            for size in [(100, 30), (79, 23), (80, 24)]:
                await pilot.resize_terminal(*size)
                await pilot.pause()
                assert (
                    isinstance(app.screen, ResizeGuard)
                    if size[0] < 80
                    else app.screen is owner
                )
            assert app.focused is table
            app.save_screenshot(f"{task}-results-80.svg", path=str(evidence))
            await pilot.press("enter")
            assert isinstance(app.screen, SelectedModel)
            selected = app.service.snapshot.selected
            assert selected is ranked[0]
            await activate(app, pilot, "inspect")
            assert isinstance(app.screen, Inspection)
            for size in [(80, 24), (100, 30)]:
                await pilot.resize_terminal(*size)
                await pilot.pause()
                app.save_screenshot(
                    f"{task}-inspection-{size[0]}.svg", path=str(evidence)
                )
            await pilot.press("question_mark", "escape", "escape", "escape")
            assert app.screen is owner and app.service.snapshot.selected is selected
            await pilot.press("escape")
            assert isinstance(app.screen, Models)
            await activate(app, pilot, "review-results")
            assert isinstance(app.screen, Results) and app.service.snapshot.run is run
            assert hashes == {
                c.model_id: hashlib.sha256(
                    (Path(c.bundle.directory) / "model.skops").read_bytes()
                ).hexdigest()
                for c in ranked
            }
            trial = await try_and_export(
                app, pilot, app.screen, selected, task, evidence
            )
            assert hashes == {
                c.model_id: hashlib.sha256(
                    (Path(c.bundle.directory) / "model.skops").read_bytes()
                ).hexdigest()
                for c in ranked
            }
            # Exported sessions quit without the unsaved-results confirmation.
            await pilot.press("ctrl+q")
            await until(lambda: app.service.snapshot.activity == Activity.CLOSED)
            assert not app.service._coordinator.root.exists()
        assert resource.read_bytes() == original
        completed.append(
            {
                "task": task.value,
                "models": len(ranked),
                "exact_bundle_retained": True,
                "source_unchanged": True,
                **trial,
            }
        )
    return {
        "tasks": completed,
        "keyboard_only": True,
        "sizes": [80, 100],
        "below_minimum_restore": True,
        "status": "passed",
    }


class TerminalScreen:
    """Current cell contents of Textual's alternate screen, not its redraw history.

    Textual emits cursor positioning, SGR styling, CR/LF and text with autowrap
    disabled, so a small grid model reproduces what is visible now. A stale frame
    (such as footer text repainted underneath Help) cannot satisfy a wait once a
    later frame has overwritten it.
    """

    SEQUENCE = re.compile(
        r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[^\[\]])"
    )
    INCOMPLETE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*|\][^\x07\x1b]*\x1b?)?\Z")

    def __init__(self, rows, columns):
        self.rows, self.columns = rows, columns
        self.grid = [[" "] * columns for _ in range(rows)]
        self.row = self.column = 0
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.pending = ""

    def resize(self, rows, columns):
        self.grid = [
            (line + [" "] * columns)[:columns] for line in self.grid[:rows]
        ] + [[" "] * columns for _ in range(rows - len(self.grid))]
        self.rows, self.columns = rows, columns
        self.row, self.column = min(self.row, rows - 1), min(self.column, columns - 1)

    def feed(self, data):
        text = self.pending + self.decoder.decode(data)
        incomplete = self.INCOMPLETE.search(text)
        cut = incomplete.start() if incomplete else len(text)
        text, self.pending = text[:cut], text[cut:]
        position = 0
        for match in self.SEQUENCE.finditer(text):
            self._write(text[position : match.start()])
            self._control(match.group())
            position = match.end()
        self._write(text[position:])

    def _control(self, sequence):
        if sequence.endswith("H") and sequence.startswith("\x1b["):
            row, _, column = sequence[2:-1].partition(";")
            self.row = min(max(int(row or 1), 1), self.rows) - 1
            self.column = min(max(int(column or 1), 1), self.columns) - 1

    def _write(self, text):
        for char in text:
            if char == "\r":
                self.column = 0
            elif char == "\n":
                self.row = min(self.row + 1, self.rows - 1)
            elif char >= " ":
                width = 2 if unicodedata.east_asian_width(char) in "WF" else 1
                if self.column + width <= self.columns:
                    self.grid[self.row][self.column] = char
                    if width == 2:
                        self.grid[self.row][self.column + 1] = ""
                self.column = min(self.column + width, self.columns - 1)

    def text(self):
        return "\n".join("".join(line) for line in self.grid)


def pty_journey(evidence, exit_key, task=None):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
    env = dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor")
    env.pop("NO_COLOR", None)
    proc = subprocess.Popen(
        [str(Path(sys.executable).parent / "mlforge")],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        start_new_session=True,
        env=env,
    )
    os.close(slave)
    output = bytearray()
    screen = TerminalScreen(24, 80)

    def pump(deadline, missing):
        assert time.monotonic() < deadline, f"PTY missing {missing!r}"
        if select.select([master], [], [], 0.1)[0]:
            try:
                chunk = os.read(master, 65536)
            except OSError as error:
                if error.errno == errno.EIO:
                    raise AssertionError("Premature PTY exit") from None
                raise
            assert chunk
            output.extend(chunk)
            screen.feed(chunk)

    def read_until(fragment, start=0):
        deadline = time.monotonic() + 30
        while True:
            observed = bytes(output[start:])
            if not fragment.startswith(b"\x1b"):
                # Textual styles individual footer spans. Text waits ignore ANSI;
                # protocol waits (alternate screen / OSC52) retain exact bytes.
                observed = re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]", b"", observed)
            if fragment in observed:
                return
            pump(deadline, fragment)

    def await_screen(present, absent=()):
        # State transitions (modal dismissal, resize restoration) are judged on
        # the currently visible cells: earlier frames repaint the same footer.
        deadline = time.monotonic() + 30
        while True:
            visible = screen.text()
            if all(text in visible for text in present) and not any(
                text in visible for text in absent
            ):
                return
            pump(deadline, (present, absent))

    def resize(rows, columns):
        size = struct.pack("HHHH", rows, columns, 0, 0)
        fcntl.ioctl(master, termios.TIOCSWINSZ, size)
        screen.resize(rows, columns)
        proc.send_signal(signal.SIGWINCH)

    def send(keys, expected):
        start = len(output)
        os.write(master, keys)
        read_until(expected, start)

    try:
        read_until(b"Press Enter to begin")
        send(b"\r", b"Browse local files")
        if task is None:
            send(b"\x1b[B\r", b"Enter a local file path")
            send(b"missing.csv\r", b"Error:")
            send(b"\t\t\r", b"Generated locally")
            assert b"\x1b]52;" not in output, "Clipboard requested without Copy"
            send(b"\t\r", b"\x1b]52;c;")
            read_until(b"\a", output.index(b"\x1b]52;c;"))
            encoded = bytes(output).split(b"\x1b]52;c;", 1)[1].split(b"\a", 1)[0]
            copied = base64.b64decode(encoded).decode()
            assert copied == Service().preparation_text("CSV", "FILE_READ")
            send(exit_key, b"\x1b[?1049l")
        else:
            index = next(i for i, e in enumerate(Service.examples) if e.task == task)
            send(b"\x1b[B\x1b[B\r", b"Synthetic data. Examples use")
            send(b"\x1b[B" * index + b"\r", b"Review your dataset")
            send(b"\t\t\r", b"What would you like to do?")
            send(
                b"\x1b[B" * list(TaskKind).index(task) + b"\r",
                b"Choose what to predict"
                if task.supervised
                else b"Choose the information to use",
            )
            if task.supervised:
                send(b"\r", b"Choose the information to use")
            send(b"\t\r", b"Review automatic preprocessing")
            send(b"\r", b"Choose models to train")
            send((b"\t" if task.supervised else b"\t\t") + b"\r", b"Training models")
            read_until(b"Review results")
            send(b"?", b"> Close")
            assert b"evaluated model" in output
            results = ("Review results", "? Help  b Back")
            # Enter must be applied to Help before resizing; a key still queued
            # when ResizeGuard is pushed is delivered to the guard instead.
            os.write(master, b"\r")
            await_screen(results, absent=("Close",))
            resize(23, 79)
            await_screen(("Resize to at least",))
            resize(30, 100)
            await_screen(results, absent=("Close", "Resize to at least"))
            send(b"\r", b"Selected model")
            send(b"\r", b"Inspect model details")
            send(b"\x1b", b"Selected model")
            send(b"\x1b", b"Review results")
            send(exit_key, b"Quit without exporting?")
            send(b"\t\r", b"\x1b[?1049l")
        assert proc.wait(timeout=5) == 0
        assert b"\x1b[?1049h" in output and b"Traceback" not in output
    finally:
        (
            evidence / f"pty-{task.value + '-' if task else ''}{exit_key.hex()}.txt"
        ).write_bytes(output)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        os.close(master)
    return {
        "exit_key": exit_key.hex(),
        "journey": task.value if task else "dataset/Prepare",
        "clipboard": "not requested" if task else "explicit OSC52",
        "status": "passed",
    }


def main():
    evidence = Path(sys.argv[1])
    checkout = Path(sys.argv[2]).resolve()
    assert checkout not in Path.cwd().resolve().parents
    assert Path.cwd().resolve() != checkout
    assert Path(mlforge.__file__).is_relative_to(Path(sys.prefix))
    assert "mlforge_installed_guard" in sys.modules
    assert sys.modules["mlforge_installed_guard"].ACTIVE
    evidence.mkdir(parents=True, exist_ok=True)
    if sys.argv[3:] not in ([], ["--training"]):
        raise SystemExit("Expected optional --training")
    training = sys.argv[3:] == ["--training"]
    result = {
        "pilot": asyncio.run(
            training_pilot_journey(evidence) if training else pilot_journey(evidence)
        ),
        "pty": (
            [
                pty_journey(evidence, key, task)
                for key, task in [
                    (b"q", TaskKind.CLASSIFICATION),
                    (b"\x03", TaskKind.REDUCTION),
                ]
            ]
            if training
            else [pty_journey(evidence, key) for key in (b"\x11", b"\x03")]
        ),
        "outside_checkout": True,
        "python": sys.version,
    }
    (evidence / ("training-journey.json" if training else "journey.json")).write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(
        "Installed training Pilot and PTY passed"
        if training
        else "Installed dataset Pilot and PTY passed"
    )


if __name__ == "__main__":
    main()
