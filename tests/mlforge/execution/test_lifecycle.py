"""Real process groups, handshakes, deadlines and unrelated-resource sentinels."""

import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

import pytest

from mlforge.execution import coordinator
from mlforge.execution.protocol import (
    MAX_STDERR,
    EventKind,
    Identity,
    Operation,
    Request,
)


@pytest.fixture
def child(monkeypatch):
    original = asyncio.create_subprocess_exec

    def use(mode):
        async def spawn(*args, **kwargs):
            return await original(
                sys.executable,
                str(Path(__file__).parent / "fixtures/child.py"),
                args[3],
                args[4],
                mode,
                **kwargs,
            )

        monkeypatch.setattr(coordinator.asyncio, "create_subprocess_exec", spawn)

    return use


def request():
    identity = Identity(uuid.uuid4().hex, 1, uuid.uuid4().hex, Operation.PARSE)
    return Request(identity, (), (f"{identity.operation_id}/output.json",))


def gone(pid):
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


async def test_real_dispatch_and_owned_directory_cleanup(tmp_path):
    source = tmp_path / "data.csv"
    source.write_text("a,b\n1,2\n")
    import json

    identity = Identity(uuid.uuid4().hex, 1, uuid.uuid4().hex, Operation.PARSE)
    req = Request(
        identity,
        (),
        tuple(
            f"{identity.operation_id}/{name}"
            for name in ("dataset.json", "schema.json")
        ),
        json.dumps({"path": str(source)}),
    )
    async with coordinator.Coordinator() as owner:
        root = owner.root
        assert root.stat().st_mode & 0o777 == 0o700
        result = await owner.run(req)
        assert result.completed
    assert not root.exists() and source.read_text() == "a,b\n1,2\n"


@pytest.mark.parametrize("mode", ["hang", "ignore", "grandchild"])
async def test_cancel_reaps_group_and_preserves_sentinel(child, mode, tmp_path):
    sentinel = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import time; time.sleep(60)",
        start_new_session=True,
    )
    sentinel_file = tmp_path / "unrelated"
    sentinel_file.write_text("keep")
    child(mode)
    try:
        async with coordinator.Coordinator() as owner:
            ready = asyncio.Event()
            task = asyncio.create_task(
                owner.run(request(), on_event=lambda e: ready.set())
            )
            await asyncio.wait_for(ready.wait(), 5)
            pid = int((owner.root / "child.pid").read_text())
            grandchild = owner.root / "grandchild.pid"
            descendant = int(grandchild.read_text()) if grandchild.exists() else None
            started = time.monotonic()
            owner.cancel()
            owner.cancel()
            outcome = await asyncio.wait_for(task, 5)
            assert outcome.cancelled and not outcome.completed
            assert time.monotonic() - started < 5
            gone(pid)
            if descendant:
                gone(descendant)
            assert sentinel.returncode is None and sentinel_file.read_text() == "keep"
    finally:
        sentinel.terminate()
        await sentinel.wait()


async def test_timeout_is_bounded(child, monkeypatch):
    child("ignore")
    monkeypatch.setitem(coordinator.DEADLINES, Operation.PARSE, 0.2)
    async with coordinator.Coordinator() as owner:
        started = time.monotonic()
        result = await asyncio.wait_for(owner.run(request()), 5)
        assert result.error_code == "TIMEOUT" and not result.completed
        assert time.monotonic() - started < 5
        gone(int((owner.root / "child.pid").read_text()))


@pytest.mark.parametrize(
    "mode", ["malformed", "truncated", "oversized", "crash", "success_then_crash"]
)
async def test_bad_child_cannot_be_accepted(child, mode):
    child(mode)
    async with coordinator.Coordinator() as owner:
        result = await asyncio.wait_for(owner.run(request()), 5)
        assert not result.completed and result.error_code in {
            "PROTOCOL",
            "WORKER_CRASH",
        }
        gone(int((owner.root / "child.pid").read_text()))


async def test_flood_does_not_deadlock_or_leak(child):
    child("flood")
    async with coordinator.Coordinator() as owner:
        result = await asyncio.wait_for(owner.run(request()), 5)
        assert result.completed and result.stderr_bytes == MAX_STDERR
        assert "private source" not in repr(result)
        gone(int((owner.root / "child.pid").read_text()))


