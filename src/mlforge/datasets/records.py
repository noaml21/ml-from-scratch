"""Immutable raw cells and separate effective schema; no file or ML services."""

import unicodedata
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


def record_keys(value, names):
    """Exact fields for private record codecs; no permissive object construction."""
    if type(value) is not dict or set(value) != set(names.split()):
        raise ValueError("Invalid record fields")


def record_count(value, maximum=2**53 - 1):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("Invalid record count")
    return value


def record_text(value, maximum=4096):
    if type(value) is not str or len(value) > maximum:
        raise ValueError("Invalid record text")
    value.encode("utf-8", errors="strict")
    return value


def dataset_data(dataset):
    return {
        "columns": [[c.id, c.name] for c in dataset.columns],
        "rows": [
            [[c.raw_text, c.source_kind.value] for c in row] for row in dataset.rows
        ],
        "source_format": dataset.source_format,
        "fingerprint": dataset.fingerprint,
        "ignored_blank_records": dataset.ignored_blank_records,
    }


def dataset_from_data(value):
    import hashlib
    import json
    import math
    import re

    record_keys(value, "columns rows source_format fingerprint ignored_blank_records")
    columns, rows = value["columns"], value["rows"]
    if type(columns) is not list or not 1 <= len(columns) <= 100:
        raise ValueError("Invalid columns")
    if type(rows) is not list or not 1 <= len(rows) <= 20000:
        raise ValueError("Invalid rows")
    checked_columns = []
    for i, column in enumerate(columns):
        if type(column) is not list or len(column) != 2 or column[0] != f"c{i}":
            raise ValueError("Invalid column")
        name = record_text(column[1], 128)
        if not name.strip() or any(
            unicodedata.category(c).startswith("C") for c in name
        ):
            raise ValueError("Invalid column name")
        checked_columns.append(Column(column[0], name))
    if len({c.name for c in checked_columns}) != len(columns):
        raise ValueError("Duplicate column")
    checked_rows = []
    for row in rows:
        if type(row) is not list or len(row) != len(columns):
            raise ValueError("Invalid row shape")
        cells = []
        for cell in row:
            if type(cell) is not list or len(cell) != 2:
                raise ValueError("Invalid cell")
            raw, kind = cell
            kind = SourceKind(kind)
            if raw is None:
                if kind != SourceKind.NULL:
                    raise ValueError("Invalid missing cell")
            else:
                record_text(raw)
                if kind == SourceKind.NULL:
                    raise ValueError("Invalid null cell")
                if kind == SourceKind.BOOLEAN and raw not in ("true", "false"):
                    raise ValueError("Invalid boolean cell")
                if kind == SourceKind.NUMBER and (
                    re.fullmatch(
                        r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", raw
                    )
                    is None
                    or not math.isfinite(float(raw))
                ):
                    raise ValueError("Invalid number cell")
            cells.append(Cell(raw, kind))
        checked_rows.append(tuple(cells))
    if value["source_format"] not in ("CSV", "TSV", "JSONL"):
        raise ValueError("Invalid source format")
    canonical = {
        "parser_version": 1,
        "format": value["source_format"],
        "headers": [c.name for c in checked_columns],
        "rows": rows,
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()
    if value["fingerprint"] != fingerprint:
        raise ValueError("Dataset fingerprint mismatch")
    return TabularDataset(
        tuple(checked_columns),
        tuple(checked_rows),
        value["source_format"],
        fingerprint,
        record_count(value["ignored_blank_records"]),
    )


def schema_data(schema):
    return {
        "revision": schema.revision,
        "columns": [
            {
                "column_id": p.column_id,
                "detected": p.detected.value,
                "effective": p.effective.value,
                "missing_count": p.missing_count,
                "distinct_count": p.distinct_count,
                "samples": list(p.samples),
                "warnings": list(p.warnings),
                "overridden": p.overridden,
            }
            for p in schema.columns
        ],
    }


def schema_from_data(value):
    record_keys(value, "revision columns")
    if type(value["columns"]) is not list or not 1 <= len(value["columns"]) <= 100:
        raise ValueError("Invalid schema columns")
    profiles = []
    for i, p in enumerate(value["columns"]):
        record_keys(
            p,
            "column_id detected effective missing_count distinct_count samples "
            "warnings overridden",
        )
        if p["column_id"] != f"c{i}" or type(p["overridden"]) is not bool:
            raise ValueError("Invalid schema identity")
        for key, maximum in (("samples", 3), ("warnings", 16)):
            if type(p[key]) is not list or len(p[key]) > maximum:
                raise ValueError("Invalid schema values")
            for text in p[key]:
                record_text(text)
        profiles.append(
            ColumnProfile(
                p["column_id"],
                ColumnType(p["detected"]),
                ColumnType(p["effective"]),
                record_count(p["missing_count"], 20000),
                record_count(p["distinct_count"], 20000),
                p["samples"],
                p["warnings"],
                p["overridden"],
            )
        )
    return Schema(tuple(profiles), record_count(value["revision"]))


def raw_records(
    dataset: TabularDataset, feature_ids: tuple[str, ...], rows: tuple[int, ...]
) -> list[dict]:
    indices = {column.id: index for index, column in enumerate(dataset.columns)}
    chosen = [indices[column_id] for column_id in feature_ids]
    return [
        {
            dataset.columns[index].name: None
            if dataset.rows[row][index].missing
            else dataset.rows[row][index].raw_text
            for index in chosen
        }
        for row in rows
    ]


def visible_text(text: str) -> str:
    """Escape controls without markup interpretation or changing canonical cells."""
    return "".join(
        (f"\\u{ord(char):04x}" if ord(char) <= 0xFFFF else f"\\U{ord(char):08x}")
        if unicodedata.category(char).startswith("C") or char in "\u2028\u2029"
        else char
        for char in text
    )
