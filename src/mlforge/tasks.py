"""Task eligibility and selection policy over confirmed canonical schema views."""

import math
from collections import Counter
from dataclasses import dataclass

from mlforge.contracts import DomainError, ExperimentSpec, TaskKind
from mlforge.datasets.records import ColumnType, Schema, TabularDataset


@dataclass(frozen=True)
class TaskSpec:
    task: TaskKind
    label: str


TASKS = (
    TaskSpec(TaskKind.CLASSIFICATION, "Predict an outcome"),
    TaskSpec(TaskKind.REGRESSION, "Predict a number"),
    TaskSpec(TaskKind.CLUSTERING, "Find groups"),
    TaskSpec(TaskKind.REDUCTION, "Reduce complexity"),
)


@dataclass(frozen=True)
class Choice:
    column_id: str
    name: str
    eligible: bool
    reason: str
    default: bool = False


@dataclass(frozen=True)
class ReviewWarning:
    code: str
    message: str
    column_id: str | None = None


def column_values(dataset: TabularDataset, schema: Schema, column_id: str) -> tuple:
    """Task-domain values from already validated types; raw cells stay immutable."""
    index = next((i for i, c in enumerate(dataset.columns) if c.id == column_id), None)
    if index is None:
        raise DomainError("COLUMN", "Choose an existing column.", "Return to Preview.")
    kind = schema.profile(column_id).effective
    values = []
    for row in dataset.rows:
        cell = row[index]
        if cell.missing:
            values.append(None)
        elif kind == ColumnType.NUMBER:
            values.append(float(cell.raw_text))
        elif kind == ColumnType.BOOLEAN:
            values.append(cell.raw_text.lower() == "true")
        else:
            values.append(cell.raw_text)
    return tuple(values)


def target_values(
    dataset: TabularDataset, schema: Schema, target_id: str, task: TaskKind
) -> tuple:
    values = column_values(dataset, schema, target_id)
    if task == TaskKind.REGRESSION:
        return values
    kind = schema.profile(target_id).effective
    if kind == ColumnType.NUMBER and any(
        value is not None and (not math.isfinite(value) or not value.is_integer())
        for value in values
    ):
        raise DomainError(
            "TARGET",
            "Classification numbers must be integral.",
            "Choose Category explicitly in Preview.",
        )
    return tuple(
        None
        if value is None
        else ("true" if value else "false")
        if kind == ColumnType.BOOLEAN
        else str(int(value))
        if kind == ColumnType.NUMBER
        else value
        for value in values
    )


def target_reason(
    dataset: TabularDataset, schema: Schema, column_id: str, task: TaskKind
) -> str | None:
    try:
        p = schema.profile(column_id)
    except StopIteration:
        raise DomainError(
            "COLUMN", "Choose an existing column.", "Return to Target."
        ) from None
    if not task.supervised:
        return "This goal has no target."
    if p.effective in {ColumnType.UNKNOWN, ColumnType.IDENTIFIER, ColumnType.DATE}:
        return "Change the interpretation in Preview before using this as a target."
    if task == TaskKind.REGRESSION and p.effective != ColumnType.NUMBER:
        return "A numeric target is required."
    if p.missing_count:
        return "Targets cannot contain missing values. Choose another target."
    if len(dataset.rows) < 20:
        return "At least 20 rows are required."
    if p.distinct_count < 2:
        return "The target must contain at least two distinct values."
    values = column_values(dataset, schema, column_id)
    if p.effective == ColumnType.NUMBER:
        if not all(math.isfinite(value) for value in values):
            return "Target values must be finite."
        if task == TaskKind.CLASSIFICATION and not all(
            value.is_integer() for value in values
        ):
            return "Nonintegral outcomes need an explicit Category override in Preview."
    if task == TaskKind.CLASSIFICATION:
        counts = Counter(target_values(dataset, schema, column_id, task))
        if not 2 <= len(counts) <= 20:
            return "Classification requires 2–20 classes."
        if min(counts.values()) < 5:
            return "Every class needs at least 5 rows."
    return None


def target_choices(
    dataset: TabularDataset, schema: Schema, task: TaskKind, *, show_all: bool = False
) -> tuple[Choice, ...]:
    choices = []
    for column in dataset.columns:
        p = schema.profile(column.id)
        reason = target_reason(dataset, schema, column.id, task)
        if show_all or (reason is None and "LONG_TEXT" not in p.warnings):
            choices.append(
                Choice(
                    column.id, column.name, reason is None, reason or "Eligible target"
                )
            )
    if task == TaskKind.CLASSIFICATION:
        choices.sort(
            key=lambda c: schema.profile(c.column_id).effective == ColumnType.NUMBER
        )
    return tuple(choices)


def feature_choices(
    dataset: TabularDataset,
    schema: Schema,
    task: TaskKind,
    target_id: str | None = None,
) -> tuple[Choice, ...]:
    choices = []
    for column in dataset.columns:
        p = schema.profile(column.id)
        reason, eligible, default = "Ready to use", True, True
        if column.id == target_id:
            reason, eligible = "The target cannot be an input feature.", False
        elif p.distinct_count < 2:
            reason, eligible = (
                "All-missing or constant columns cannot be features.",
                False,
            )
        elif p.effective in {
            ColumnType.UNKNOWN,
            ColumnType.IDENTIFIER,
            ColumnType.DATE,
        }:
            reason, eligible = (
                "Change the interpretation in Preview to use this column.",
                False,
            )
        elif not task.supervised and p.effective != ColumnType.NUMBER:
            reason, eligible = "This goal uses numeric features only.", False
        elif set(p.warnings) & {"HIGH_CARDINALITY", "LONG_TEXT"}:
            reason, default = (
                "High-cardinality or long text: review before selecting.",
                False,
            )
        choices.append(
            Choice(column.id, column.name, eligible, reason, eligible and default)
        )
    return tuple(choices)


