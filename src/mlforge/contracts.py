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


def distribution_name(module_name: str) -> str:
    """PEP distribution normalization, preserving Python's separate import name."""
    import re

    return re.sub(r"[-_.]+", "-", module_name).lower().rstrip("-")


@dataclass(frozen=True)
class ExportOptions:
    """Shared syntax and deterministic filename; exporter checks reserved names."""

    module_name: str
    version: str

    def __post_init__(self):
        import keyword
        import re

        if (
            type(self.module_name) is not str
            or re.fullmatch(r"[a-z][a-z0-9_]{2,49}", self.module_name) is None
            or keyword.iskeyword(self.module_name)
        ):
            raise DomainError(
                "PACKAGE_NAME",
                "Choose a valid, non-reserved module name.",
                "Use 3–50 lowercase letters, digits or underscores; "
                "start with a letter.",
            )
        if (
            type(self.version) is not str
            or re.fullmatch(
                r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", self.version
            )
            is None
        ):
            raise DomainError(
                "PACKAGE_VERSION",
                "Use a three-part version such as 1.0.0.",
                "Use nonnegative integers without leading zeros.",
            )

    @property
    def wheel_stem(self):
        return f"{distribution_name(self.module_name).replace('-', '_')}-{self.version}"

    @property
    def wheel_name(self):
        return f"{self.wheel_stem}-py3-none-any.whl"


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


def _metadata(text, maximum):
    """Validate immutable JSON objects, including nested scalar values."""
    import json
    import math

    from mlforge.datasets.records import record_text

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate metadata key")
            result[key] = value
        return result

    def walk(value, depth=0):
        if depth > 12:
            raise ValueError("Metadata nesting exceeds limit")
        if isinstance(value, dict):
            for key, item in value.items():
                record_text(key, maximum)
                walk(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                walk(item, depth + 1)
        elif isinstance(value, str):
            record_text(value, maximum)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Nonfinite metadata")
        elif type(value) is int and abs(value) > 2**53 - 1:
            raise ValueError("Metadata integer exceeds limit")

    try:
        value = json.loads(record_text(text, maximum), object_pairs_hook=pairs)
        if type(value) is not dict:
            raise ValueError("Metadata must be an object")
        walk(value)
    except RecursionError:
        raise ValueError("Metadata nesting exceeds limit") from None
    return value


def experiment_data(spec):
    from dataclasses import asdict

    value = asdict(spec)
    value["task"] = spec.task.value
    for key in ("feature_ids", "model_ids", "acknowledgements"):
        value[key] = list(value[key])
    return value


def experiment_from_data(value):
    from mlforge.datasets.records import record_count, record_keys, record_text

    record_keys(
        value,
        "dataset_revision dataset_fingerprint task target_id feature_ids model_ids "
        "option seed acknowledgements schema_version",
    )
    record_count(value["dataset_revision"])
    record_text(value["dataset_fingerprint"], 64)
    if value["target_id"] is not None:
        record_text(value["target_id"], 8)
    for key, maximum in (
        ("feature_ids", 100),
        ("model_ids", 2),
        ("acknowledgements", 1000),
    ):
        if type(value[key]) is not list or len(value[key]) > maximum:
            raise ValueError("Invalid experiment selection")
        for item in value[key]:
            record_text(item, 128)
    if value["option"] is not None:
        record_count(value["option"], 10)
    record_count(value["seed"])
    record_count(value["schema_version"])
    return ExperimentSpec(**dict(value, task=TaskKind(value["task"])))


def prepared_data(prepared):
    from mlforge.datasets.records import schema_data

    return {
        "experiment": experiment_data(prepared.experiment),
        "schema": schema_data(prepared.schema),
        "train_rows": list(prepared.train_rows),
        "test_rows": list(prepared.test_rows),
        "policy_json": prepared.policy_json,
        "environment_json": prepared.environment_json,
    }


def prepared_from_data(value):
    from mlforge.datasets.records import (
        record_count,
        record_keys,
        schema_from_data,
    )

    record_keys(
        value, "experiment schema train_rows test_rows policy_json environment_json"
    )
    for key in ("train_rows", "test_rows"):
        if type(value[key]) is not list or len(value[key]) > 20000:
            raise ValueError("Invalid split")
        for row in value[key]:
            record_count(row, 19999)
        if len(set(value[key])) != len(value[key]):
            raise ValueError("Duplicate split row")
    all_rows = value["train_rows"] + value["test_rows"]
    if not value["train_rows"] or set(all_rows) != set(range(len(all_rows))):
        raise ValueError("Incomplete split")
    for key in ("policy_json", "environment_json"):
        _metadata(value[key], 65536)
    return PreparedRun(
        experiment_from_data(value["experiment"]),
        schema_from_data(value["schema"]),
        value["train_rows"],
        value["test_rows"],
        value["policy_json"],
        value["environment_json"],
    )


def candidate_data(candidate):
    from dataclasses import asdict

    value = asdict(candidate)
    value["status"] = candidate.status.value
    value["metrics"] = list(value["metrics"])
    value["warnings"] = list(value["warnings"])
    if candidate.bundle:
        value["bundle"].pop("directory")
        value["bundle"]["task"] = candidate.bundle.task.value
    return value


def candidate_from_data(value, directory):
    import math
    import re

    from mlforge.datasets.records import record_keys, record_text

    record_keys(
        value,
        "model_id status elapsed metrics diagnostics_json warnings bundle "
        "error_code error_message",
    )
    record_text(value["model_id"], 64)
    if (
        type(value["elapsed"]) not in (int, float)
        or not math.isfinite(value["elapsed"])
        or value["elapsed"] < 0
    ):
        raise ValueError("Invalid elapsed")
    if type(value["metrics"]) is not list or len(value["metrics"]) > 8:
        raise ValueError("Invalid metrics")
    metrics = []
    for item in value["metrics"]:
        record_keys(item, "key value reason")
        record_text(item["key"], 64)
        if item["value"] is not None and (
            type(item["value"]) not in (int, float) or not math.isfinite(item["value"])
        ):
            raise ValueError("Invalid metric value")
        if item["reason"] is not None:
            record_text(item["reason"])
        metrics.append(Metric(**item))
    if type(value["warnings"]) is not list or len(value["warnings"]) > 1000:
        raise ValueError("Invalid warnings")
    for warning in value["warnings"]:
        record_text(warning, 128)
    for key in ("error_code", "error_message"):
        if value[key] is not None:
            record_text(value[key])
    _metadata(value["diagnostics_json"], 4 * 1024**2)
    bundle = value["bundle"]
    if bundle is not None:
        record_keys(bundle, "model_id task model_sha256 schema_sha256 metadata_json")
        if bundle["model_id"] != value["model_id"]:
            raise ValueError("Candidate model mismatch")
        for key in ("model_sha256", "schema_sha256"):
            if re.fullmatch(r"[0-9a-f]{64}", record_text(bundle[key], 64)) is None:
                raise ValueError("Invalid bundle hash")
        _metadata(bundle["metadata_json"], 4 * 1024**2)
        bundle = ModelBundle(
            directory=directory, **dict(bundle, task=TaskKind(bundle["task"]))
        )
    return CandidateResult(
        value["model_id"],
        CandidateStatus(value["status"]),
        value["elapsed"],
        tuple(metrics),
        value["diagnostics_json"],
        tuple(value["warnings"]),
        bundle,
        value["error_code"],
        value["error_message"],
    )
