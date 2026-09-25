"""Immutable application snapshots. Only service.py replaces authoritative state."""

from dataclasses import dataclass
from enum import StrEnum

from mlforge.contracts import (
    CandidateResult,
    ExperimentSpec,
    ExportOptions,
    PreparedRun,
    TaskKind,
)
from mlforge.datasets.records import Schema, TabularDataset
from mlforge.execution.protocol import EventKind, Identity
from mlforge.tasks import ConfigurationReview


class Activity(StrEnum):
    IDLE = "idle"
    SAVING = "saving_prompt"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CLOSED = "closed"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True)
class Revisions:
    dataset: int = 0
    schema: int = 0
    experiment: int = 0


@dataclass(frozen=True)
class Configuration:
    task: TaskKind | None = None
    target_id: str | None = None
    feature_ids: tuple[str, ...] = ()
    model_ids: tuple[str, ...] = ()
    option: int | None = None
    acknowledgements: tuple[str, ...] = ()
    features_initialized: bool = False

    def __post_init__(self):
        for name in ("feature_ids", "model_ids", "acknowledgements"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True)
class ActiveOperation:
    identity: Identity
    revisions: Revisions
    sequence: int = -1
    phase: str | None = None
    terminal: EventKind | None = None


@dataclass(frozen=True)
class Run:
    id: str
    revisions: Revisions
    experiment: ExperimentSpec
    status: RunStatus = RunStatus.RUNNING
    candidates: tuple[CandidateResult, ...] = ()
    cancelled: bool = False

    def __post_init__(self):
        object.__setattr__(self, "candidates", tuple(self.candidates))


@dataclass(frozen=True)
class Failure:
    code: str
    message: str
    action: str
    row: int | None = None
    column: str | None = None


@dataclass(frozen=True)
class Prediction:
    run_id: str
    revisions: Revisions
    model_id: str
    payload_json: str

    @property
    def data(self):
        import json

        return json.loads(self.payload_json)


@dataclass(frozen=True)
class Session:
    revisions: Revisions = Revisions()
    dataset: TabularDataset | None = None
    schema: Schema | None = None
    confirmed: bool = False
    configuration: Configuration = Configuration()
    review: ConfigurationReview | None = None
    prepared: PreparedRun | None = None
    run: Run | None = None
    selected_model_id: str | None = None
    activity: Activity = Activity.IDLE
    active: ActiveOperation | None = None
    error_code: str | None = None
    failure: Failure | None = None
    exported_path: str | None = None
    export_options: ExportOptions | None = None
    prediction: Prediction | None = None

    @property
    def results(self):
        return self.run.candidates if self.run is not None else ()

    @property
    def selected(self):
        return next(
            (c for c in self.results if c.model_id == self.selected_model_id), None
        )