def goal_reason(dataset: TabularDataset, schema: Schema, task: TaskKind) -> str | None:
    if task.supervised:
        targets = target_choices(dataset, schema, task, show_all=True)
        if not any(
            c.eligible
            and any(
                f.eligible for f in feature_choices(dataset, schema, task, c.column_id)
            )
            for c in targets
        ):
            return "Choose a complete, varying target and at least one usable feature."
    else:
        minimum_rows, minimum_features = (
            (10, 1) if task == TaskKind.CLUSTERING else (3, 2)
        )
        if len(dataset.rows) < minimum_rows:
            return f"At least {minimum_rows} rows are required."
        if (
            sum(c.eligible for c in feature_choices(dataset, schema, task))
            < minimum_features
        ):
            return f"At least {minimum_features} varying numeric features are required."
    return None


LEAKAGE_NAMES = frozenset(
    {
        "target_copy",
        "prediction",
        "predicted",
        "outcome",
        "result",
        "label",
        "post_outcome",
    }
)


def option_bounds(
    task: TaskKind, rows: int, features: int
) -> tuple[int, int, int] | None:
    """Return minimum, maximum and default; supervised tasks have no option."""
    if task.supervised:
        return None
    if task == TaskKind.CLUSTERING:
        return 2, min(10, rows - 1), 3
    maximum = min(10, rows - 1, features - 1)
    return 1, maximum, min(2, maximum)


def review_warnings(
    dataset: TabularDataset, schema: Schema, spec: ExperimentSpec
) -> tuple[ReviewWarning, ...]:
    warnings = []
    target = column_values(dataset, schema, spec.target_id) if spec.target_id else None
    if spec.target_id and "MIXED_KINDS" in schema.profile(spec.target_id).warnings:
        warnings.append(
            ReviewWarning(
                f"MIXED_KINDS:{spec.target_id}",
                "Review mixed scalar kinds in the target before training.",
                spec.target_id,
            )
        )
    selected = []
    columns = {column.id: column for column in dataset.columns}
    for column_id in spec.feature_ids:
        values = column_values(dataset, schema, column_id)
        selected.append(values)
        p = schema.profile(column_id)
        for code in p.warnings:
            if code in {"HIGH_CARDINALITY", "LONG_TEXT", "MIXED_KINDS"}:
                warnings.append(
                    ReviewWarning(
                        f"{code}:{column_id}",
                        "Review this column's interpretation and suitability.",
                        column_id,
                    )
                )
        if target is not None and values == target:
            warnings.append(
                ReviewWarning(
                    f"EQUAL_TARGET:{column_id}",
                    "This input exactly matches the target; it may leak the answer.",
                    column_id,
                )
            )
        if spec.task.supervised and columns[column_id].name.lower() in LEAKAGE_NAMES:
            warnings.append(
                ReviewWarning(
                    f"LEAKAGE_NAME:{column_id}",
                    "This name suggests information that may be unavailable "
                    "at prediction time.",
                    column_id,
                )
            )
    rows = list(zip(*selected, strict=True))
    if len(set(rows)) < len(rows):
        warnings.append(
            ReviewWarning(
                "DUPLICATE_ROWS",
                "Selected inputs contain duplicate rows; repeated entities "
                "can make evaluation optimistic.",
            )
        )
    return tuple(warnings)


def validate_selection(
    dataset: TabularDataset, schema: Schema, spec: ExperimentSpec
) -> tuple[ReviewWarning, ...]:
    if spec.task.supervised:
        reason = target_reason(dataset, schema, spec.target_id, spec.task)
        if reason:
            raise DomainError(
                "TARGET", reason, "Return to Target or Preview.", column=spec.target_id
            )
    elif reason := goal_reason(dataset, schema, spec.task):
        raise DomainError("GOAL", reason, "Choose another goal or review column types.")
    choices = {
        c.column_id: c
        for c in feature_choices(dataset, schema, spec.task, spec.target_id)
    }
    for column_id in spec.feature_ids:
        if column_id not in choices or not choices[column_id].eligible:
            raise DomainError(
                "FEATURE",
                "Choose usable inputs without the target.",
                "Return to Features or Preview.",
                column=column_id,
            )
    if spec.task == TaskKind.REDUCTION and len(spec.feature_ids) < 2:
        raise DomainError(
            "FEATURE",
            "PCA requires at least two numeric features.",
            "Select more numeric features.",
        )
    if not spec.task.supervised:
        minimum, maximum, _ = option_bounds(
            spec.task, len(dataset.rows), len(spec.feature_ids)
        )
        if type(spec.option) is not int or not minimum <= spec.option <= maximum:
            raise DomainError(
                "OPTION",
                f"Choose an integer from {minimum} to {maximum}.",
                "Correct the task option.",
            )
    elif spec.option is not None:
        raise DomainError(
            "OPTION", "This goal has no numeric task option.", "Return to Models."
        )
    warnings = review_warnings(dataset, schema, spec)
    missing = [
        warning for warning in warnings if warning.code not in spec.acknowledgements
    ]
    if missing:
        raise DomainError(
            "ACKNOWLEDGEMENT",
            "Review selected-feature warnings before training.",
            "Keep selected features and continue, or edit Features.",
        )
    return warnings
