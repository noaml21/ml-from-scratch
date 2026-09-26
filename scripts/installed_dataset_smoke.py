"""Dataset and training Pilot/PTY gates in isolated application installations."""

import asyncio
import base64
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
from mlforge.tui.screens.prepare import Prepare, SavePrompt
from mlforge.tui.screens.preview import Preview, TypeReview
from mlforge.tui.screens.results import Inspection, Results, SelectedModel
from mlforge.tui.screens.shell import Confirm, Help, ResizeGuard


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
            await pilot.press("ctrl+q")
            assert isinstance(app.screen, Confirm) and app.focused.id == "keep"
            await pilot.press("tab", "enter")
            await until(lambda: app.service.snapshot.activity == Activity.CLOSED)
            assert not app.service._coordinator.root.exists()
        assert resource.read_bytes() == original
        completed.append(
            {
                "task": task.value,
                "models": len(ranked),
                "exact_bundle_retained": True,
                "source_unchanged": True,
            }
        )
    return {
        "tasks": completed,
        "keyboard_only": True,
        "sizes": [80, 100],
        "below_minimum_restore": True,
        "status": "passed",
    }


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
            assert time.monotonic() < deadline, f"PTY missing {fragment!r}"
            if select.select([master], [], [], 0.1)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError as error:
                    if error.errno == errno.EIO:
                        raise AssertionError("Premature PTY exit") from None
                    raise
                assert chunk
                output.extend(chunk)

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
            send(b"\r", b"? Help  b Back")
            start = len(output)
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 23, 79, 0, 0))
            proc.send_signal(signal.SIGWINCH)
            read_until(b"Resize to at least", start)
            start = len(output)
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
            proc.send_signal(signal.SIGWINCH)
            read_until(b"? Help  b Back", start)
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
