"""The installed PTY verifier judges transitions on visible cells, not history."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def terminal_screen():
    spec = importlib.util.spec_from_file_location(
        "installed_dataset_smoke", ROOT / "scripts/installed_dataset_smoke.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TerminalScreen


def test_later_frame_replaces_footer_repainted_underneath_help():
    screen = terminal_screen()(4, 20)
    screen.feed(b"\x1b[1;1H\x1b[1mReview results\x1b[0m\x1b[2;3H> Close")
    screen.feed(b"\x1b[4;1H? Help  b Back")
    visible = screen.text()
    assert "? Help  b Back" in visible and "Close" in visible
    screen.feed(b"\x1b[2;1H" + b" " * 20)
    assert "Close" not in screen.text()
    assert "? Help  b Back" in screen.text()


def test_split_sequences_utf8_wide_cells_and_resize():
    screen = terminal_screen()(3, 12)
    screen.feed(b"\x1b]22;default\x07\x1b[2")
    screen.feed(b";2H80 \xc3")
    screen.feed(b"\x97 24 \xe7\x95\x8c\r\nnext")
    lines = screen.text().splitlines()
    assert lines[1] == " 80 × 24 界 "
    assert lines[2].startswith("next")
    screen.resize(2, 5)
    assert screen.text().splitlines() == ["     ", " 80 ×"]
    screen.feed(b"\x1b[9;9Hz")
    assert screen.text().splitlines()[1] == " 80 z"
