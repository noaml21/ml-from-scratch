"""Atomic schema changes, preview views and session-only effective provenance."""

import hashlib
import json

from mlforge.contracts import DomainError
from mlforge.datasets.inference import interpreted, profile
from mlforge.datasets.records import ColumnType, Schema, TabularDataset
from mlforge.datasets.records import preview as preview
from mlforge.datasets.records import visible_text as visible_text


def change_type(
    dataset: TabularDataset, schema: Schema, column_id: str, kind: ColumnType | None
) -> Schema:
    """None resets detection. Validate every present value before replacing state."""
    try:
        index = next(
            i for i, column in enumerate(dataset.columns) if column.id == column_id
        )
        previous = schema.profile(column_id)
    except StopIteration:
        raise DomainError(
            "COLUMN", "Choose an existing column.", "Return to Preview."
        ) from None
    if kind == ColumnType.UNKNOWN or (
        kind is not None and not isinstance(kind, ColumnType)
    ):
        raise DomainError(
            "TYPE",
            "Unknown is diagnostic, not an override.",
            "Choose a supported type.",
        )
    effective = previous.detected if kind is None else kind
    cells = tuple(row[index] for row in dataset.rows)
    if kind is not None and all(cell.missing for cell in cells):
        raise DomainError(
            "TYPE_EMPTY",
            "This column has no present values.",
            "Choose another column or dataset.",
            column=column_id,
        )
    failures = []
    for row, cell in enumerate(cells):
        try:
            interpreted(cell, effective)
        except ValueError:
            failures.append(row)
    if failures:
        locations = ", ".join(str(row + 1) for row in failures[:5])
        raise DomainError(
            "TYPE_VALUES",
            f"{len(failures)} values cannot use this type. Data rows: {locations}.",
            "Keep the current type or choose Category.",
            row=failures[0],
            column=column_id,
        )
    changed = profile(
        column_id, cells, previous.detected, effective, overridden=kind is not None
    )
    return Schema(
        tuple(changed if p.column_id == column_id else p for p in schema.columns),
        schema.revision + 1,
    )


def effective_fingerprint(dataset: TabularDataset, schema: Schema) -> str:
    payload = [
        dataset.fingerprint,
        [(p.column_id, p.effective.value, p.overridden) for p in schema.columns],
    ]
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":")).encode()
    ).hexdigest()
