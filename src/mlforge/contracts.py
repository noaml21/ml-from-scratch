"""Shared value records; application state, estimators and processes live elsewhere."""

from dataclasses import dataclass
from enum import StrEnum

from mlforge.datasets.records import Schema


class TaskKind(StrEnum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    REDUCTION = "reduction"

    @property
    def supervised(self) -> bool:
        return self in (self.CLASSIFICATION, self.REGRESSION)


class CandidateStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DomainError(ValueError):
    """Actionable error containing safe diagnostics, never a source value dump."""

    def __init__(
        self,
        code: str,
        message: str,
        action: str,
        *,
        row: int | None = None,
        column: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.action = action
        self.row = row
        self.column = column


@dataclass(frozen=True)
class ExperimentSpec:
    dataset_revision: int
    dataset_fingerprint: str
    task: TaskKind
    target_id: str | None
    feature_ids: tuple[str, ...]
    model_ids: tuple[str, ...]
    option: int | None = None
    seed: int = 42
    acknowledgements: tuple[str, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        for field in ("feature_ids", "model_ids", "acknowledgements"):
            object.__setattr__(self, field, tuple(getattr(self, field)))
        if self.schema_version != 1 or self.seed != 42:
            raise ValueError("Unsupported experiment version or seed")
        if self.task.supervised != (self.target_id is not None):
            raise ValueError("Target presence must match task")
        if not self.feature_ids or len(set(self.feature_ids)) != len(self.feature_ids):
            raise ValueError("Choose distinct features")
        if self.target_id in self.feature_ids:
            raise ValueError("Target cannot be a feature")
        if not self.model_ids or len(set(self.model_ids)) != len(self.model_ids):
            raise ValueError("Choose distinct models")


@dataclass(frozen=True)
class PreparedRun:
    experiment: ExperimentSpec
    schema: Schema
    train_rows: tuple[int, ...]
    test_rows: tuple[int, ...]
    policy_json: str
    environment_json: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "train_rows", tuple(self.train_rows))
        object.__setattr__(self, "test_rows", tuple(self.test_rows))
        if set(self.train_rows) & set(self.test_rows):
            raise ValueError("Training and test partitions must be disjoint")


@dataclass(frozen=True)
class Metric:
    key: str
    value: float | None
    reason: str | None = None


@dataclass(frozen=True)
class ModelBundle:
    """Parent-facing validated handle; no mutable estimator or raw table."""

    directory: str
    model_id: str
    task: TaskKind
    model_sha256: str
    schema_sha256: str
    metadata_json: str


@dataclass(frozen=True)
class CandidateResult:
    model_id: str
    status: CandidateStatus
    elapsed: float
    metrics: tuple[Metric, ...] = ()
    diagnostics_json: str = "{}"
    warnings: tuple[str, ...] = ()
    bundle: ModelBundle | None = None
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", tuple(self.metrics))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        if (self.status == CandidateStatus.COMPLETED) != (self.bundle is not None):
            raise ValueError("Only completed candidates have validated bundles")
