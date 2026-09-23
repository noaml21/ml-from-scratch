"""Real preparation/training composed through the authoritative application service."""

import asyncio
import hashlib
import json
import os
import sys
import threading
from pathlib import Path

import pytest

from mlforge.application import artifacts
from mlforge.application.service import Service
from mlforge.application.state import Activity, RunStatus
from mlforge.contracts import CandidateStatus, DomainError, TaskKind
from mlforge.execution.protocol import EventKind, Operation, Request, decode, read_owned
from mlforge.tasks import review_warnings


async def configure(app, tmp_path, task=TaskKind.CLASSIFICATION):
    path = tmp_path / f"{task}.csv"
    path.write_text(
        "x,z,outcome\n"
        + "".join(
            f"{i % 13},{i // 5 + 0.1 * (i % 3)},"
            f"{i * 1.5 if task == TaskKind.REGRESSION else i % 2}\n"
            for i in range(60)
        )
    )
    assert await app.load(path)
    app.confirm_schema()
    app.choose_task(task)
    if task.supervised:
        app.choose_target("c2")
    app.choose_features(("c0", "c1"))
    if not task.supervised:
        app.choose_option(1 if task == TaskKind.REDUCTION else 3)
    spec = app.experiment()
    app.acknowledge(
        tuple(
            w.code
            for w in review_warnings(app.snapshot.dataset, app.snapshot.schema, spec)
        )
    )


@pytest.mark.parametrize("task", list(TaskKind))
async def test_real_tasks_accept_exact_evaluated_bundles(tmp_path, task):
    async with Service() as app:
        await configure(app, tmp_path, task)
        before = app.snapshot
        assert await app.train(), app.snapshot.failure
        snapshot = app.snapshot
        assert snapshot.run.status == RunStatus.COMPLETED
        assert len(snapshot.results) == (2 if task.supervised else 1)
        assert all(c.status == CandidateStatus.COMPLETED for c in snapshot.results)
        assert snapshot.run.revisions == before.revisions
        assert snapshot.prepared.experiment == snapshot.run.experiment
        assert not before.results and snapshot.activity == Activity.IDLE
        for candidate in snapshot.results:
            bundle = candidate.bundle
            assert (
                hashlib.sha256(
                    (Path(bundle.directory) / "model.skops").read_bytes()
                ).hexdigest()
                == bundle.model_sha256
            )
            meta = json.loads(bundle.metadata_json)
            assert meta["training_count"] == len(snapshot.prepared.train_rows)
            assert meta["test_count"] == len(snapshot.prepared.test_rows)
            app.select_candidate(candidate.model_id)
            assert app.snapshot.selected is candidate
        assert app.ranked_results
        assert bool(app.recommended) == task.supervised
        app.choose_features(("c0",), discard=True)
        assert not app.snapshot.results and not app._bundles
        assert snapshot.run.status == RunStatus.COMPLETED
        with pytest.raises(DomainError):
            app.select_candidate(snapshot.results[0].model_id)


@pytest.fixture
def train_children(monkeypatch):
    original = asyncio.create_subprocess_exec
    launched = []

    def modes(*modes):
        queue = iter(modes)

        async def spawn(*args, **kwargs):
            req = decode(read_owned(Path(args[3]), f"request-{args[4]}.json"), Request)
            mode = next(queue) if req.identity.operation == Operation.TRAIN else None
            command = (
                (
                    sys.executable,
                    str(Path(__file__).parents[1] / "execution/fixtures/child.py"),
                    args[3],
                    args[4],
                    mode,
                )
                if mode
                else args
            )
            child = await original(*command, **kwargs)
            launched.append(child.pid)
            return child

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        return launched

    return modes


@pytest.mark.parametrize("first_fails", [True, False])
async def test_real_success_retained_across_candidate_local_failure(
    tmp_path, train_children, first_fails
):
    train_children(
        *(
            ("failure-CONVERGENCE", None)
            if first_fails
            else (None, "failure-CONVERGENCE")
        )
    )
    async with Service() as app:
        await configure(app, tmp_path)
        assert await app.train()
        assert len(app.ranked_results) == 1 and len(app.snapshot.results) == 2
        failed = next(
            c for c in app.snapshot.results if c.status == CandidateStatus.FAILED
        )
        with pytest.raises(DomainError):
            app.select_candidate(failed.model_id)
        assert app.recommended[1] == "Only completed model"


async def test_all_failed_has_no_selection_and_valid_retry(tmp_path, train_children):
    train_children("failure-CONVERGENCE", "failure-CANDIDATE_FAILED", None, None)
    async with Service() as app:
        await configure(app, tmp_path)
        assert not await app.train()
        assert app.snapshot.run.status == RunStatus.FAILED
        assert app.snapshot.error_code == "ALL_FAILED" and not app.ranked_results
        old = app.snapshot.run
        assert await app.train(discard=True)
        assert old.id != app.snapshot.run.id
        assert not app._end_training(old.id)
        assert old.status == RunStatus.FAILED


async def test_cancel_second_candidate_preserves_first_and_blocks_edit(
    tmp_path, train_children
):
    pids = train_children(None, "ignore")
    async with Service() as app:
        await configure(app, tmp_path)
        task = asyncio.create_task(app.train())

        async def second_started():
            while not (
                app.snapshot.active
                and app.snapshot.active.identity.model_id == "classification.forest"
                and app.snapshot.active.sequence >= 0
            ):
                if task.done():
                    pytest.fail(str(app.snapshot.failure))
                await asyncio.sleep(0.01)

        await asyncio.wait_for(second_started(), 15)
        before = app.snapshot.revisions
        with pytest.raises(DomainError, match="locked"):
            app.choose_task(TaskKind.REGRESSION, discard=True)
        assert app.snapshot.revisions == before
        app.cancel()
        assert not await asyncio.wait_for(task, 5)
        assert (
            app.snapshot.run.status == RunStatus.PARTIAL
            and len(app.snapshot.results) == 1
        )
        app.select_candidate("classification.logistic")
        for pid in pids:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)


