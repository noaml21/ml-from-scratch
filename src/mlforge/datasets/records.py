"""Immutable raw cells and separate effective schema; no file or ML services."""

from dataclasses import dataclass
from enum import StrEnum


class SourceKind(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    NULL = "null"


class ColumnType(StrEnum):
    NUMBER = "Number"
    CATEGORY = "Category"
    BOOLEAN = "Boolean"
    DATE = "Date"
    IDENTIFIER = "Identifier"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class Cell:
    raw_text: str | None
    source_kind: SourceKind = SourceKind.TEXT

    @property
    def missing(self) -> bool:
        return self.raw_text is None or self.raw_text == ""


@dataclass(frozen=True)
class Column:
    id: str
    name: str


@dataclass(frozen=True)
class TabularDataset:
    columns: tuple[Column, ...]
    rows: tuple[tuple[Cell, ...], ...]
    source_format: str
    fingerprint: str
    ignored_blank_records: int = 0

    def __post_init__(self) -> None:
        # Freeze caller-owned sequences as well as the dataclass attributes.
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(self, "rows", tuple(tuple(row) for row in self.rows))
        if not self.columns or not self.rows:
            raise ValueError("A dataset must contain columns and data rows")
        if len({column.id for column in self.columns}) != len(self.columns):
            raise ValueError("Column IDs must be unique")
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("Every row must match the column count")


@dataclass(frozen=True)
class ColumnProfile:
    column_id: str
    detected: ColumnType
    effective: ColumnType
    missing_count: int
    distinct_count: int
    samples: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    overridden: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "samples", tuple(self.samples))
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True)
class Schema:
    columns: tuple[ColumnProfile, ...]
    revision: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "columns", tuple(self.columns))

    def profile(self, column_id: str) -> ColumnProfile:
        return next(column for column in self.columns if column.column_id == column_id)
