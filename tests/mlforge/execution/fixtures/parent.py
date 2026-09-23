"""Actual parent signal/exception cleanup, supervised by a separate test process."""

import asyncio
import json
import sys
import uuid
from pathlib import Path

from mlforge.execution.coordinator import Coordinator
from mlforge.execution.protocol import Identity, Operation, Request

marker, mode = Path(sys.argv[1]), sys.argv[2]
original = asyncio.create_subprocess_exec


async def launch(*args, **kwargs):
    return await original(
        sys.executable,
        str(Path(__file__).with_name("child.py")),
        args[3],
        args[4],
        "ignore",
        **kwargs,
    )


async def main():
    asyncio.create_subprocess_exec = launch
    async with Coordinator() as owner:
        identity = Identity(uuid.uuid4().hex, 1, uuid.uuid4().hex, Operation.PARSE)
        request = Request(identity, (), (f"{identity.operation_id}/output.json",))

        def started(event):
            marker.write_text(
                json.dumps(
                    {
                        "root": str(owner.root),
                        "child": int((owner.root / "child.pid").read_text()),
                    }
                )
            )
            if mode == "exception":
                raise RuntimeError("synthetic parent failure")

        await owner.run(request, on_event=started)


asyncio.run(main())
