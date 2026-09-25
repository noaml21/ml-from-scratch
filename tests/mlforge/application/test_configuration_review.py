"""Real pre-training reviews reuse domain rules without fitting or UI imports."""

import asyncio
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from mlforge.application.service import Service
from mlforge.application.state import Activity
from mlforge.contracts import DomainError, TaskKind
from mlforge.execution.protocol import Operation
from mlforge.tasks import ConfigurationReview, review_data, review_from_data


@pytest.mark.parametrize("task", list(TaskKind))
async def test_real_configuration_review_and_preflight(task):
    async with Service() as app:
        example = next(e for e in app.examples if e.task == task)
        assert await app.load_example(example.filename)
        with pytest.raises(DomainError, match="Confirm"):
            await app.review_configuration()
        app.confirm_schema()
        assert await app.review_configuration()
        assert app.snapshot.configuration.task is None
        assert (
            app.snapshot.review.goal_reasons[[t.task for t in app.tasks].index(task)]
            is None
        )
        app.choose_task(task)
        assert app.snapshot.review is None
        assert await app.review_configuration()
        if task.supervised:
            assert app.snapshot.configuration.target_id is None
            assert not app.snapshot.configuration.features_initialized
            choices = app.snapshot.review.targets
            target = next(c for c in choices if c.default)
            app.choose_target(target.column_id)
            assert await app.review_configuration()
        else:
            assert app.snapshot.review.targets == ()
        review = app.snapshot.review
        config = app.snapshot.configuration
        assert config.features_initialized and config.feature_ids
        assert config.target_id not in config.feature_ids
        assert all(
            c.default == (c.column_id in config.feature_ids) for c in review.features
        )
        snapshot = app.snapshot
        assert await app.review_configuration()
        assert app.snapshot.revisions == snapshot.revisions
        assert app.snapshot.configuration == snapshot.configuration
        app.acknowledge(tuple(w.code for w in review.warnings))
        assert await app.preview_preprocessing()
        prepared = app.snapshot.prepared
        assert prepared.experiment == app.experiment()
        assert bool(prepared.test_rows) == task.supervised
        assert not set(prepared.train_rows) & set(prepared.test_rows)
        assert app.snapshot.run is None and app.snapshot.results == ()
        assert not list(app._coordinator.root.rglob("*.skops"))
        assert await app.preview_preprocessing()
        assert app.snapshot.prepared == prepared
        app.choose_features(())
        assert app.snapshot.prepared is None and app.snapshot.review is None
        assert await app.review_configuration()
        assert app.snapshot.configuration.feature_ids == ()  # Never reselect defaults.
        with pytest.raises(DomainError, match="Complete"):
            await app.preview_preprocessing()


async def test_target_gates_warnings_and_invalidation(tmp_path):
    source = tmp_path / "synthetic.csv"
    source.write_text(
        "x,outcome,target,empty,id,date\n"
        + "".join(f"{i},{i % 2},{i % 2},,{i},2025-01-01\n" for i in range(40))
    )
    original = source.read_bytes()
    async with Service() as app:
        assert await app.load(source)
        app.confirm_schema()
        assert await app.review_configuration()
        app.choose_task("classification")
        assert await app.review_configuration()
        with pytest.raises(DomainError):
            app.choose_target("c3")
        app.choose_target("c2")
        assert await app.review_configuration()
        review = app.snapshot.review
        assert {w.code for w in review.warnings} >= {
            "EQUAL_TARGET:c1",
            "LEAKAGE_NAME:c1",
        }
        assert not next(c for c in review.features if c.column_id == "c4").eligible
        with pytest.raises(DomainError):
            app.choose_features(("c4",))
        assert not await app.preview_preprocessing()
        assert app.snapshot.failure.code == "ACKNOWLEDGEMENT"
        assert app.snapshot.prepared is None
        app.acknowledge(tuple(w.code for w in review.warnings))
        assert await app.preview_preprocessing()
        app.choose_features(("c0",))
        assert (
            app.snapshot.prepared is None
            and not app.snapshot.configuration.acknowledgements
        )
        assert await app.review_configuration()
        assert not app.snapshot.review.warnings
        assert await app.preview_preprocessing()
        assert await app.change_type("c0", "Category")
        assert app.snapshot.review is None and app.snapshot.prepared is None
        assert app.snapshot.configuration.task is None and not app.snapshot.confirmed
    assert source.read_bytes() == original


