"""Packaged examples are synthetic, reproducible and use ordinary validation."""

import importlib.util
from importlib import resources
from pathlib import Path

import pytest

from mlforge.datasets.importers import EXAMPLES, load_dataset
from mlforge.datasets.inference import infer_schema
from mlforge.datasets.records import ColumnType


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda example: example.filename)
def test_packaged_example_passes_real_importer(example):
    resource = resources.files("mlforge").joinpath("examples", example.filename)
    original = resource.read_bytes()
    with resources.as_file(resource) as path:
        dataset = load_dataset(path)
    schema = infer_schema(dataset)
    assert len(dataset.rows) >= 60
    assert len(schema.columns) == len(dataset.columns)
    assert all(p.effective != ColumnType.UNKNOWN for p in schema.columns)
    assert resource.read_bytes() == original
    if example.filename == "mixed.csv":
        assert [p.effective for p in schema.columns] == [
            ColumnType.IDENTIFIER,
            ColumnType.NUMBER,
            ColumnType.NUMBER,
            ColumnType.CATEGORY,
            ColumnType.CATEGORY,
            ColumnType.BOOLEAN,
            ColumnType.DATE,
            ColumnType.CATEGORY,
        ]
        assert schema.columns[2].missing_count == 7
        assert dataset.rows[0][3].raw_text == "0001"


def test_formulas_reproduce_committed_bytes():
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "example_generator", root / "scripts/generate_examples.py"
    )
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generated = generator.examples()
    assert set(generated) == {example.filename for example in EXAMPLES}
    for filename, content in generated.items():
        assert (
            resources.files("mlforge").joinpath("examples", filename).read_bytes()
            == content.encode()
        )
