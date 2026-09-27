"""Real child producing controlled export transport faults, never a destination."""

import json
import os
import signal
import sys
from pathlib import Path

from mlforge.contracts import ExportOptions
from mlforge.execution.protocol import (
    EventKind,
    Request,
    Result,
    RunEvent,
    decode,
    encode,
    json_data,
    read_owned,
    write_owned,
)

root, operation_id, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
request = decode(read_owned(root, f"request-{operation_id}.json"), Request)
options = json.loads(request.options_json)
staging = Path(options["publication_directory"])
assert "destination" not in options
write_owned(root, "child.pid", str(os.getpid()).encode())
os.write(1, encode(RunEvent(request.identity, 0, EventKind.STARTED)))
artifact = write_owned(staging, "wheel.whl", b"controlled transport payload")
if mode == "hang":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        signal.pause()
if mode == "crash":
    os._exit(19)
if mode == "missing":
    (staging / "wheel.whl").unlink()
receipt = {
    "name": ExportOptions(options["module_name"], options["version"]).wheel_name,
    "size": artifact.size,
    "sha256": artifact.sha256,
}
if mode == "hash":
    receipt["sha256"] = "0" * 64
if mode == "name":
    receipt["name"] = "../foreign.whl"
if mode == "size":
    receipt["size"] = True
if mode == "extra":
    receipt["destination"] = "/tmp/forbidden"
(root / operation_id).mkdir(mode=0o700)
ref = write_owned(root, request.outputs[0], json_data(receipt))
write_owned(
    root, f"result-{operation_id}.json", encode(Result(request.identity, (ref,)))
)
if mode == "malformed":
    os.write(1, b'{"completed":true}\n')
else:
    os.write(1, encode(RunEvent(request.identity, 1, EventKind.COMPLETED)))
if mode == "late-crash":
    os._exit(17)