async def test_cancel_on_provisional_completion_never_becomes_success(
    tmp_path, monkeypatch
):
    async with Service() as app:
        await configure(app, tmp_path)
        original = app._event

        def event(value):
            result = original(value)
            if (
                value.identity.operation == Operation.TRAIN
                and value.kind == EventKind.COMPLETED
            ):
                app.cancel()
            return result

        monkeypatch.setattr(app, "_event", event)
        assert not await app.train()
        assert (
            app.snapshot.run.status == RunStatus.CANCELLED and not app.snapshot.results
        )


@pytest.mark.parametrize("cancel_task", [False, True])
async def test_cancel_during_accepted_transport_decode_retains_valid_candidate(
    tmp_path, monkeypatch, cancel_task
):
    entered, release = threading.Event(), threading.Event()
    original = artifacts.candidate_result

    def read(*args):
        result = original(*args)
        entered.set()
        assert release.wait(10)
        return result

    monkeypatch.setattr(artifacts, "candidate_result", read)
    async with Service() as app:
        await configure(app, tmp_path)
        task = asyncio.create_task(app.train())
        try:

            async def ready():
                while not entered.is_set():
                    if task.done():
                        pytest.fail(str(app.snapshot.failure))
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(ready(), 15)
            task.cancel() if cancel_task else app.cancel()
        finally:
            release.set()
        if cancel_task:
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 5)
        else:
            assert not await asyncio.wait_for(task, 5)
        assert app.snapshot.run.status == RunStatus.PARTIAL
        assert len(app.snapshot.results) == 1
        app.select_candidate("classification.logistic")


async def test_invalid_preparation_has_action_and_unlocks_configuration(tmp_path):
    async with Service() as app:
        await configure(app, tmp_path)
        app.choose_features(())
        with pytest.raises(DomainError):
            await app.train()
        assert app.snapshot.activity == Activity.IDLE
        app.choose_features(("c0",))
        app.choose_task(TaskKind.REDUCTION)
        app.choose_features(("c0",))
        app.choose_option(1)
        assert not await app.train()
        assert app.snapshot.failure.code == "FEATURE"
        assert (
            app.snapshot.failure.action and app.snapshot.run.status == RunStatus.FAILED
        )


async def test_shared_failure_stops_queued_candidate(tmp_path, train_children):
    pids = train_children("failure-STORAGE", None)
    async with Service() as app:
        await configure(app, tmp_path)
        assert not await app.train()
        assert len(pids) == 3  # parse, preparation and first candidate only
        assert len(app.snapshot.results) == 1
        assert app.snapshot.failure.code == "STORAGE"
        assert not app.ranked_results


async def test_quit_with_live_training_worker_cleans_all_owned_work(
    tmp_path, train_children
):
    pids = train_children("ignore", None)
    app = await Service().__aenter__()
    root = app._coordinator.root
    try:
        await configure(app, tmp_path)
        task = asyncio.create_task(app.train())

        async def started():
            while not (
                app.snapshot.active
                and app.snapshot.active.identity.operation == Operation.TRAIN
                and app.snapshot.active.sequence >= 0
            ):
                if task.done():
                    pytest.fail(str(app.snapshot.failure))
                await asyncio.sleep(0.01)

        await asyncio.wait_for(started(), 15)
        await asyncio.wait_for(app.close(), 5)
        assert not await task
        assert app.snapshot.activity == Activity.CLOSED
        assert not root.exists()
        for pid in pids:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
    finally:
        await app.close()


async def test_candidate_semantic_mismatch_is_rejected_after_transport_integrity(
    tmp_path,
):
    from mlforge.execution.coordinator import Outcome
    from mlforge.execution.protocol import (
        Identity,
        ProtocolError,
        Result,
        json_data,
        parse_json,
        write_owned,
    )

    async with Service() as app:
        await configure(app, tmp_path)
        app.choose_models(("classification.logistic",))
        assert await app.train()
        accepted = app.snapshot
        refs = app._bundles["classification.logistic"]
        operation_id = refs[0].name.split("/")[0]
        identity = Identity(
            accepted.run.id,
            accepted.revisions.experiment,
            operation_id,
            Operation.TRAIN,
            "classification.logistic",
        )
        raw = {ref.name: read_owned(app._coordinator.root, ref.name) for ref in refs}
        for index, changed in enumerate(("metrics", "diagnostics_json", "warnings")):
            root = tmp_path / f"forged-{index}"
            root.mkdir(mode=0o700)
            (root / operation_id).mkdir(mode=0o700)
            value = parse_json(raw[refs[0].name])
            if changed == "metrics":
                value["metrics"][0]["value"] = 0.123456
            elif changed == "diagnostics_json":
                value[changed] = "{}"
            else:
                value[changed] = ["FORGED_WARNING"]
            forged = tuple(
                write_owned(
                    root, name, json_data(value) if name == refs[0].name else data
                )
                for name, data in raw.items()
            )
            request = Request(identity, (), tuple(a.name for a in forged))
            outcome = Outcome(request, Result(identity, forged), returncode=0)
            with pytest.raises(ProtocolError):
                artifacts.candidate_result(root, outcome, accepted.prepared)
        assert app.snapshot is accepted
