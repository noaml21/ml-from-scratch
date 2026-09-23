"""Parent acceptance is the sole final publication barrier (real child faults)."""

import asyncio
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

from mlforge.execution import coordinator
from mlforge.execution.protocol import EventKind, Identity, Operation, Request


@pytest.fixture
def child(monkeypatch):
    original = asyncio.create_subprocess_exec

    def use(mode):
        async def spawn(*args, **kwargs):
            return await original(
                sys.executable,
                str(Path(__file__).parent / "fixtures/staged_export.py"),
                args[3],
                args[4],
                mode,
                **kwargs,
            )

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)

    return use


def request(staging):
    identity = Identity(uuid.uuid4().hex, 1, uuid.uuid4().hex, Operation.EXPORT)
    return Request(
        identity,
        (),
        (f"{identity.operation_id}/export.json",),
        json.dumps(
            {
                "publication_directory": str(staging),
                "module_name": "foo__bar_",
                "version": "1.0.0",
            }
        ),
    )


@pytest.mark.parametrize(
    "mode",
    [
        "success",
        "missing",
        "hash",
        "name",
        "size",
        "extra",
        "malformed",
        "crash",
        "late-crash",
        "hang",
        "existing",
    ],
)
async def test_only_valid_completed_transport_can_publish(child, mode, tmp_path):
    child("success" if mode == "existing" else mode)
    sentinel = tmp_path / "unrelated"
    sentinel.write_text("preserved")
    final = tmp_path / "foo_bar-1.0.0-py3-none-any.whl"
    if mode == "existing":
        final.write_text("prior export")
    async with coordinator.Coordinator() as owner:
        async with owner.publication_staging(tmp_path) as staging:
            outcome = await owner.run(
                request(staging),
                deadline=time.monotonic() + 1 if mode == "hang" else None,
            )
            pid = int((owner.root / "child.pid").read_text())
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
            assert outcome.completed == (mode == "success")
            if mode == "success":
                assert outcome.published_path == str(final)
                assert final.read_bytes() == b"controlled transport payload"
            elif mode == "existing":
                assert outcome.error_code == "EXPORT_EXISTS"
                assert final.read_text() == "prior export"
            else:
                assert not final.exists()
                assert outcome.error_code
        assert not staging.exists()
    assert sentinel.read_text() == "preserved"
    assert set(tmp_path.iterdir()) == (
        {sentinel, final} if mode in {"success", "existing"} else {sentinel}
    )


async def test_cancel_at_completed_event_never_publishes(child, tmp_path):
    child("success")
    async with coordinator.Coordinator() as owner:
        async with owner.publication_staging(tmp_path) as staging:

            def event(value):
                if value.kind == EventKind.COMPLETED:
                    owner.cancel()

            outcome = await owner.run(request(staging), on_event=event)
            assert outcome.cancelled and not outcome.completed
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("action", ["cancel", "task-cancel", "timeout"])
async def test_cancel_or_timeout_during_parent_validation(
    child, tmp_path, monkeypatch, action
):
    child("success")
    entered, release = threading.Event(), threading.Event()
    async with coordinator.Coordinator() as owner:
        original = owner._validate_export

        def validate(outcome):
            value = original(outcome)
            entered.set()
            assert release.wait(5)
            return value

        monkeypatch.setattr(owner, "_validate_export", validate)
        async with owner.publication_staging(tmp_path) as staging:
            expires = time.monotonic() + (1 if action == "timeout" else 30)
            task = asyncio.create_task(owner.run(request(staging), deadline=expires))
            try:

                async def wait_entered():
                    while not entered.is_set():
                        if task.done():
                            pytest.fail(str(task.result()))
                        await asyncio.sleep(0.01)

                await asyncio.wait_for(wait_entered(), 5)
                if action == "cancel":
                    owner.cancel()
                elif action == "task-cancel":
                    task.cancel()
                else:
                    await asyncio.sleep(max(0, expires - time.monotonic()) + 0.02)
            finally:
                release.set()
            if action == "task-cancel":
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                outcome = await task
                assert not outcome.completed
                assert (
                    outcome.cancelled
                    if action == "cancel"
                    else outcome.error_code == "TIMEOUT"
                )
    assert not list(tmp_path.iterdir())


async def test_parent_fsync_failure_rolls_back_only_created_link(
    child, tmp_path, monkeypatch
):
    child("success")
    async with coordinator.Coordinator() as owner:
        async with owner.publication_staging(tmp_path) as staging:
            original = owner._publish

            def publish(*args):
                with monkeypatch.context() as patch:

                    def fail(fd):
                        raise OSError("disk failure")

                    patch.setattr(os, "fsync", fail)
                    return original(*args)

            monkeypatch.setattr(owner, "_publish", publish)
            outcome = await owner.run(request(staging))
            assert outcome.error_code == "EXPORT_IO" and not outcome.completed
    assert not list(tmp_path.iterdir())


async def test_registered_staging_permissions_checked_before_spawn(
    child, tmp_path, monkeypatch
):
    async def forbidden(*args, **kwargs):
        pytest.fail("Changed staging ownership must not reach a child")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    async with coordinator.Coordinator() as owner:
        async with owner.publication_staging(tmp_path) as staging:
            staging.chmod(0o755)
            outcome = await owner.run(request(staging))
            assert outcome.error_code == "PROTOCOL" and outcome.fatal
    assert not list(tmp_path.iterdir())
