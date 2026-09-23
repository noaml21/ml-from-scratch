"""Parent interruption/exception must finish owned cleanup before exiting."""

import asyncio
import json
import os
import signal
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("mode", ["interrupt", "exception"])
async def test_parent_signal_or_exception_reaps_and_removes_owned_resources(
    tmp_path, mode
):
    marker = tmp_path / "parent-ready.json"
    parent = await asyncio.create_subprocess_exec(
        sys.executable,
        str(Path(__file__).parent / "fixtures/parent.py"),
        str(marker),
        mode,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True,
    )

    async def ready():
        while not marker.exists():
            if parent.returncode is not None:
                pytest.fail("Parent exited before starting its owned worker")
            await asyncio.sleep(0.01)
        return json.loads(marker.read_text())

    info = None
    try:
        info = await asyncio.wait_for(ready(), 5)
        if mode == "interrupt":
            parent.send_signal(signal.SIGINT)
        assert await asyncio.wait_for(parent.wait(), 5) != 0
        with pytest.raises(ProcessLookupError):
            os.kill(info["child"], 0)
        assert not Path(info["root"]).exists()
    finally:
        if parent.returncode is None:
            parent.send_signal(signal.SIGINT)
            await asyncio.wait_for(parent.wait(), 5)
