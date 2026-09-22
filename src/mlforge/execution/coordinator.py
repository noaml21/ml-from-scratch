"""Owned child lifetime and transport; application owns semantic acceptance."""

import asyncio
import ctypes
import os
import signal
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from mlforge.contracts import DomainError
from mlforge.execution.protocol import (
    MAX_EVENT,
    MAX_MESSAGE,
    MAX_STDERR,
    EventKind,
    EventStream,
    Operation,
    ProtocolError,
    Request,
    Result,
    decode,
    encode,
    read_owned,
    validate_result,
    write_owned,
)

DEADLINES = {operation: 30.0 for operation in Operation}
DEADLINES.update({Operation.TRAIN: 120.0, Operation.EXPORT: 60.0})
TERMINATE_GRACE = 2.0


def _subreaper(value=None):
    """Linux-only supported platform; reap orphaned descendants in our group."""
    libc = ctypes.CDLL(None, use_errno=True)
    current = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(current), 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Cannot inspect child ownership")
    if value is not None and libc.prctl(36, int(value), 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Cannot establish child ownership")
    return bool(current.value)


async def _settle(task):
    """Finish owned work despite repeated cancellation; report it to the caller."""
    interrupted = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            interrupted = True
    return task.result(), interrupted


@dataclass(frozen=True)
class Outcome:
    request: Request
    result: Result | None = None
    error_code: str | None = None
    cancelled: bool = False
    returncode: int | None = None
    stderr_bytes: int = 0

    @property
    def completed(self):
        return (
            self.result is not None and self.error_code is None and not self.cancelled
        )


class Coordinator:
    """One session, one operation at a time. Use async with for guaranteed cleanup."""

    def __init__(self):
        self._temporary = None
        self.root = None
        self._busy = False
        self._closed = False
        self._cancel = None
        self._idle = asyncio.Event()
        self._idle.set()
        self._previous_subreaper = None

    async def __aenter__(self):
        if self._temporary is not None or self._closed:
            raise RuntimeError("Coordinator cannot be reopened")
        self._previous_subreaper = _subreaper(True)
        try:
            self._temporary = tempfile.TemporaryDirectory(prefix="mlforge-")
            self.root = Path(self._temporary.name)
            self.root.chmod(0o700)
        except BaseException:
            _subreaper(self._previous_subreaper)
            raise
        return self

    async def __aexit__(self, *exc):
        await self.close()

    def cancel(self):
        """Synchronous acknowledgement; cleanup remains awaited by run/close."""
        if self._cancel is not None:
            self._cancel.set()

    async def close(self):
        self._closed = True
        self.cancel()
        _, interrupted = await _settle(asyncio.create_task(self._idle.wait()))
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None
            _subreaper(self._previous_subreaper)
        if interrupted:
            raise asyncio.CancelledError

    async def run(self, request, *, cancellation=None, on_event=None):
        if self._closed or self.root is None or self._busy:
            raise RuntimeError("Coordinator is closed, unopened or busy")
        if type(request) is not Request:
            raise ProtocolError()
        self._busy = True
        self._idle.clear()
        self._cancel = cancellation if cancellation is not None else asyncio.Event()
        try:
            outcome = await self._run(request, self._cancel, on_event)
            if self._cancel.is_set():
                return Outcome(
                    request,
                    cancelled=True,
                    returncode=outcome.returncode,
                    stderr_bytes=outcome.stderr_bytes,
                )
            return outcome
        finally:
            self._cancel = None
            self._busy = False
            self._idle.set()

    async def _run(self, request, cancellation, on_event):
        if cancellation.is_set():
            return Outcome(request, cancelled=True)
        started = time.monotonic()
        proc = None
        completion = None
        cancel_wait = None
        drains = []
        last_event = None
        stderr_bytes = 0
        stream = EventStream(request.identity)

        async def stdout():
            nonlocal last_event
            buffer = bytearray()
            while chunk := await proc.stdout.read(4096):
                buffer.extend(chunk)
                while b"\n" in buffer:
                    end = buffer.index(b"\n") + 1
                    if end > MAX_EVENT:
                        raise ProtocolError()
                    last_event = stream.accept(bytes(buffer[:end]))
                    del buffer[:end]
                    if on_event is not None:
                        on_event(last_event)
                if len(buffer) >= MAX_EVENT:
                    raise ProtocolError()
            if buffer or not stream.terminal:
                raise ProtocolError()

        async def stderr():
            nonlocal stderr_bytes
            while chunk := await proc.stderr.read(4096):
                # Keep only a bounded byte count; no raw library logs/paths/data.
                stderr_bytes = min(MAX_STDERR, stderr_bytes + len(chunk))

        try:
            write_owned(
                self.root,
                f"request-{request.identity.operation_id}.json",
                encode(request),
            )
            # Spawn is shielded: cancellation during process creation must still
            # obtain the handle and reap it before propagating CancelledError.
            spawn = asyncio.create_task(
                asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "mlforge.execution.worker",
                    str(self.root),
                    request.identity.operation_id,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    start_new_session=True,
                    limit=MAX_EVENT,
                )
            )
            proc, interrupted = await _settle(spawn)
            if interrupted:
                raise asyncio.CancelledError
            drains = [asyncio.create_task(stdout()), asyncio.create_task(stderr())]
            completion = asyncio.gather(proc.wait(), *drains)
            cancel_wait = asyncio.create_task(cancellation.wait())
            remaining = max(
                0, DEADLINES[request.identity.operation] - (time.monotonic() - started)
            )
            done, _ = await asyncio.wait(
                {completion, cancel_wait},
                timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if cancellation.is_set():
                return Outcome(request, cancelled=True, stderr_bytes=stderr_bytes)
            if completion not in done:
                return Outcome(request, error_code="TIMEOUT", stderr_bytes=stderr_bytes)
            try:
                completion.result()
            except (ValueError, DomainError):
                return Outcome(
                    request,
                    error_code="PROTOCOL",
                    returncode=proc.returncode,
                    stderr_bytes=stderr_bytes,
                )
            if proc.returncode != 0 or last_event.kind != EventKind.COMPLETED:
                code = (
                    last_event.error_code
                    if last_event.kind == EventKind.FAILED
                    else "WORKER_CRASH"
                )
                return Outcome(
                    request,
                    error_code=code,
                    returncode=proc.returncode,
                    stderr_bytes=stderr_bytes,
                )

            def validated():
                result = decode(
                    read_owned(
                        self.root,
                        f"result-{request.identity.operation_id}.json",
                        MAX_MESSAGE,
                    ),
                    Result,
                )
                return validate_result(
                    request,
                    result,
                    self.root,
                    returncode=proc.returncode,
                    completed=True,
                    cancelled=cancellation.is_set(),
                )

            result, interrupted = await _settle(
                asyncio.create_task(asyncio.to_thread(validated))
            )
            if interrupted:
                raise asyncio.CancelledError
            if time.monotonic() - started > DEADLINES[request.identity.operation]:
                return Outcome(request, error_code="TIMEOUT", stderr_bytes=stderr_bytes)
            return Outcome(
                request,
                result=result,
                returncode=proc.returncode,
                stderr_bytes=stderr_bytes,
            )
        except ProtocolError:
            return Outcome(request, error_code="PROTOCOL", stderr_bytes=stderr_bytes)
        except OSError:
            return Outcome(request, error_code="STORAGE", stderr_bytes=stderr_bytes)
        finally:
            interrupted = False
            if proc is not None:
                _, interrupted = await _settle(
                    asyncio.create_task(self._reap_group(proc))
                )
            if cancel_wait is not None:
                cancel_wait.cancel()
                _, cancelled = await _settle(
                    asyncio.gather(cancel_wait, return_exceptions=True)
                )
                interrupted |= cancelled
            pending = [*drains]
            if completion is not None:
                pending.append(completion)
            if pending:
                _, cancelled = await _settle(
                    asyncio.gather(*pending, return_exceptions=True)
                )
                interrupted |= cancelled
            if interrupted:
                raise asyncio.CancelledError

    async def _reap_group(self, proc):
        """Never signal a released handle; reap only this operation's group."""
        pgid = proc.pid  # start_new_session makes this child's PID its PGID.

        released = False

        def exists():
            nonlocal released
            if released:
                return False
            if proc.returncode is not None:
                # asyncio owns/reaps the direct child. Only then collect adopted
                # descendants, never waitpid(-1) or other session children.
                while True:
                    try:
                        pid, _ = os.waitpid(-pgid, os.WNOHANG)
                        if pid == 0:
                            break
                    except ChildProcessError:
                        break
            try:
                os.killpg(pgid, 0)
                return True
            except ProcessLookupError:
                released = True
                return False

        def stop(sig):
            try:
                os.killpg(pgid, sig)
            except ProcessLookupError:
                pass

        if exists():
            stop(signal.SIGTERM)
            deadline = time.monotonic() + TERMINATE_GRACE
            while exists() and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            if exists():
                stop(signal.SIGKILL)
            while exists():
                await asyncio.sleep(0.01)
        await proc.wait()
