"""Hold the actual export publication step after creating its temporary file."""

import os
import signal
import sys
import tempfile
from pathlib import Path

from mlforge.execution import worker
from mlforge.execution.protocol import json_data, write_owned

root, operation_id = Path(sys.argv[1]), sys.argv[2]
original = tempfile.NamedTemporaryFile


def held(*args, **kwargs):
    output = original(*args, **kwargs)
    if kwargs.get("prefix") == ".mlforge-":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        write_owned(
            root,
            "publication-ready.json",
            json_data({"pid": os.getpid(), "path": output.name}),
        )
        while True:
            signal.pause()
    return output


tempfile.NamedTemporaryFile = held
raise SystemExit(worker.main([str(root), operation_id]))
