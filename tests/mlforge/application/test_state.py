"""Headless revision/invalidation rules; real worker adapters are tested separately."""

from dataclasses import FrozenInstanceError, replace

import pytest

from mlforge.application.service import Service
from mlforge.application.state import Activity, Configuration, RunStatus
from mlforge.contracts import (
    CandidateResult,
    CandidateStatus,
    DomainError,
    Metric,
    ModelBundle,
    TaskKind,
)
from mlforge.datasets.importers import load_dataset
from mlforge.datasets.inference import infer_schema
from mlforge.execution.protocol import EventKind, Operation, RunEvent


@pytest.fixture
def data(tmp_path):
    path = tmp_path / "synthetic.csv"
    path.write_text(
        "x,z,target,other\n"
        + "".join(f"{i},{i % 7},{i % 2},{i % 3}\n" for i in range(30))
    )
    dataset = load_dataset(path)
    return dataset, infer_schema(dataset)


def terminal(service, identity, kind=EventKind.COMPLETED):
    assert service._event(RunEvent(identity, 0, EventKind.STARTED))
    assert service._event(
        RunEvent(
            identity,
            1,
            kind,
            error_code="CANDIDATE_FAILED" if kind == EventKind.FAILED else None,
        )
    )


def loaded(data):
    service = Service()
    identity = service._begin_operation(Operation.PARSE)
    terminal(service, identity)
    assert service._accept_dataset(identity, *data)
    service.confirm_schema()
    return service


def configured(data):
    service = loaded(data)
    service.choose_task(TaskKind.CLASSIFICATION)
    service.choose_target("c2")
    service.choose_features(["c0", "c1"])
    return service


def candidate(model="classification.logistic", status=CandidateStatus.COMPLETED):
    bundle = (
        ModelBundle(
            "/private/test", model, TaskKind.CLASSIFICATION, "0" * 64, "1" * 64, "{}"
        )
        if status == CandidateStatus.COMPLETED
        else None
    )
    return CandidateResult(
        model,
        status,
        0.1,
        (Metric("macro_f1", 0.7), Metric("accuracy", 0.8)),
        bundle=bundle,
        error_code="CANDIDATE_FAILED" if status == CandidateStatus.FAILED else None,
    )


def accepted(service, *, finish=True, status=CandidateStatus.COMPLETED):
    run = service._begin_training()
    identity = service._begin_operation(Operation.TRAIN, "classification.logistic")
    terminal(
        service,
        identity,
        EventKind.FAILED if status == CandidateStatus.FAILED else EventKind.COMPLETED,
    )
    assert service._accept_candidate(identity, candidate(status=status))
    assert service._end_operation(identity)
    if finish:
        assert service._end_training(run.id)
    return identity, run


def test_snapshots_and_accepted_runs_remain_immutable(data):
    service = configured(data)
    old = service.snapshot
    _, run = accepted(service)
    result = service.snapshot
    service.select_candidate("classification.logistic")
    service.choose_features(["c1"], discard=True)
    assert not old.results and not run.candidates
    assert len(result.results) == 1 and result.run.status == RunStatus.COMPLETED
    assert result.configuration.feature_ids == ("c0", "c1")
    assert not service.snapshot.results and service.snapshot.selected is None
    with pytest.raises(FrozenInstanceError):
        result.run.status = RunStatus.FAILED
    ids = ["c0"]
    config = Configuration(feature_ids=ids)
    ids.append("c1")
    assert config.feature_ids == ("c0",)


@pytest.mark.parametrize(
    "change", ["task", "target", "features", "models", "acknowledgements"]
)
def test_change_requires_one_discard_and_invalidates_results(data, change):
    service = configured(data)
    accepted(service)
    before = service.snapshot

    def edit(discard=False):
        if change == "task":
            service.choose_task(TaskKind.REGRESSION, discard=discard)
        elif change == "target":
            service.choose_target("c3", discard=discard)
        elif change == "features":
            service.choose_features(["c1"], discard=discard)
        elif change == "models":
            service.choose_models(["classification.forest"], discard=discard)
        else:
            service.acknowledge(["LEAKAGE:c1"], discard=discard)

    with pytest.raises(DomainError) as error:
        edit()
    assert error.value.code == "DISCARD" and service.snapshot is before
    edit(True)
    assert service.snapshot.revisions.experiment == before.revisions.experiment + 1
    assert service.snapshot.run is None and service.snapshot.prepared is None
    edit()  # Identical committed choice is harmless, no second discard.
    if change in {"task", "target"}:
        assert not service.snapshot.configuration.feature_ids
    if change == "task":
        assert service.snapshot.configuration.target_id is None


def test_dataset_and_schema_changes_invalidate_every_downstream_choice(data):
    service = configured(data)
    old = service.snapshot
    identity = service._begin_operation(Operation.INSPECT)
    terminal(service, identity)
    assert service._accept_schema(identity, replace(data[1], revision=1))
    assert not service.snapshot.confirmed
    assert service.snapshot.configuration == Configuration()
    assert service.snapshot.revisions.dataset == old.revisions.dataset
    assert service.snapshot.revisions.schema == old.revisions.schema + 1
    identity = service._begin_operation(Operation.PARSE)
    terminal(service, identity)
    assert service._accept_dataset(identity, *data)
    assert service.snapshot.revisions.dataset == old.revisions.dataset + 1
    assert not service.snapshot.confirmed and service.snapshot.run is None


