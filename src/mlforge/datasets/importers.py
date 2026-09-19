"""Bounded local table import; preserve lexical cells without interpreting types."""

import csv
import hashlib
import json
import math
import os
import stat
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from mlforge.contracts import DomainError, TaskKind
from mlforge.datasets.records import Cell, Column, SourceKind, TabularDataset

MAX_BYTES = 20 * 1024 * 1024
MAX_ROWS = 20_000
MAX_COLUMNS = 100
MAX_HEADER = 128
MAX_CELL = 4096
RECOVERY = "Prepare with AI, choose another dataset, or go Back."


@dataclass(frozen=True)
class Format:
    extension: str
    label: str
    delimiter: str | None


FORMATS = (
    Format(".csv", "CSV", ","),
    Format(".tsv", "TSV", "\t"),
    Format(".jsonl", "JSONL", None),
)
BY_EXTENSION = {item.extension: item for item in FORMATS}


@dataclass(frozen=True)
class Example:
    filename: str
    label: str
    task: TaskKind


EXAMPLES = (
    Example("classification.csv", "Two synthetic outcomes", TaskKind.CLASSIFICATION),
    Example("regression.tsv", "Synthetic measurements", TaskKind.REGRESSION),
    Example("clustering.csv", "Three synthetic groups", TaskKind.CLUSTERING),
    Example("reduction.jsonl", "Related synthetic measurements", TaskKind.REDUCTION),
    Example("mixed.csv", "Mixed types and missing values", TaskKind.CLASSIFICATION),
)


def _error(code: str, message: str, line: int | None = None) -> DomainError:
    return DomainError(code, message, RECOVERY, row=line)


def _limit(label: str, limit: int, line: int | None = None) -> DomainError:
    return _error(
        "DATA_LIMIT", f"The {label} limit is {limit:,}. Use a smaller table.", line
    )


def _lines(stream: BinaryIO) -> Iterator[str]:
    total = 0
    line = 0
    while data := stream.readline(MAX_BYTES - total + 1):
        total += len(data)
        line += 1
        if total > MAX_BYTES:
            raise _limit("file byte", MAX_BYTES, line)
        try:
            yield data.decode("utf-8-sig" if line == 1 else "utf-8")
        except UnicodeDecodeError:
            raise _error(
                "ENCODING", "Use UTF-8 text with an optional initial BOM.", line
            ) from None


def _csv_lines(lines: Iterator[str], delimiter: str) -> Iterator[str]:
    # csv.reader(strict=True) still accepts quotes inside unquoted fields.
    # Validate that grammar explicitly and bound fields before reader allocation.
    state, length, columns = "start", 0, 1
    for number, line in enumerate(lines, 1):
        for char in line:
            if state == "quoted":
                if char == '"':
                    state = "closed"
                else:
                    length += 1
            elif state == "closed" and char == '"':
                state = "quoted"
                length += 1
            elif char == delimiter:
                columns += 1
                if columns > MAX_COLUMNS:
                    raise _limit("column", MAX_COLUMNS, number)
                state, length = "start", 0
            elif char in "\r\n":
                state, length, columns = "start", 0, 1
            elif state == "start" and char == '"':
                state = "quoted"
            elif state == "closed" or char == '"':
                raise _error(
                    "CSV_QUOTES", "Malformed quoting in a delimited record.", number
                )
            else:
                state = "plain"
                length += 1
            if length > MAX_CELL:
                raise _limit("cell character", MAX_CELL, number)
        yield line


def _headers(names: list[str], line: int) -> tuple[Column, ...]:
    if len(names) > MAX_COLUMNS:
        raise _limit("column", MAX_COLUMNS, line)
    if not names or any(not name.strip() for name in names):
        raise _error("HEADERS", "Every column needs a nonempty header.", line)
    if len(names) != len(set(names)):
        raise _error("HEADERS", "Column headers must be unique.", line)
    for name in names:
        if len(name) > MAX_HEADER:
            raise _limit("header character", MAX_HEADER, line)
        if any(unicodedata.category(char).startswith("C") for char in name):
            raise _error("HEADERS", "Headers cannot contain control characters.", line)
    return tuple(Column(f"c{index}", name) for index, name in enumerate(names))


def _append(rows: list, cells: tuple[Cell, ...], line: int) -> None:
    if len(rows) >= MAX_ROWS:
        raise _limit("data row", MAX_ROWS, line)
    for cell in cells:
        if cell.raw_text is not None and len(cell.raw_text) > MAX_CELL:
            raise _limit("cell character", MAX_CELL, line)
    rows.append(cells)


