"""Selected real pipelines, immutable predictions and parent-only export publication."""

import asyncio
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

from mlforge.application.state import Activity
from mlforge.contracts import DomainError, TaskKind
from mlforge.datasets.records import raw_records
from mlforge.execution.protocol import EventKind, Operation, Request, decode, read_owned
from mlforge.prediction.runtime import Predictor


def probes(app):
    return raw_records(
        app.snapshot.dataset, app.snapshot.run.experiment.feature_ids, (0, 1)
    )


def same(actual, expected):
    assert len(actual) == len(expected)
    for left, right in zip(actual, expected, strict=True):
        assert left.keys() == right.keys()
        assert left["warnings"] == right["warnings"]
        for key in left.keys() - {"warnings"}:
            if type(right[key]) is str:
                assert left[key] == right[key]
            else:
                np.testing.assert_allclose(left[key], right[key], rtol=1e-8, atol=1e-10)


async def test_prediction_exact_pipeline_errors_retry_and_invalidation(trained_app):
    app = trained_app
    candidate = app.snapshot.selected
    bundle = candidate.bundle
    model_path = Path(bundle.directory) / "model.skops"
    original = model_path.read_bytes()
    predictor = Predictor._from_directory(bundle.directory)
    operation = (
        predictor.transform_many
        if bundle.task == TaskKind.REDUCTION
        else predictor.predict_many
    )
    records = probes(app)
    result = await app.predict(records)
    assert result is app.snapshot.prediction
    assert result.run_id == app.snapshot.run.id
    assert (
        result.revisions == app.snapshot.revisions
        and result.model_id == candidate.model_id
    )
    same(result.data, operation(records))
    view = result.data
    view[0].clear()
    assert result.data[0]  # Snapshot holds immutable JSON, callers get copies.
    assert await app.predict([{"unexpected": "private input"}]) is None
    assert app.snapshot.failure.code == "PREDICT_INPUT"
    assert app.snapshot.selected is candidate and app.snapshot.prediction is None
    assert await app.predict(records)
    assert model_path.read_bytes() == original
    app.choose_models((), discard=True)
    assert app.snapshot.prediction is None
    with pytest.raises(DomainError):
        await app.predict(records)
    with pytest.raises(DomainError):
        await app.export(Path(bundle.directory).parent / "unused")


async def test_export_exact_bytes_context_and_no_replace(trained_app, tmp_path):
    app = trained_app
    candidate = app.snapshot.selected
    bundle = candidate.bundle
    source = Path(bundle.directory)
    original_metadata = (source / "metadata.json").read_bytes()
    if bundle.task == TaskKind.CLASSIFICATION:
        assert (
            json.loads(original_metadata)["split_policy"] == "80/20 stratified holdout"
        )
    destination = tmp_path / "chosen"
    destination.mkdir()
    sentinel = destination / "unrelated"
    sentinel.write_text("keep")
    path = await app.export(destination, "foo__bar_", "1.0.0")
    assert path == str(destination / "foo_bar-1.0.0-py3-none-any.whl"), (
        app.snapshot.failure
    )
    assert app.snapshot.exported_path == path
    with zipfile.ZipFile(path) as archive:
        assert (
            hashlib.sha256(archive.read("foo__bar_/model.skops")).hexdigest()
            == bundle.model_sha256
        )
        assert (
            archive.read("foo__bar_/schema.json")
            == (source / "schema.json").read_bytes()
        )
        assert (
            json.loads(archive.read("foo__bar_/metadata.json"))["partial_run"] is False
        )
        assert all("probes" not in name for name in archive.namelist())
    wheel = Path(path).read_bytes()
    assert await app.export(destination, "foo__bar_", "1.0.0") is None
    assert app.snapshot.failure.code == "EXPORT_EXISTS"
    assert app.snapshot.selected is candidate and Path(path).read_bytes() == wheel
    assert (source / "metadata.json").read_bytes() == original_metadata
    assert not list(destination.glob(".mlforge-*"))
    assert sentinel.read_text() == "keep"


async def test_partial_run_export_context_does_not_mutate_bundle(
    trained_app, tmp_path, monkeypatch
):
    import threading

    from mlforge.application import artifacts
    from mlforge.application.state import RunStatus

    app = trained_app
    model_id = app.snapshot.selected.model_id
    original = artifacts.candidate_result
    loop = asyncio.get_running_loop()
    cancelled = threading.Event()

    def cancel():
        app.cancel()
        cancelled.set()

    def decode_accepted(*args):
        value = original(*args)
        loop.call_soon_threadsafe(cancel)
        assert cancelled.wait(5)
        return value

    with monkeypatch.context() as patch:
        patch.setattr(artifacts, "candidate_result", decode_accepted)
        assert not await app.train(discard=True)
    assert app.snapshot.run.status == RunStatus.PARTIAL
    app.select_candidate(model_id)
    candidate = app.snapshot.selected
    metadata = candidate.bundle.metadata_json
    path = await app.export(tmp_path / "partial", "partial_model", "1.0.0")
    assert path, app.snapshot.failure
    with zipfile.ZipFile(path) as archive:
        assert (
            json.loads(archive.read("partial_model/metadata.json"))["partial_run"]
            is True
        )
        assert b"Partial run: True" in archive.read("partial_model/MODEL_CARD.md")
        assert (
            hashlib.sha256(archive.read("partial_model/model.skops")).hexdigest()
            == candidate.bundle.model_sha256
        )
    assert candidate.bundle.metadata_json == metadata
    assert json.loads(metadata)["partial_run"] is False


@pytest.mark.parametrize("operation", [Operation.PREDICT, Operation.EXPORT])
async def test_cancel_on_provisional_completion_rejects_result(
    trained_app, tmp_path, monkeypatch, operation
):
    app = trained_app
    selected = app.snapshot.selected
    original = app._event

    def event(value):
        result = original(value)
        if value.identity.operation == operation and value.kind == EventKind.COMPLETED:
            app.cancel()
        return result

    monkeypatch.setattr(app, "_event", event)
    if operation == Operation.EXPORT:
        destination = tmp_path / "cancelled"
        assert await app.export(destination) is None
        assert not list(destination.iterdir())
    else:
        assert await app.predict(probes(app)) is None
        assert app.snapshot.prediction is None
    assert app.snapshot.selected is selected and app.snapshot.activity == Activity.IDLE


async def test_quit_during_export_reaps_worker_and_preserves_destination(
    trained_app, tmp_path, monkeypatch
):
    app = trained_app
    original = asyncio.create_subprocess_exec
    pids = []

    async def spawn(*args, **kwargs):
        request = decode(read_owned(Path(args[3]), f"request-{args[4]}.json"), Request)
        assert request.identity.operation == Operation.EXPORT
        proc = await original(
            sys.executable,
            str(Path(__file__).parents[1] / "execution/fixtures/export_child.py"),
            args[3],
            args[4],
            **kwargs,
        )
        pids.append(proc.pid)
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    root = app._coordinator.root
    destination = tmp_path / "owned"
    destination.mkdir()
    sentinel = destination / "keep"
    sentinel.write_text("unrelated")
    task = asyncio.create_task(app.export(destination))
    try:

        async def ready():
            while not (root / "publication-ready.json").exists():
                if task.done():
                    pytest.fail(str(app.snapshot.failure))
                await asyncio.sleep(0.01)

        await asyncio.wait_for(ready(), 40)
        await asyncio.wait_for(app.close(), 5)
        assert await task is None
        assert not root.exists()
        assert list(destination.iterdir()) == [sentinel]
        for pid in pids:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
    finally:
        app.cancel()
        await asyncio.wait_for(task, 5)