def test_duplicate_stale_sequence_and_terminal_events_do_not_mutate(data):
    service = configured(data)
    run = service._begin_training()
    identity = service._begin_operation(Operation.TRAIN, "classification.logistic")
    assert not service._end_training(run.id)
    before = service.snapshot
    stale = replace(identity, revision=identity.revision - 1)
    assert not service._event(RunEvent(stale, 0, EventKind.STARTED))
    assert not service._event(
        RunEvent(identity, 1, EventKind.PROGRESS, phase="training")
    )
    assert service.snapshot is before
    terminal(service, identity)
    after = service.snapshot
    assert not service._event(RunEvent(identity, 1, EventKind.COMPLETED))
    assert not service._event(RunEvent(identity, 2, EventKind.COMPLETED))
    assert service.snapshot is after
    assert service._accept_candidate(identity, candidate())
    assert not service._accept_candidate(identity, candidate())
    service._end_operation(identity)
    service._end_training(run.id)
    assert not service._end_training(run.id)


@pytest.mark.parametrize("change", ["dataset", "task", "models"])
def test_old_result_after_revision_change_is_rejected(data, change):
    service = configured(data)
    identity, _ = accepted(service)
    if change == "dataset":
        operation = service._begin_operation(Operation.PARSE)
        terminal(service, operation)
        service._accept_dataset(operation, *data)
    elif change == "task":
        service.choose_task(TaskKind.REGRESSION, discard=True)
    else:
        service.choose_models(["classification.forest"], discard=True)
    before = service.snapshot
    assert not service._accept_candidate(identity, candidate())
    assert not service._event(RunEvent(identity, 2, EventKind.COMPLETED))
    assert service.snapshot is before
    with pytest.raises(DomainError):
        service.select_candidate("classification.logistic")


@pytest.mark.parametrize("cancel_first", [True, False])
def test_cancel_completion_crossing_retains_only_already_accepted(data, cancel_first):
    service = configured(data)
    run = service._begin_training()
    identity = service._begin_operation(Operation.TRAIN, "classification.logistic")
    terminal(service, identity)
    if cancel_first:
        service.cancel()
    assert service._accept_candidate(identity, candidate()) == (not cancel_first)
    service.cancel()
    service.cancel()
    assert service.snapshot.activity == Activity.CANCELLING
    with pytest.raises(DomainError, match="locked"):
        service.choose_models([], discard=True)
    service._end_operation(identity)
    service._end_training(run.id)
    assert service.snapshot.run.status == (
        RunStatus.CANCELLED if cancel_first else RunStatus.PARTIAL
    )
    if cancel_first:
        with pytest.raises(DomainError):
            service.select_candidate("classification.logistic")
    else:
        service.select_candidate("classification.logistic")
        assert service.snapshot.selected.bundle is not None


def test_all_failed_and_unaccepted_completion_cannot_be_selected(data):
    service = configured(data)
    identity, _ = accepted(service, status=CandidateStatus.FAILED)
    assert service.snapshot.run.status == RunStatus.FAILED
    with pytest.raises(DomainError):
        service.select_candidate(identity.model_id)
    run = service._begin_training(discard=True)
    identity = service._begin_operation(Operation.TRAIN, "classification.logistic")
    assert not service._accept_candidate(identity, candidate())
    service.cancel()
    service._end_operation(identity)
    service._end_training(run.id)
    assert not service.snapshot.results


def test_active_run_blocks_configuration_and_supersession(data):
    service = configured(data)
    first = service._begin_training()
    with pytest.raises(DomainError):
        service._begin_training(discard=True)
    with pytest.raises(DomainError):
        service._begin_operation(Operation.PARSE)
    with pytest.raises(DomainError):
        service.choose_features([], discard=True)
    service.cancel()
    service._end_training(first.id)
    second = service._begin_training()
    assert second.id != first.id and first.status == RunStatus.RUNNING
    assert not service._end_training(first.id)


def test_export_failure_keeps_selection_and_close_rejects_late_events(data):
    service = configured(data)
    accepted(service)
    service.select_candidate("classification.logistic")
    selected = service.snapshot.selected
    identity = service._begin_operation(Operation.EXPORT, selected.model_id)
    service._end_operation(identity, error_code="EXPORT_IO")
    assert service.snapshot.selected is selected
    identity = service._begin_operation(Operation.EXPORT, selected.model_id)
    service.cancel()
    service._closed()  # Adapter must first await coordinator cleanup (P05.3.b).
    assert service.snapshot.selected is None
    assert not service._event(RunEvent(identity, 0, EventKind.STARTED))
    assert not service._end_operation(identity)
    with pytest.raises(DomainError):
        service.select_candidate(selected.model_id)


def test_invalid_configuration_is_atomic_and_empty_choices_block_training(data):
    service = configured(data)
    old = service.snapshot
    for command in [
        lambda: service.choose_features(["c2"]),
        lambda: service.choose_target("missing"),
        lambda: service.choose_models(["reduction.pca"]),
        lambda: service.choose_option(True),
    ]:
        with pytest.raises(DomainError):
            command()
        assert service.snapshot is old
    service.choose_models([])
    with pytest.raises(DomainError):
        service._begin_training()
    assert service.snapshot.activity == Activity.IDLE


def test_unsupervised_option_invalidates_run_revision_and_target_is_absent(data):
    service = loaded(data)
    service.choose_task(TaskKind.CLUSTERING)
    service.choose_features(["c0", "c1"])
    service.choose_option(3)
    before = service.snapshot
    service.choose_option(4)
    assert service.snapshot.revisions.experiment == before.revisions.experiment + 1
    assert service.experiment().target_id is None
    with pytest.raises(DomainError):
        service.choose_target("c2")