def _delimited(lines: Iterator[str], descriptor: Format):
    reader = csv.reader(
        _csv_lines(lines, descriptor.delimiter),
        delimiter=descriptor.delimiter,
        strict=True,
    )
    columns, rows, blanks = (), [], 0
    try:
        for record in reader:
            if not record:
                blanks += 1
                continue
            if not columns:
                columns = _headers(record, reader.line_num)
                continue
            if len(record) != len(columns):
                raise _error(
                    "ROW_WIDTH",
                    "Every record must match the header width.",
                    reader.line_num,
                )
            _append(rows, tuple(Cell(value) for value in record), reader.line_num)
    except csv.Error:
        raise _error(
            "CSV_QUOTES", "Malformed quoting in a delimited record.", reader.line_num
        ) from None
    return columns, rows, blanks


def _number(token: str) -> Cell:
    if not math.isfinite(float(token)):
        raise ValueError("Nonfinite number")
    return Cell(token, SourceKind.NUMBER)


def _object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate key")
        result[key] = value
    return result


def _constant(token: str):
    raise ValueError("Nonstandard JSON constant")


def _jsonl(lines: Iterator[str], descriptor: Format):
    columns, rows, blanks = (), [], 0
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            blanks += 1
            continue
        try:
            record = json.loads(
                line,
                object_pairs_hook=_object,
                parse_int=_number,
                parse_float=_number,
                parse_constant=_constant,
            )
            if not isinstance(record, dict):
                raise ValueError("Expected object")
            if not columns:
                columns = _headers(list(record), line_number)
            if set(record) != {column.name for column in columns}:
                raise _error(
                    "JSON_KEYS",
                    "Every object must have the same column keys.",
                    line_number,
                )
            cells = []
            for column in columns:
                value = record[column.name]
                if isinstance(value, Cell):
                    cells.append(value)
                elif value is None:
                    cells.append(Cell(None, SourceKind.NULL))
                elif isinstance(value, bool):
                    cells.append(Cell("true" if value else "false", SourceKind.BOOLEAN))
                elif isinstance(value, str):
                    cells.append(Cell(value))
                else:
                    raise ValueError("Nested value")
            _append(rows, tuple(cells), line_number)
        except DomainError:
            raise
        except (ValueError, RecursionError, OverflowError):
            raise _error(
                "JSON_STRUCTURE",
                "Use flat JSON objects with unique keys and finite scalar values.",
                line_number,
            ) from None
    return columns, rows, blanks


PARSERS = {".csv": _delimited, ".tsv": _delimited, ".jsonl": _jsonl}


def load_dataset(path: str | Path) -> TabularDataset:
    """Read a local file once; no logging, source writes, or retained source path."""
    if "://" in str(path):
        raise _error("LOCAL_FILE", "Choose a local regular file.")
    candidate = Path(path).expanduser()
    descriptor = BY_EXTENSION.get(candidate.suffix.lower())
    if descriptor is None:
        raise _error("FORMAT", "Supported formats are CSV, TSV and flat JSONL.")
    try:
        resolved = candidate.resolve(strict=True)
        before = resolved.stat()
        if not stat.S_ISREG(before.st_mode):
            raise _error("LOCAL_FILE", "Choose a local regular file.")
        if before.st_size > MAX_BYTES:
            raise _limit("file byte", MAX_BYTES)
        fd = os.open(resolved, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (before.st_dev, before.st_ino) != (
                opened.st_dev,
                opened.st_ino,
            ):
                raise _error(
                    "FILE_CHANGED", "The file changed while opening. Retry the import."
                )
            columns, rows, blanks = PARSERS[descriptor.extension](
                _lines(stream), descriptor
            )
            after = os.fstat(stream.fileno())
            if (opened.st_size, opened.st_mtime_ns) != (
                after.st_size,
                after.st_mtime_ns,
            ):
                raise _error(
                    "FILE_CHANGED", "The file changed while reading. Retry the import."
                )
    except DomainError:
        raise
    except (OSError, RuntimeError, ValueError):
        raise _error(
            "FILE_READ",
            "Could not read this local file. Check its location and permissions.",
        ) from None
    if not rows:
        raise _error("NO_DATA", "The table has no data records.")
    canonical = {
        "parser_version": 1,
        "format": descriptor.label,
        "headers": [column.name for column in columns],
        "rows": [
            [(cell.raw_text, cell.source_kind.value) for cell in row] for row in rows
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()
    return TabularDataset(columns, tuple(rows), descriptor.label, fingerprint, blanks)
