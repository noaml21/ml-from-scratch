"""Full-table descriptive type inference; no learned model preprocessing."""

import math
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from mlforge.datasets.records import (
    Cell,
    ColumnProfile,
    ColumnType,
    Schema,
    SourceKind,
    TabularDataset,
)

NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
LEADING_ZERO = re.compile(r"[+-]?0[0-9]+\Z")


def interpreted(cell: Cell, kind: ColumnType):
    """A derived scalar view. Invalid interpretations never change the raw cell."""
    if cell.missing:
        return None
    text = cell.raw_text
    if kind in {ColumnType.CATEGORY, ColumnType.IDENTIFIER}:
        return text
    if kind == ColumnType.NUMBER:
        text = text.strip()
        if cell.source_kind == SourceKind.BOOLEAN or not NUMBER.fullmatch(text):
            raise ValueError("NUMBER_REQUIRED")
        # float(text) and float(Decimal(text)) are the same correctly rounded
        # value; only magnitudes from 2**52 can need the exact precision check.
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("NUMBER_RANGE")
        if abs(value) < 2**52:
            return value
        try:
            decimal = Decimal(text)
            value = float(decimal)
            if not math.isfinite(value):
                raise ValueError("NUMBER_RANGE")
            if decimal == decimal.to_integral_value() and abs(decimal) > 2**53 - 1:
                raise ValueError("PRECISION")
        except (InvalidOperation, OverflowError):
            raise ValueError("NUMBER_RANGE") from None
        return value
    if kind == ColumnType.BOOLEAN and text.lower() in {"true", "false"}:
        return text.lower() == "true"
    if kind == ColumnType.DATE and DATE.fullmatch(text):
        return date.fromisoformat(text).isoformat()
    raise ValueError("TYPE_REQUIRED")


def _all(cells: tuple[Cell, ...], kind: ColumnType) -> list | None:
    """Every interpretation, or None as soon as one value does not fit."""
    try:
        return [interpreted(cell, kind) for cell in cells]
    except ValueError:
        return None


def _detect(name: str, present: tuple[Cell, ...]) -> tuple[ColumnType, list | None]:
    if not present:
        return ColumnType.UNKNOWN, None
    raw_unique = len({cell.raw_text for cell in present})
    lowered = name.lower()
    if (
        (lowered in {"id", "uuid", "guid", "identifier"} or lowered.endswith("_id"))
        and len(present) >= 10
        and raw_unique / len(present) >= 0.9
    ):
        return ColumnType.IDENTIFIER, None
    for kind in (ColumnType.BOOLEAN, ColumnType.DATE, ColumnType.NUMBER):
        values = _all(present, kind)
        if values is not None:
            if kind == ColumnType.NUMBER and any(
                cell.source_kind == SourceKind.TEXT
                and LEADING_ZERO.fullmatch(cell.raw_text.strip())
                for cell in present
            ):
                return ColumnType.CATEGORY, None
            return kind, values
    return ColumnType.CATEGORY, None


def detect(name: str, cells: tuple[Cell, ...]) -> ColumnType:
    return _detect(name, tuple(cell for cell in cells if not cell.missing))[0]


def profile(
    column_id: str,
    cells: tuple[Cell, ...],
    detected: ColumnType,
    effective: ColumnType,
    *,
    overridden: bool = False,
    interpretations: list | None = None,
) -> ColumnProfile:
    """Profile cells; interpretations may carry detect's values for `effective`."""
    present = tuple(cell for cell in cells if not cell.missing)
    values = set(
        interpretations
        if interpretations is not None
        else (interpreted(cell, effective) for cell in present)
    )
    warnings = []
    if (
        len({cell.source_kind for cell in present}) > 1
        and detected in {ColumnType.CATEGORY, ColumnType.IDENTIFIER}
        and not overridden
    ):
        warnings.append("MIXED_KINDS")
    # Detection never yields Number when a text value has leading zeros.
    if detected != ColumnType.NUMBER and any(
        cell.source_kind == SourceKind.TEXT
        and LEADING_ZERO.fullmatch(cell.raw_text.strip())
        for cell in present
    ):
        warnings.append("LEADING_ZEROS")
    # Every value of an effective Number column already interpreted exactly.
    for cell in present if effective != ColumnType.NUMBER else ():
        try:
            interpreted(cell, ColumnType.NUMBER)
        except ValueError as error:
            if str(error) == "PRECISION":
                warnings.append("PRECISION")
                break
    if effective == ColumnType.CATEGORY and (
        len(values) > 50 or (len(present) >= 20 and len(values) / len(present) > 0.8)
    ):
        warnings.append("HIGH_CARDINALITY")
    if any(len(cell.raw_text) > 200 for cell in present):
        warnings.append("LONG_TEXT")
    samples = tuple(dict.fromkeys(cell.raw_text for cell in present))[:3]
    return ColumnProfile(
        column_id,
        detected,
        effective,
        len(cells) - len(present),
        len(values),
        samples,
        tuple(warnings),
        overridden,
    )


def infer_schema(dataset: TabularDataset) -> Schema:
    profiles = []
    for index, column in enumerate(dataset.columns):
        cells = tuple(row[index] for row in dataset.rows)
        present = tuple(cell for cell in cells if not cell.missing)
        detected, values = _detect(column.name, present)
        profiles.append(
            profile(column.id, cells, detected, detected, interpretations=values)
        )
    return Schema(tuple(profiles))
