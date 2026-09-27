"""Ordered real children preserve accepted candidates across isolated failures."""

import asyncio
import sys
import time
import uuid
from pathlib import Path

import pytest

from mlforge.execution.coordinator import Coordinator
from mlforge.execution.protocol import (
    Artifact,
    Identity,
    Operation,
    ProtocolError,
    Request,
)


def requests():
    run_id = uuid.uuid4().hex
    result = []
    for model in ("classification.logistic", "classification.forest"):
        identity = Identity(run_id, 3, uuid.uuid4().hex, Operation.TRAIN, model)
        result.append(Request(identity, (), (f"{identity.operation_id}/output.json",)))
    return result


@pytest.fixture
def children(monkeypatch):
    original = asyncio.create_subprocess_exec
    launched = []

    def modes(*values):
        queue = iter(values)

        async def spawn(*args, **kwargs):
            # Previous child's group must already be gone before next launch.
            if launched:
                import os

                with pytest.raises(ProcessLookupError):
                    os.killpg(launched[-1], 0)
            child = await original(
                sys.executable,
                str(Path(__file__).parent / "fixtures/child.py"),
                args[3],
                args[4],
                next(queue),
                **kwargs,
            )
            launched.append(child.pid)
            return child

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        return launched

    return modes


@pytest.mark.parametrize("failed", ["failure-CANDIDATE_FAILED", "malformed", "crash"])
@pytest.mark.parametrize("first_fails", [True, False])
async def test_failure_isolation_and_preserved_success(children, failed, first_fails):
    launched = children(*((failed, "success") if first_fails else ("success", failed)))
    async with Coordinator() as owner:
        accepted = []
        result = await asyncio.wait_for(
            owner.run_many(
                requests(),
                on_result=accepted.append,
                abort_codes=frozenset({"PROTOCOL"}),
            ),
            5,
        )
        assert len(launched) == 2 and len(result.outcomes) == 2
        assert len(result.completed) == 1 and not result.all_failed
        assert result.outcomes == tuple(accepted)
        success = result.completed[0]
        assert (
            owner.root / success.result.artifacts[0].name
        ).read_bytes() == b'{"ok":true}'


async def test_all_fail_reports_no_selectable_success(children):
    children("failure-CANDIDATE_FAILED", "failure-CONVERGENCE")
    async with Coordinator() as owner:
        result = await owner.run_many(requests())
        assert result.all_failed and not result.completed and not result.aborted


async def test_shared_error_stops_queue_preserving_prior_success(children):
    launched = children("failure-STALE_RUN", "success")
    async with Coordinator() as owner:
        result = await owner.run_many(requests(), abort_codes=frozenset({"STALE_RUN"}))
        assert result.aborted and len(launched) == 1 and not result.completed


async def test_corrupt_shared_input_never_launches_child(children):
    launched = children("success", "success")
    reqs = requests()
    bad = Artifact("missing.json", 1, "0" * 64)
    reqs[0] = Request(reqs[0].identity, (bad,), reqs[0].outputs)
    async with Coordinator() as owner:
        result = await owner.run_many(reqs)
        assert result.aborted and result.outcomes[0].fatal and not launched


async def test_cancel_after_accepted_result_stops_queue(children):
    launched = children("success", "success")
    async with Coordinator() as owner:
        result = await owner.run_many(requests(), on_result=lambda _: owner.cancel())
        assert result.cancelled and len(launched) == 1 and len(result.completed) == 1


async def test_absolute_run_deadline_stops_queued_work(children):
    launched = children("ignore", "success")
    async with Coordinator() as owner:
        result = await asyncio.wait_for(
            owner.run_many(requests(), deadline=time.monotonic() + 0.2), 5
        )
        assert result.aborted and len(launched) == 1
        assert result.outcomes[0].error_code == "TIMEOUT" and not result.completed


async def test_expired_deadline_and_pre_cancel_do_not_spawn(children):
    launched = children("success", "success")
    async with Coordinator() as owner:
        result = await owner.run_many(requests(), deadline=time.monotonic() - 1)
        assert result.aborted and not launched
        cancelled = asyncio.Event()
        cancelled.set()
        result = await owner.run_many(requests(), cancellation=cancelled)
        assert result.cancelled and not launched


async def test_mismatched_revisions_rejected_before_start(children):
    launched = children("success", "success")
    async with Coordinator() as owner:
        reqs = requests()
        reqs[1] = requests()[1]
        with pytest.raises(ProtocolError):
            await owner.run_many(reqs)
        assert not launched


async def test_worker_reported_shared_protocol_failure_aborts(children):
    launched = children("failure-PROTOCOL", "success")
    async with Coordinator() as owner:
        result = await owner.run_many(requests(), abort_codes=frozenset({"PROTOCOL"}))
        assert result.aborted and len(launched) == 1
        assert result.outcomes[0].reported


async def test_late_event_after_cancel_is_not_delivered(children):
    children("success", "success")
    async with Coordinator() as owner:
        events = []

        def cancel_on_start(event):
            events.append(event)
            owner.cancel()

        result = await owner.run_many(requests(), on_event=cancel_on_start)
        assert result.cancelled and not result.completed
        assert len(events) == 1
