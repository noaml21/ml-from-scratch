"""Application acceptance and cleanup over real selected pipelines and child faults."""

import asyncio
import os
import sys
from pathlib import Path

import pytest

from mlforge.application.state import Activity
from mlforge.contracts import DomainError, TaskKind
from mlforge.datasets.records import raw_records
from mlforge.execution import coordinator
from mlforge.execution.protocol import EventKind, Operation, RunEvent
from mlforge.models import MODELS

pytestmark = pytest.mark.parametrize(
    "prepared_candidate", [MODELS[0]], indirect=True, ids=lambda model: model.id
)


def inputs(app):
    return raw_records(
        app.snapshot.dataset, app.snapshot.run.experiment.feature_ids, (0,)
    )


@pytest.fixture
def fault_child(monkeypatch):
    original = asyncio.create_subprocess_exec
    pids = []

    def use(mode):
        async def spawn(*args, **kwargs):
            child = await original(
                sys.executable,
                str(Path(__file__).parents[1] / "execution/fixtures/child.py"),
                args[3],
                args[4],
                mode,
                **kwargs,
            )
            pids.append(child.pid)
            return child

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        return pids

    return use


async def test_real_prediction_events_and_active_edits_are_guarded(
    trained_app, tmp_path, monkeypatch
):
    app = trained_app
    original = app._event
    prior = []
    checked = []
    before = app.snapshot

    def event(value):
        accepted = original(value)
        current = app.snapshot
        if value.kind == EventKind.STARTED:
            for change in (
                lambda: app.choose_task(TaskKind.REGRESSION, discard=True),
                lambda: app.choose_features((), discard=True),
                lambda: app.select_candidate(before.selected.model_id),
            ):
                with pytest.raises(DomainError, match="locked"):
                    change()
                assert app.snapshot is current
            for stale in prior:
                assert not original(stale)
                assert app.snapshot is current
            checked.append(value.identity)
        elif value.kind == EventKind.COMPLETED:
            assert not original(value)
            assert app.snapshot is current
            prior.append(value)
        return accepted

    monkeypatch.setattr(app, "_event", event)
    first = await app.predict(inputs(app))
    second = await app.predict(inputs(app))
    assert first.data == second.data and len(checked) == 2
    assert checked[0].operation_id != checked[1].operation_id
    assert checked[0].run_id == checked[1].run_id == before.run.id
    assert app.snapshot.run is before.run
    app.choose_features(("c0",), discard=True)
    current = app.snapshot
    for stale in prior:
        assert not original(stale)
    assert app.snapshot is current and current.prediction is None
    assert first.revisions == before.revisions != current.revisions
    assert before.run.experiment.feature_ids == ("c0", "c1", "c2", "c3")
    with pytest.raises(DomainError):
        await app.export(tmp_path / "stale")


@pytest.mark.parametrize("operation", [Operation.PREDICT, Operation.EXPORT])
async def test_quit_live_inference_locks_source_and_reaps_owned_child(
    trained_app, tmp_path, fault_child, operation
):
    app = trained_app
    pids = fault_child("ignore")
    root = app._coordinator.root
    before = app.snapshot
    destination = tmp_path / "destination"
    destination.mkdir()
    sentinel = destination / "unrelated"
    sentinel.write_text("preserve")
    task = asyncio.create_task(
        app.predict(inputs(app))
        if operation == Operation.PREDICT
        else app.export(destination)
    )
    try:

        async def started():
            while not (app.snapshot.active and app.snapshot.active.sequence >= 0):
                if task.done():
                    pytest.fail(str(app.snapshot.failure))
                await asyncio.sleep(0.01)

        await asyncio.wait_for(started(), 10)
        identity = app.snapshot.active.identity
        with pytest.raises(DomainError, match="locked"):
            await app.load(tmp_path / "changed.csv", discard=True)
        with pytest.raises(DomainError, match="locked"):
            app.choose_models((), discard=True)
        with pytest.raises(DomainError, match="locked"):
            app.select_candidate(before.selected.model_id)
        assert app.snapshot.revisions == before.revisions
        await asyncio.wait_for(app.close(), 5)
        assert await task is None
        assert app.snapshot.activity == Activity.CLOSED
        assert not app._event(RunEvent(identity, 1, EventKind.COMPLETED))
        assert not root.exists()
        assert list(destination.iterdir()) == [sentinel]
        assert sentinel.read_text() == "preserve"
        for pid in pids:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
    finally:
        app.cancel()
        await asyncio.wait_for(task, 5)


@pytest.mark.parametrize(
    ("mode", "code"),
    [
        ("crash", "PROTOCOL"),  # Incomplete stream is rejected before exit status.
        ("malformed", "PROTOCOL"),
        ("success", "PROTOCOL"),  # Valid envelope, invalid export receipt content.
        ("ignore", "TIMEOUT"),
    ],
)
async def test_export_transport_failure_retains_selection_and_cleans_staging(
    trained_app, tmp_path, monkeypatch, fault_child, mode, code
):
    app = trained_app
    selected = app.snapshot.selected
    pids = fault_child(mode)
    if mode == "ignore":
        monkeypatch.setitem(coordinator.DEADLINES, Operation.EXPORT, 0.2)
    destination = tmp_path / "failed"
    destination.mkdir()
    sentinel = destination / "keep"
    sentinel.write_text("unrelated")
    assert await asyncio.wait_for(app.export(destination), 10) is None
    assert app.snapshot.failure.code == code
    assert app.snapshot.activity == Activity.IDLE
    assert app.snapshot.selected is selected
    assert app.snapshot.exported_path is None
    assert list(destination.iterdir()) == [sentinel]
    for pid in pids:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
