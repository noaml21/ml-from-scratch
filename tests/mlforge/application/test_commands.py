"""Real application commands use the production worker and owned cleanup."""

import asyncio
import os
import sys
from pathlib import Path

import pytest

from mlforge.application.service import Service
from mlforge.application.state import Activity
from mlforge.contracts import DomainError
from mlforge.datasets.records import ColumnType
from mlforge.execution.protocol import EventKind, RunEvent


async def test_actual_load_override_reset_and_source_preservation(tmp_path):
    source = tmp_path / "synthetic.csv"
    original = "zip,x\n001,1\n002,2\n003,3\n"
    source.write_text(original)
    async with Service() as app:
        root = app._coordinator.root
        assert await app.load(source)
        assert app.snapshot.dataset.rows[0][0].raw_text == "001"
        app.confirm_schema()
        before = app.snapshot
        assert await app.change_type("c0", ColumnType.NUMBER)
        assert app.snapshot.schema.profile("c0").overridden
        assert app.snapshot.revisions.schema == before.revisions.schema + 1
        assert not app.snapshot.confirmed
        assert await app.change_type("c0", None)
        assert not app.snapshot.schema.profile("c0").overridden
        assert app.snapshot.activity == Activity.IDLE
    assert app.snapshot.activity == Activity.CLOSED and not root.exists()
    assert source.read_text() == original


async def test_failed_load_and_override_preserve_prior_valid_state(tmp_path):
    source = tmp_path / "synthetic.csv"
    source.write_text("x,name\n1,north\n2,south\n")
    async with Service() as app:
        assert await app.load(source)
        before = app.snapshot
        assert not await app.change_type("c1", ColumnType.NUMBER)
        assert app.snapshot.schema is before.schema
        assert app.snapshot.error_code and app.snapshot.activity == Activity.IDLE
        assert not await app.load(tmp_path / "missing.csv")
        assert app.snapshot.dataset is before.dataset
        assert await app.load(source)
        assert await app.change_type("c0", ColumnType.CATEGORY)
        assert app.snapshot.error_code is None
        with pytest.raises(DomainError, match="local file"):
            await app.load("https://example.test/data.csv")


@pytest.mark.parametrize("operation", ["parse", "inspect"])
@pytest.mark.parametrize("action", ["cancel", "quit", "task-cancel"])
async def test_cancel_and_quit_reap_actual_blocked_worker(
    action, operation, tmp_path, monkeypatch
):
    original = asyncio.create_subprocess_exec
    launched = []

    async def spawn(*args, **kwargs):
        proc = await original(
            sys.executable,
            str(Path(__file__).parents[1] / "execution/fixtures/child.py"),
            args[3],
            args[4],
            "ignore",
            **kwargs,
        )
        launched.append(proc.pid)
        return proc

    app = await Service().__aenter__()
    source = tmp_path / "synthetic.csv"
    source.write_text("x\n1\n2\n")
    if operation == "inspect":
        assert await app.load(source)
    prior = app.snapshot
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    root = app._coordinator.root
    if action == "quit":
        end = app._end_operation

        def ending(*args, **kwargs):
            result = end(*args, **kwargs)
            # Exercise the cleanup gap before close's idle waiter resumes.
            with pytest.raises(DomainError, match="locked"):
                app._open_command()
            return result

        monkeypatch.setattr(app, "_end_operation", ending)
    task = asyncio.create_task(
        app.load(source)
        if operation == "parse"
        else app.change_type("c0", ColumnType.CATEGORY)
    )
    try:

        async def started():
            while not app.snapshot.active or app.snapshot.active.sequence < 0:
                await asyncio.sleep(0.01)

        await asyncio.wait_for(started(), 5)
        with pytest.raises(DomainError, match="locked"):
            await app.load(tmp_path / "another.csv")
        if action == "quit":
            await asyncio.wait_for(app.close(), 5)
            assert not await task
            assert app.snapshot.activity == Activity.CLOSED
        elif action == "task-cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 5)
        else:
            app.cancel()
            assert app.snapshot.activity == Activity.CANCELLING
            assert not await asyncio.wait_for(task, 5)
        assert app.snapshot.dataset is prior.dataset
        assert app.snapshot.schema is prior.schema
        for pid in launched:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
    finally:
        await app.close()
    assert not root.exists()


async def test_quit_locks_new_commands_immediately(tmp_path):
    app = await Service().__aenter__()
    closing = asyncio.create_task(app.close())
    await asyncio.sleep(0)
    with pytest.raises(DomainError, match="locked"):
        await app.load(tmp_path / "synthetic.csv")
    await closing
    assert app.snapshot.activity == Activity.CLOSED


async def test_input_staging_disk_failure_is_safe(tmp_path, monkeypatch):
    source = tmp_path / "synthetic.csv"
    source.write_text("x\n1\n2\n")
    async with Service() as app:
        assert await app.load(source)
        schema = app.snapshot.schema

        def fail(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("mlforge.application.service.write_owned", fail)
        assert not await app.change_type("c0", ColumnType.CATEGORY)
        assert app.snapshot.schema is schema
        assert app.snapshot.error_code == "STORAGE"
        assert app.snapshot.activity == Activity.IDLE


async def test_real_completion_duplicate_and_old_source_cannot_replace_new_source(
    tmp_path, monkeypatch
):
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    first.write_text("x\n1\n2\n")
    second.write_text("x\n3\n4\n")
    async with Service() as app:
        original = app._event
        identities = []

        def event(value):
            accepted = original(value)
            if value.kind == EventKind.COMPLETED:
                identities.append(value.identity)
                snapshot = app.snapshot
                assert not original(value)
                assert app.snapshot is snapshot
            return accepted

        monkeypatch.setattr(app, "_event", event)
        assert await app.load(first)
        old = app.snapshot
        assert await app.load(second)
        current = app.snapshot
        assert current.revisions.dataset == old.revisions.dataset + 1
        assert not app._event(RunEvent(identities[0], 99, EventKind.COMPLETED))
        assert not app._accept_dataset(identities[0], old.dataset, old.schema)
        assert app.snapshot is current
        assert app.snapshot.dataset.rows[0][0].raw_text == "3"
