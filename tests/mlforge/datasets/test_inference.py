"""Full-table interpretation, safe atomic correction and immutable raw cells."""

import json
import math

import pytest

from mlforge.contracts import DomainError
from mlforge.datasets.importers import load_dataset
from mlforge.datasets.inference import infer_schema, interpreted
from mlforge.datasets.records import Cell, Column, TabularDataset
from mlforge.datasets.records import ColumnType as T
from mlforge.datasets.validation import (
    change_type,
    effective_fingerprint,
    preview,
    visible_text,
)


def table(values, name="measurement"):
    return TabularDataset(
        (Column("c0", name),), tuple((Cell(v),) for v in values), "CSV", "test"
    )


@pytest.mark.parametrize(
    "values,name,expected",
    [
        (["", None], "id", T.UNKNOWN),
        (["true", "FALSE"], "x", T.BOOLEAN),
        (["0", "1"], "x", T.NUMBER),
        (["yes", "no"], "x", T.CATEGORY),
        (["2024-02-29", "2023-01-01"], "x", T.DATE),
        (["2023-02-29", "2023-01-01"], "x", T.CATEGORY),
        (["2023-1-01"], "x", T.CATEGORY),
        ([" 1 ", ".2", "3e2"], "x", T.NUMBER),
        (["001", "002"], "zip", T.CATEGORY),
        (["+001"], "zip", T.CATEGORY),
        (["9007199254740993"], "x", T.CATEGORY),
        (["9007199254740991"], "x", T.NUMBER),
        (["1e400"], "x", T.CATEGORY),
        (["NaN", "Infinity"], "x", T.CATEGORY),
        (["$5", "1,000"], "x", T.CATEGORY),
        ([str(i) for i in range(10)], "USER_ID", T.IDENTIFIER),
        ([str(i) for i in range(9)], "id", T.NUMBER),
        ([str(i / 10) for i in range(100)], "temperature", T.NUMBER),
        (["NA", "N/A", "null", "None", "?", " "], "x", T.CATEGORY),
        (["1"] * 51 + ["tail contradiction"], "x", T.CATEGORY),
    ],
)
def test_detection(values, name, expected):
    assert infer_schema(table(values, name)).columns[0].detected == expected


def test_effective_counts_samples_missing_and_full_preview():
    data = table(["1", "1.0", " 1 ", "", "2"] + ["3"] * 55)
    schema = infer_schema(data)
    p = schema.columns[0]
    assert p.distinct_count == 3 and p.missing_count == 1
    assert p.samples == ("1", "1.0", " 1 ")
    view = preview(data, schema)
    assert view["row_count"] == 60 and view["shown_rows"] == 50
    assert len(view["rows"]) == 50 and view["label"] == "First 50 of 60 rows"
    assert view["columns"][0]["missing_percent"] == pytest.approx(100 / 60)


def test_atomic_override_reset_and_provenance():
    data = table(["001", "002", "003"])
    raw = data.rows
    detected = infer_schema(data)
    numeric = change_type(data, detected, "c0", T.NUMBER)
    assert numeric.columns[0].effective == T.NUMBER
    assert numeric.columns[0].detected == T.CATEGORY
    assert numeric.columns[0].overridden
    category = change_type(data, numeric, "c0", T.CATEGORY)
    assert interpreted(data.rows[0][0], category.columns[0].effective) == "001"
    reset = change_type(data, category, "c0", None)
    assert not reset.columns[0].overridden and reset.revision == 3
    assert effective_fingerprint(data, reset) == effective_fingerprint(data, detected)
    assert effective_fingerprint(data, numeric) != effective_fingerprint(data, detected)
    assert data.rows is raw
    for kind in (T.DATE, T.BOOLEAN, T.UNKNOWN):
        with pytest.raises(DomainError):
            change_type(data, category, "c0", kind)
    assert category.columns[0].effective == T.CATEGORY and category.revision == 2


def test_invalid_override_counts_locations_no_values():
    data = table(["1", "private", "2", "secret"])
    original = infer_schema(data)
    with pytest.raises(DomainError) as caught:
        change_type(data, original, "c0", T.NUMBER)
    assert caught.value.row == 1 and caught.value.column == "c0"
    assert "2 values" in str(caught.value) and "2, 4" in str(caught.value)
    assert "private" not in str(caught.value) and "secret" not in str(caught.value)
    assert original.revision == 0
    with pytest.raises(DomainError):
        change_type(data, original, "absent", T.CATEGORY)
    empty = table(["", None])
    with pytest.raises(DomainError):
        change_type(empty, infer_schema(empty), "c0", T.CATEGORY)


