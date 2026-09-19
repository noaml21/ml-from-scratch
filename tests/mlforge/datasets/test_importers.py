"""Canonical preservation and adversarial boundaries on actual local files."""

import io
import os
from dataclasses import FrozenInstanceError

import pytest

from mlforge.contracts import DomainError
from mlforge.datasets import importers
from mlforge.datasets.importers import load_dataset
from mlforge.datasets.records import SourceKind


def write(tmp_path, content, extension="csv"):
    path = tmp_path / f"private data ש.{extension}"
    path.write_bytes(content.encode() if isinstance(content, str) else content)
    return path


@pytest.mark.parametrize("extension,delimiter", [("CSV", ","), ("tSv", "\t")])
def test_delimited_lexical_and_multiline(tmp_path, extension, delimiter):
    text = (
        f'\ufeff name {delimiter}value\r\n"a\n""b"{delimiter}0012\r\n'
        f" {delimiter}NA\r\n{delimiter}\r\n\r\n"
    )
    path = write(tmp_path, text, extension)
    original = path.read_bytes()
    data = load_dataset(path)
    assert [c.name for c in data.columns] == [" name ", "value"]
    assert [c.id for c in data.columns] == ["c0", "c1"]
    assert [[c.raw_text for c in row] for row in data.rows] == [
        ['a\n"b', "0012"],
        [" ", "NA"],
        ["", ""],
    ]
    assert data.ignored_blank_records == 1
    assert data.rows[-1][0].missing and not data.rows[1][0].missing
    assert path.read_bytes() == original
    assert load_dataset(path).fingerprint == data.fingerprint
    with pytest.raises(FrozenInstanceError):
        data.rows = ()


def test_json_lexical_order_kinds_and_blanks(tmp_path):
    path = write(
        tmp_path,
        '\ufeff{"x":1.00e+2,"b":true,"t":"0012","m":null}\n \n'
        '{"m":"","t":" ","b":false,"x":9007199254740993}\n',
        "JSONL",
    )
    data = load_dataset(path)
    assert [c.name for c in data.columns] == ["x", "b", "t", "m"]
    assert [c.raw_text for c in data.rows[0]] == ["1.00e+2", "true", "0012", None]
    assert [c.source_kind for c in data.rows[0]] == [
        SourceKind.NUMBER,
        SourceKind.BOOLEAN,
        SourceKind.TEXT,
        SourceKind.NULL,
    ]
    assert data.rows[1][0].raw_text == "9007199254740993"
    assert data.rows[1][3].missing
    assert data.ignored_blank_records == 1


@pytest.mark.parametrize(
    "content,code",
    [
        ("", "NO_DATA"),
        ("a,b\n", "NO_DATA"),
        ("a,a\n1,2", "HEADERS"),
        ("a, \n1,2", "HEADERS"),
        ("a,\x1b\n1,2", "HEADERS"),
        ("a,b\n1", "ROW_WIDTH"),
        ("a\n1,2", "ROW_WIDTH"),
        ('a\n"secret', "CSV_QUOTES"),
        ('a\nsec"ret', "CSV_QUOTES"),
        ('a\n"secret"oops', "CSV_QUOTES"),
        ('a\n"secret" ', "CSV_QUOTES"),
        ("a" * 129 + "\n1", "DATA_LIMIT"),
        ("a\n" + "x" * 4097, "DATA_LIMIT"),
        (",".join(f"c{i}" for i in range(101)) + "\n1", "DATA_LIMIT"),
    ],
)
def test_csv_errors_are_safe(tmp_path, content, code):
    with pytest.raises(DomainError) as caught:
        load_dataset(write(tmp_path, content))
    assert caught.value.code == code
    assert "secret" not in str(caught.value)
    assert "private" not in str(caught.value)
    assert caught.value.action


@pytest.mark.parametrize(
    "content,code",
    [
        ('{"x":1,"x":2}', "JSON_STRUCTURE"),
        ("[]", "JSON_STRUCTURE"),
        ("1", "JSON_STRUCTURE"),
        ("null", "JSON_STRUCTURE"),
        ('{"x":[]}', "JSON_STRUCTURE"),
        ('{"x":{"a":1}}', "JSON_STRUCTURE"),
        ('{"x":NaN}', "JSON_STRUCTURE"),
        ('{"x":Infinity}', "JSON_STRUCTURE"),
        ('{"x":1e400}', "JSON_STRUCTURE"),
        ('{"x":1}\n{"y":2}', "JSON_KEYS"),
        ('{"x":1}\n{}', "JSON_KEYS"),
        ("{}", "HEADERS"),
        ('{" ":1}', "HEADERS"),
        ('{"x\\u0000":1}', "HEADERS"),
        ('{"x":"' + "a" * 4097 + '"}', "DATA_LIMIT"),
        ('{"x":"secret"', "JSON_STRUCTURE"),
    ],
)
def test_json_errors_are_safe(tmp_path, content, code):
    with pytest.raises(DomainError) as caught:
        load_dataset(write(tmp_path, content, "jsonl"))
    assert caught.value.code == code
    assert "secret" not in str(caught.value)
    assert caught.value.row is not None