async def test_stale_review_and_empty_goal_rejection(tmp_path, monkeypatch):
    source = tmp_path / "one.csv"
    source.write_text("x\n1\n")
    async with Service() as app:
        assert await app.load(source)
        app.confirm_schema()
        accepted = []
        original = app._accept_review

        def capture(identity, review):
            accepted.append((identity, review))
            return original(identity, review)

        monkeypatch.setattr(app, "_accept_review", capture)
        assert await app.review_configuration()
        for task in TaskKind:
            with pytest.raises(DomainError):
                app.choose_task(task)
        before = app.snapshot
        assert not original(*accepted[0])  # Duplicate terminal acceptance.
        assert not original(replace(accepted[0][0], revision=99), accepted[0][1])
        assert app.snapshot == before


@pytest.mark.parametrize("summary", [False, True])
async def test_review_and_preflight_cancel_reap_owned_child(
    tmp_path, monkeypatch, summary
):
    async with Service() as app:
        assert await app.load_example("clustering.csv")
        app.confirm_schema()
        app.choose_task("clustering")
        assert await app.review_configuration()
        before = app.snapshot
        original = asyncio.create_subprocess_exec
        pids = []

        async def spawn(*args, **kwargs):
            proc = await original(
                sys.executable,
                str(Path(__file__).parents[1] / "execution/fixtures/child.py"),
                args[3],
                args[4],
                "ignore",
                **kwargs,
            )
            pids.append(proc.pid)
            return proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        pending = asyncio.create_task(
            app.preview_preprocessing() if summary else app.review_configuration()
        )
        async with asyncio.timeout(10):
            while not app.snapshot.active or app.snapshot.active.sequence < 0:
                await asyncio.sleep(0.01)
        assert app.snapshot.active.identity.operation == (
            Operation.PREFLIGHT if summary else Operation.REVIEW
        )
        with pytest.raises(DomainError, match="locked"):
            app.choose_task("regression")
        app.cancel()
        assert not await asyncio.wait_for(pending, 5)
        assert app.snapshot.activity == Activity.IDLE
        assert app.snapshot.configuration == before.configuration
        assert app.snapshot.review == before.review and app.snapshot.prepared is None
        for pid in pids:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)


def test_review_codec_rejects_corrupt_metadata():
    original = review_data(ConfigurationReview((None,) * 4))
    assert (
        review_from_data(json.loads(json.dumps(original))).goal_reasons == (None,) * 4
    )
    for change in (
        {"goal_reasons": [None]},
        {"selected_features": ["c0"]},
        {"bounds": [True, 2, 2]},
        {"bounds": [2, 1, 3]},
        {
            "targets": [
                {
                    "column_id": "c0",
                    "name": "x",
                    "eligible": False,
                    "reason": "No",
                    "default": True,
                }
            ]
        },
        {"warnings": [{"code": "bad", "message": "bad", "column_id": "c0"}]},
    ):
        with pytest.raises(ValueError):
            review_from_data(original | change)


async def test_feature_count_reinitializes_only_invalid_pca_option():
    async with Service() as app:
        example = next(e for e in app.examples if e.task == TaskKind.REDUCTION)
        assert await app.load_example(example.filename)
        app.confirm_schema()
        app.choose_task("reduction")
        assert await app.review_configuration()
        features = app.snapshot.configuration.feature_ids
        assert len(features) >= 3 and app.snapshot.configuration.option == 2
        app.choose_features(features[:2])
        assert app.snapshot.configuration.option is None
        assert await app.review_configuration()
        assert app.snapshot.configuration.option == 1
        app.acknowledge(tuple(w.code for w in app.snapshot.review.warnings))
        assert await app.preview_preprocessing()
        app.choose_features(features)
        assert await app.review_configuration()
        assert app.snapshot.configuration.option == 1  # Preserve a valid choice.


async def test_incomplete_worker_review_cannot_replace_valid_configuration(monkeypatch):
    async with Service() as app:
        assert await app.load_example("clustering.csv")
        app.confirm_schema()
        app.choose_task("clustering")
        assert await app.review_configuration()
        prior = app.snapshot.configuration
        accept = app._accept_review

        def incomplete(identity, review):
            return accept(identity, replace(review, features=review.features[:-1]))

        monkeypatch.setattr(app, "_accept_review", incomplete)
        assert not await app.review_configuration()
        assert app.snapshot.configuration == prior
        assert app.snapshot.activity == Activity.IDLE


async def test_preflight_does_not_trap_an_empty_model_selection():
    async with Service() as app:
        assert await app.load_example("clustering.csv")
        app.confirm_schema()
        app.choose_task("clustering")
        assert await app.review_configuration()
        app.choose_models(())
        assert await app.preview_preprocessing()
        assert app.snapshot.configuration.model_ids == ()
        assert app.snapshot.run is None
        with pytest.raises(DomainError):
            await app.train()