def test_mixed_json_kinds_and_explicit_category_ack(tmp_path):
    path = tmp_path / "mixed.jsonl"
    path.write_text("\n".join(json.dumps({"x": v}) for v in [1, "01", True, None]))
    data = load_dataset(path)
    schema = infer_schema(data)
    assert "MIXED_KINDS" in schema.columns[0].warnings
    changed = change_type(data, schema, "c0", T.CATEGORY)
    assert "MIXED_KINDS" not in changed.columns[0].warnings
    assert [interpreted(row[0], T.CATEGORY) for row in data.rows] == [
        "1",
        "01",
        "true",
        None,
    ]
    assert "MIXED_KINDS" in change_type(data, changed, "c0", None).columns[0].warnings


def test_warning_boundaries():
    assert (
        "HIGH_CARDINALITY"
        not in infer_schema(table([f"a{i}" for i in range(19)])).columns[0].warnings
    )
    assert (
        "HIGH_CARDINALITY"
        in infer_schema(table([f"a{i}" for i in range(20)])).columns[0].warnings
    )
    assert (
        "HIGH_CARDINALITY"
        in infer_schema(table([f"a{i}" for i in range(51)] * 10)).columns[0].warnings
    )
    assert "LONG_TEXT" in infer_schema(table(["x" * 201])).columns[0].warnings
    assert "PRECISION" in infer_schema(table(["9007199254740993"])).columns[0].warnings
    assert "LEADING_ZEROS" in infer_schema(table(["001"])).columns[0].warnings


def test_compatible_json_kinds_do_not_need_mixed_warning(tmp_path):
    path = tmp_path / "compatible.jsonl"
    path.write_text('{"x":1,"b":true}\n{"x":"1.0","b":"TRUE"}\n')
    schema = infer_schema(load_dataset(path))
    assert [p.effective for p in schema.columns] == [T.NUMBER, T.BOOLEAN]
    assert all("MIXED_KINDS" not in p.warnings for p in schema.columns)


def test_controls_escaped_only_for_presentation():
    raw = "\x1b[31m[bold]\n\t\u202e\u2028"
    data = table([raw])
    schema = infer_schema(data)
    shown = preview(data, schema)["rows"][0][0]
    assert shown == visible_text(raw)
    assert "\x1b" not in shown and "\n" not in shown and "\u202e" not in shown
    assert "[bold]" in shown  # UI must also use literal rendering, not Rich markup.
    assert data.rows[0][0].raw_text == raw


def test_equivalent_semantic_views_across_formats(tmp_path):
    contents = {
        "csv": "x,b,c\n1,true,alpha\n2,false,beta\n",
        "tsv": "x\tb\tc\n1\ttrue\talpha\n2\tfalse\tbeta\n",
        "jsonl": '{"x":1,"b":true,"c":"alpha"}\n{"c":"beta","b":false,"x":2}\n',
    }
    views = []
    for extension, content in contents.items():
        path = tmp_path / f"equivalent.{extension}"
        path.write_text(content)
        data = load_dataset(path)
        schema = infer_schema(data)
        views.append(
            [
                [interpreted(cell, p.effective) for cell, p in zip(row, schema.columns)]
                for row in data.rows
            ]
        )
    assert views[0] == views[1] == views[2]


def _decimal_reference(text):
    """The original exact interpretation, kept here as the parity oracle."""
    from decimal import Decimal

    decimal = Decimal(text.strip())
    value = float(decimal)
    if not math.isfinite(value):
        return "NUMBER_RANGE"
    if decimal == decimal.to_integral_value() and abs(decimal) > 2**53 - 1:
        return "PRECISION"
    return value


@pytest.mark.parametrize(
    "text",
    [
        "0",
        "-0",
        "+0.0",
        ".5",
        "5.",
        " 7 ",
        "1e5",
        "1E-7",
        "-2.5e+3",
        "0.1",
        "123456.789",
        "4503599627370495",
        "4503599627370496",
        "9007199254740991",
        "9007199254740992",
        "9007199254740993",
        "-9007199254740993",
        "9007199254740993.0",
        "9007199254740993.5",
        "1e16",
        "1.5e16",
        "1e308",
        "1.7976931348623157e308",
        "1.7976931348623159e308",
        "1e309",
        "-1e400",
        "1e-400",
        "0.30000000000000004",
        "123456789012345678901234567890e-20",
    ],
)
def test_number_fast_path_matches_exact_decimal_interpretation(text):
    expected = _decimal_reference(text)
    try:
        actual = interpreted(Cell(text), T.NUMBER)
    except ValueError as error:
        actual = str(error)
    assert actual == expected and type(actual) is type(expected)
    if type(expected) is float:
        assert math.copysign(1, actual) == math.copysign(1, expected)