async def test_cancel_before_start_and_completion_race(child):
    child("success")
    async with coordinator.Coordinator() as owner:
        cancelled = asyncio.Event()
        cancelled.set()
        result = await owner.run(request(), cancellation=cancelled)
        assert result.cancelled and not list(owner.root.iterdir())

        def cancel_on_complete(event):
            if event.kind == EventKind.COMPLETED:
                owner.cancel()

        result = await owner.run(request(), on_event=cancel_on_complete)
        assert result.cancelled and not result.completed


async def test_task_cancel_and_quit_wait_for_reaping(child):
    child("ignore")
    owner = await coordinator.Coordinator().__aenter__()
    ready = asyncio.Event()
    task = asyncio.create_task(owner.run(request(), on_event=lambda e: ready.set()))
    await asyncio.wait_for(ready.wait(), 5)
    pid = int((owner.root / "child.pid").read_text())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 5)
    gone(pid)
    root = owner.root
    await owner.close()
    await owner.close()
    assert not root.exists()


async def test_repeated_task_cancellation_during_spawn_retains_handle(
    child, monkeypatch
):
    child("ignore")
    original = coordinator.asyncio.create_subprocess_exec
    spawned, release = asyncio.Event(), asyncio.Event()

    async def delayed(*args, **kwargs):
        proc = await original(*args, **kwargs)
        spawned.set()
        await release.wait()
        return proc

    monkeypatch.setattr(coordinator.asyncio, "create_subprocess_exec", delayed)
    async with coordinator.Coordinator() as owner:
        task = asyncio.create_task(owner.run(request()))
        await asyncio.wait_for(spawned.wait(), 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        # The child may have been killed before writing its handshake.
        assert not owner._busy


async def test_cancellation_during_cleanup_wins_unaccepted_success(child, monkeypatch):
    child("success")
    entered, release = asyncio.Event(), asyncio.Event()
    original = coordinator.Coordinator._reap_group

    async def gated(self, proc):
        entered.set()
        await release.wait()
        await original(self, proc)

    monkeypatch.setattr(coordinator.Coordinator, "_reap_group", gated)
    async with coordinator.Coordinator() as owner:
        task = asyncio.create_task(owner.run(request()))
        await asyncio.wait_for(entered.wait(), 5)
        owner.cancel()
        release.set()
        result = await asyncio.wait_for(task, 5)
        assert result.cancelled and not result.completed


async def test_concurrent_close_cleans_after_active_child(child):
    child("ignore")
    owner = await coordinator.Coordinator().__aenter__()
    ready = asyncio.Event()
    task = asyncio.create_task(owner.run(request(), on_event=lambda e: ready.set()))
    await asyncio.wait_for(ready.wait(), 5)
    pid = int((owner.root / "child.pid").read_text())
    root = owner.root
    await asyncio.wait_for(owner.close(), 5)
    assert (await task).cancelled and not root.exists()
    gone(pid)


async def test_disk_failure_does_not_spawn_or_touch_unrelated_paths(monkeypatch):
    def fail(*args):
        raise OSError("synthetic disk full")

    monkeypatch.setattr(coordinator, "write_owned", fail)
    async with coordinator.Coordinator() as owner:
        result = await owner.run(request())
        assert result.error_code == "STORAGE" and not list(owner.root.iterdir())


async def test_repeated_task_cancellation_during_cleanup_cannot_release_early(
    child, monkeypatch
):
    child("ignore")
    entered = asyncio.Event()
    original = coordinator.Coordinator._reap_group

    async def cleanup(self, proc):
        entered.set()
        await original(self, proc)

    monkeypatch.setattr(coordinator.Coordinator, "_reap_group", cleanup)
    async with coordinator.Coordinator() as owner:
        ready = asyncio.Event()
        task = asyncio.create_task(owner.run(request(), on_event=lambda e: ready.set()))
        await asyncio.wait_for(ready.wait(), 5)
        pid = int((owner.root / "child.pid").read_text())
        task.cancel()
        await asyncio.wait_for(entered.wait(), 5)
        for _ in range(3):
            task.cancel()
            await asyncio.sleep(0)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        gone(pid)


async def test_cancelled_close_still_cleans_owned_directory(child):
    child("ignore")
    owner = await coordinator.Coordinator().__aenter__()
    ready = asyncio.Event()
    task = asyncio.create_task(owner.run(request(), on_event=lambda e: ready.set()))
    await asyncio.wait_for(ready.wait(), 5)
    pid, root = int((owner.root / "child.pid").read_text()), owner.root
    closing = asyncio.create_task(owner.close())
    await asyncio.sleep(0)
    closing.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(closing, 5)
    assert (await task).cancelled and not root.exists()
    gone(pid)