def test_control_values_preserved_and_fingerprint_changes(tmp_path):
    path = write(tmp_path, 'x\n"\x1b[31m[bold]secret[/bold]"\n')
    data = load_dataset(path)
    assert data.rows[0][0].raw_text == "\x1b[31m[bold]secret[/bold]"
    path.write_text("x\nchanged\n")
    assert load_dataset(path).fingerprint != data.fingerprint


def test_exact_cell_and_row_boundaries(tmp_path, monkeypatch):
    monkeypatch.setattr(importers, "MAX_ROWS", 2)
    path = write(tmp_path, "x\n" + "a" * 4096 + "\nb\n")
    assert len(load_dataset(path).rows) == 2
    with path.open("a") as stream:
        stream.write("c\n")
    with pytest.raises(DomainError, match="data row"):
        load_dataset(path)


def test_byte_limits_stat_and_growing_stream(tmp_path, monkeypatch):
    monkeypatch.setattr(importers, "MAX_BYTES", 8)
    assert list(importers._lines(io.BytesIO(b"x\n12345\n"))) == ["x\n", "12345\n"]
    with pytest.raises(DomainError, match="file byte"):
        list(importers._lines(io.BytesIO(b"x\n123456\n")))
    with pytest.raises(DomainError, match="file byte"):
        load_dataset(write(tmp_path, "x\n123456\n"))


def test_encoding_and_extension(tmp_path):
    with pytest.raises(DomainError) as caught:
        load_dataset(write(tmp_path, b"x\n\xff"))
    assert caught.value.code == "ENCODING"
    with pytest.raises(DomainError) as caught:
        load_dataset(write(tmp_path, "x\n1", "xlsx"))
    assert caught.value.code == "FORMAT"


def test_local_regular_files_and_symlinks(tmp_path):
    path = write(tmp_path, "x\n1")
    link = tmp_path / "linked.csv"
    link.symlink_to(path)
    assert load_dataset(link) == load_dataset(path)
    fifo = tmp_path / "pipe.csv"
    os.mkfifo(fifo)
    directory = tmp_path / "folder.csv"
    directory.mkdir()
    device = tmp_path / "device.csv"
    device.symlink_to("/dev/null")
    for invalid in (fifo, directory, device, "https://example.test/private.csv"):
        with pytest.raises(DomainError) as caught:
            load_dataset(invalid)
        assert caught.value.code == "LOCAL_FILE"
    with pytest.raises(DomainError) as caught:
        load_dataset(tmp_path / "absent.csv")
    assert caught.value.code == "FILE_READ"


def test_open_identity_race_and_permission(tmp_path, monkeypatch):
    path = write(tmp_path, "x\n1")
    other = tmp_path / "replacement.csv"
    other.write_text("x\n2")
    original_open = os.open
    monkeypatch.setattr(
        importers.os, "open", lambda name, flags: original_open(other, flags)
    )
    with pytest.raises(DomainError) as caught:
        load_dataset(path)
    assert caught.value.code == "FILE_CHANGED"

    def refused(*args):
        raise PermissionError("private path")

    monkeypatch.setattr(importers.os, "open", refused)
    with pytest.raises(DomainError) as caught:
        load_dataset(path)
    assert caught.value.code == "FILE_READ"
    assert "private" not in str(caught.value)


def test_growth_after_stat_cannot_bypass_byte_limit(tmp_path, monkeypatch):
    path = write(tmp_path, "x\n1\n")
    monkeypatch.setattr(importers, "MAX_BYTES", 8)
    original_open = os.open

    def growing_open(name, flags):
        with path.open("ab") as stream:
            stream.write(b"2\n3\n4\n")
        return original_open(name, flags)

    monkeypatch.setattr(importers.os, "open", growing_open)
    with pytest.raises(DomainError, match="file byte"):
        load_dataset(path)


def test_real_row_limit_and_multiline_error_location(tmp_path):
    path = write(tmp_path, "x\n" + "1\n" * 20_000)
    assert len(load_dataset(path).rows) == 20_000
    with path.open("a") as stream:
        stream.write("1\n")
    with pytest.raises(DomainError, match="data row") as caught:
        load_dataset(path)
    assert caught.value.row == 20_002
    path.write_text('a,b\n"one\ntwo",1\nwrong\n')
    with pytest.raises(DomainError) as caught:
        load_dataset(path)
    assert caught.value.code == "ROW_WIDTH"
    assert caught.value.row == 4
