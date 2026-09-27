"""Actual existing launcher restores a Linux PTY after normal/error exits."""

import errno
import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

import pytest


@pytest.mark.pty
@pytest.mark.parametrize("exit_key", [b"\x11", b"\x03"])
def test_entrypoint_restores_terminal_after_recoverable_error(tmp_path, exit_key):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
    env = dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor")
    proc = subprocess.Popen(
        [sys.executable, "-m", "mlforge"],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        start_new_session=True,
        env=env,
    )
    os.close(slave)
    output = bytearray()

    def read_until(fragment):
        deadline = time.monotonic() + 30
        while fragment not in output:
            assert time.monotonic() < deadline, f"PTY did not show {fragment!r}"
            if select.select([master], [], [], 0.1)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError as error:
                    if error.errno == errno.EIO:
                        raise AssertionError(
                            "App exited before expected screen"
                        ) from None
                    raise
                assert chunk
                output.extend(chunk)

    try:
        read_until(b"Press Enter to begin")
        os.write(master, b"\r")
        read_until(b"Browse local files")
        os.write(master, b"\x1b[B\r")
        read_until(b"Enter a local file path")
        os.write(master, str(tmp_path / "absent.csv").encode() + b"\r")
        read_until(b"Error:")
        os.write(master, exit_key)
        read_until(b"\x1b[?1049l")
        assert proc.wait(timeout=5) == 0
        assert b"\x1b[?1049h" in output
        assert b"Traceback" not in output
        destination = Path(".mlforge-build/p06-shell")
        destination.mkdir(parents=True, exist_ok=True)
        (destination / f"pty-{exit_key.hex()}.txt").write_bytes(output)
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
        os.close(master)
