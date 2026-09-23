"""Owned child lifetime and transport; application owns semantic acceptance."""

import asyncio
import ctypes
import os
import shutil
import signal
import stat
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from pathlib import Path

from mlforge.contracts import DomainError, ExportOptions
from mlforge.execution.protocol import (
    MAX_EVENT,
    MAX_MESSAGE,
    MAX_STDERR,
    Artifact,
    EventKind,
    EventStream,
    Operation,
    ProtocolError,
    Request,
    Result,
    decode,
    encode,
    parse_json,
    read_owned,
    validate_result,
    verify_artifact,
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
    fatal: bool = False
    reported: bool = False
    published_path: str | None = None

    @property
    def completed(self):
        return (
            self.result is not None and self.error_code is None and not self.cancelled
        )


@dataclass(frozen=True)
class RunOutcome:
    outcomes: tuple[Outcome, ...]
    expected_count: int
    cancelled: bool = False
    aborted: bool = False

    @property
    def all_failed(self):
        return (
            not self.cancelled
            and len(self.outcomes) == self.expected_count
            and all(not item.completed for item in self.outcomes)
        )

    @property
    def completed(self):
        return tuple(item for item in self.outcomes if item.completed)


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
        self._publication_directories = {}

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
        for path in tuple(self._publication_directories):
            self._release_publication(path)
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None
            _subreaper(self._previous_subreaper)
        if interrupted:
            raise asyncio.CancelledError

    @asynccontextmanager
    async def publication_staging(self, destination):
        """Parent-owned private destination resource, removed only after reaping."""
        if self._closed or self.root is None or self._busy:
            raise RuntimeError("Cannot reserve publication staging now")
        destination = Path(destination).expanduser().resolve()
        try:
            destination.mkdir(parents=True, exist_ok=True)
            path = Path(tempfile.mkdtemp(prefix=".mlforge-", dir=destination))
            info = path.lstat()
            self._publication_directories[path] = (info.st_dev, info.st_ino)
        except OSError:
            raise DomainError(
                "EXPORT_IO",
                "Could not create private export staging.",
                "Choose a writable destination with free space.",
            ) from None
        try:
            yield path
        finally:
            self.cancel()
            _, interrupted = await _settle(asyncio.create_task(self._idle.wait()))
            self._release_publication(path)
            if interrupted:
                raise asyncio.CancelledError

    def _release_publication(self, path):
        identity = self._publication_directories.get(path)
        if identity is None:
            return
        try:
            info = path.lstat()
            if (info.st_dev, info.st_ino) != identity or not stat.S_ISDIR(info.st_mode):
                raise DomainError(
                    "OWNERSHIP",
                    "Export staging ownership changed.",
                    "Inspect the destination; unrelated paths were not removed.",
                )
            shutil.rmtree(path)
        except FileNotFoundError:
            pass
        except OSError:
            raise DomainError(
                "EXPORT_IO",
                "Could not remove private export staging.",
                "Check destination permissions and retry cleanup.",
            ) from None
        self._publication_directories.pop(path)

    async def run(self, request, *, cancellation=None, on_event=None, deadline=None):
        if self._closed or self.root is None or self._busy:
            raise RuntimeError("Coordinator is closed, unopened or busy")
        if type(request) is not Request:
            raise ProtocolError()
        self._busy = True
        self._idle.clear()
        self._cancel = cancellation if cancellation is not None else asyncio.Event()
        try:
            expires = min(
                time.monotonic() + DEADLINES[request.identity.operation],
                deadline if deadline is not None else float("inf"),
            )
            outcome = await self._run(request, self._cancel, on_event, expires)
            if outcome.completed and request.identity.operation == Operation.EXPORT:
                outcome = await self._complete_export(outcome, self._cancel, expires)
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

    def _checked_publication(self, request):
        options = parse_json(request.options_json.encode())
        value = options.get("publication_directory")
        if type(value) is not str:
            raise ProtocolError()
        path = Path(value)
        expected = self._publication_directories.get(path)
        if expected is None:
            raise ProtocolError()
        info = path.lstat()
        if (
            (info.st_dev, info.st_ino) != expected
            or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise ProtocolError()
        return path

    def _validate_export(self, outcome):
        request = outcome.request
        staging = self._checked_publication(request)
        options = parse_json(request.options_json.encode())
        expected = ExportOptions(options.get("module_name"), options.get("version"))
        artifacts = outcome.result.artifacts
        if (
            len(artifacts) != 1
            or artifacts[0].name != f"{request.identity.operation_id}/export.json"
        ):
            raise ProtocolError()
        receipt = parse_json(verify_artifact(self.root, artifacts[0]))
        if (
            type(receipt) is not dict
            or set(receipt) != {"name", "size", "sha256"}
            or receipt["name"] != expected.wheel_name
        ):
            raise ProtocolError()
        artifact = Artifact("wheel.whl", receipt["size"], receipt["sha256"])
        if not 0 < artifact.size <= 100 * 1024**2:
            raise ProtocolError()
        verify_artifact(staging, artifact)
        return staging, expected.wheel_name

    def _publish(self, staging, name):
        """One non-yielding no-replace commit after the cancellation barrier."""
        source = os.open(staging, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        destination = None
        published = False
        try:
            destination = os.open(
                staging.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
            original = os.stat("wheel.whl", dir_fd=source, follow_symlinks=False)
            os.link(
                "wheel.whl",
                name,
                src_dir_fd=source,
                dst_dir_fd=destination,
                follow_symlinks=False,
            )
            published = True
            os.fsync(destination)
        except OSError:
            # Remove only the exact link this call just created, never a prior file.
            if published:
                current = os.stat(name, dir_fd=destination, follow_symlinks=False)
                if (current.st_dev, current.st_ino) == (
                    original.st_dev,
                    original.st_ino,
                ):
                    os.unlink(name, dir_fd=destination)
            raise
        finally:
            os.close(source)
            if destination is not None:
                os.close(destination)
        return str(staging.parent / name)

    async def _complete_export(self, outcome, cancellation, expires):
        try:
            (staging, name), interrupted = await _settle(
                asyncio.create_task(asyncio.to_thread(self._validate_export, outcome))
            )
            if interrupted:
                raise asyncio.CancelledError
            if cancellation.is_set():
                return replace(outcome, result=None, cancelled=True)
            if time.monotonic() >= expires:
                return replace(outcome, result=None, error_code="TIMEOUT")
            self._checked_publication(outcome.request)
            # No await between this barrier and publication/accepted outcome.
            path = self._publish(staging, name)
            return replace(outcome, published_path=path)
        except FileExistsError:
            return replace(outcome, result=None, error_code="EXPORT_EXISTS")
        except DomainError as error:
            return replace(outcome, result=None, error_code=error.code)
        except OSError:
            return replace(outcome, result=None, error_code="EXPORT_IO")

    async def run_many(
        self,
        requests,
        *,
        cancellation=None,
        on_event=None,
        on_result=None,
        abort_codes=frozenset(),
        deadline=None,
    ):
        """Serial candidates; application supplies domain errors that abort a run.

        A deadline is absolute monotonic time, so shared preparation can consume
        the same supervised 300-second budget rather than resetting it here.
        """
        requests = tuple(requests)
        if not 1 <= len(requests) <= 2 or any(type(r) is not Request for r in requests):
            raise ProtocolError()
        identities = [r.identity for r in requests]
        if (
            any(i.operation != Operation.TRAIN for i in identities)
            or len({(i.run_id, i.revision) for i in identities}) != 1
            or len({i.operation_id for i in identities}) != len(identities)
            or len({i.model_id for i in identities}) != len(identities)
        ):
            raise ProtocolError()
        if self._closed or self.root is None or self._busy:
            raise RuntimeError("Coordinator is closed, unopened or busy")
        self._busy = True
        self._idle.clear()
        self._cancel = cancellation if cancellation is not None else asyncio.Event()
        deadline = time.monotonic() + 300 if deadline is None else deadline
        outcomes = []
        aborted = False
        try:
            for request in requests:
                if self._cancel.is_set():
                    break
                outcome = await self._run(request, self._cancel, on_event, deadline)
                if self._cancel.is_set():
                    break  # Unaccepted completion is not retained.
                outcomes.append(outcome)
                if on_result is not None:
                    on_result(outcome)
                if outcome.fatal or (
                    outcome.reported and outcome.error_code in abort_codes
                ):
                    aborted = True
                    break
                if time.monotonic() >= deadline:
                    aborted = True
                    break
            return RunOutcome(
                tuple(outcomes), len(requests), self._cancel.is_set(), aborted
            )
        finally:
            self._cancel = None
            self._busy = False
            self._idle.set()

    async def _run(self, request, cancellation, on_event, deadline=None):
        if cancellation.is_set():
            return Outcome(request, cancelled=True)
        started = time.monotonic()
        expires = min(
            started + DEADLINES[request.identity.operation],
            deadline if deadline is not None else float("inf"),
        )
        if started >= expires:
            return Outcome(request, error_code="TIMEOUT")
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
                    if on_event is not None and not cancellation.is_set():
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
            if request.identity.operation == Operation.EXPORT:
                self._checked_publication(request)

            def verify_inputs():
                for artifact in request.inputs:
                    verify_artifact(self.root, artifact)

            _, interrupted = await _settle(
                asyncio.create_task(asyncio.to_thread(verify_inputs))
            )
            if interrupted:
                raise asyncio.CancelledError
            if cancellation.is_set():
                return Outcome(request, cancelled=True)
            if time.monotonic() >= expires:
                return Outcome(request, error_code="TIMEOUT")
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
            remaining = max(0, expires - time.monotonic())
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
                    reported=last_event.kind == EventKind.FAILED,
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
            if time.monotonic() >= expires:
                return Outcome(request, error_code="TIMEOUT", stderr_bytes=stderr_bytes)
            return Outcome(
                request,
                result=result,
                returncode=proc.returncode,
                stderr_bytes=stderr_bytes,
            )
        except ProtocolError:
            return Outcome(
                request,
                error_code="PROTOCOL",
                stderr_bytes=stderr_bytes,
                fatal=proc is None,
            )
        except OSError:
            return Outcome(
                request, error_code="STORAGE", stderr_bytes=stderr_bytes, fatal=True
            )
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
