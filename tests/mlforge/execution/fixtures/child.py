"""Synthetic process faults; only launched by lifecycle tests."""

import os
import signal
import sys
import time
from pathlib import Path

from mlforge.execution.protocol import (
    EventKind,
    Request,
    Result,
    RunEvent,
    decode,
    encode,
    read_owned,
    write_owned,
)

root, operation_id, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
request = decode(read_owned(root, f"request-{operation_id}.json"), Request)
identity = request.identity


def event(sequence, kind, **fields):
    os.write(1, encode(RunEvent(identity, sequence, kind, **fields)))


if mode in {"ignore", "grandchild"}:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
if mode == "grandchild":
    pid = os.fork()
    if pid == 0:
        while True:
            signal.pause()
    write_owned(root, "grandchild.pid", str(pid).encode())
write_owned(root, f"child-{operation_id}.pid", str(os.getpid()).encode())
if not (root / "child.pid").exists():
    write_owned(root, "child.pid", str(os.getpid()).encode())
event(0, EventKind.STARTED)
if mode in {"hang", "ignore", "grandchild"}:
    if mode == "grandchild":
        os._exit(0)  # Descendant retains pipes and survives its leader.
    while True:
        signal.pause()
elif mode == "malformed":
    os.write(1, b'{"bad":true}\n')
    time.sleep(60)
elif mode == "truncated":
    os.write(1, b'{"bad":')
elif mode == "oversized":
    os.write(1, b"x" * 20000)
    time.sleep(60)
elif mode.startswith("failure-"):
    event(1, EventKind.FAILED, error_code=mode.removeprefix("failure-"))
    os._exit(1)
elif mode == "crash":
    os._exit(19)
else:
    if mode == "flood":
        for _ in range(512):
            os.write(2, b"private source data" * 1024)
    (root / operation_id).mkdir(mode=0o700)
    artifact = write_owned(root, request.outputs[0], b'{"ok":true}')
    result = Result(identity, (artifact,))
    write_owned(root, f"result-{operation_id}.json", encode(result))
    event(1, EventKind.COMPLETED)
    if mode == "success_then_crash":
        os._exit(17)
