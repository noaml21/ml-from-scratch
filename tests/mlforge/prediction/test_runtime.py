import copy

import numpy as np
import pytest

from mlforge.prediction.runtime import (
    InputValidationError,
    UnsupportedOperationError,
    normalize_record,
    number,
)


def test_six_pipeline_roundtrips(fitted_bundle):
    bundle, predictor, pipeline, records, fields = fitted_bundle
    matrix = np.asarray([normalize_record(records[0], fields)[0]], dtype=object)
    if bundle.task.value == "reduction":
        np.testing.assert_allclose(
            predictor.transform(records[0])["components"], pipeline.transform(matrix)[0]
        )
        with pytest.raises(UnsupportedOperationError):
            predictor.predict(records[0])
    else:
        result = predictor.predict(records[0])
        key = "cluster" if bundle.task.value == "clustering" else "prediction"
        expected = pipeline.predict(matrix)[0]
        if isinstance(expected, str):
            assert result[key] == expected
        else:
            np.testing.assert_allclose(result[key], expected, rtol=1e-8, atol=1e-10)
        with pytest.raises(UnsupportedOperationError):
            predictor.transform(records[0])


def test_missing_unknown_ranges_and_order(fitted_bundle):
    bundle, predictor, _, records, _ = fitted_bundle
    operation = (
        predictor.transform if bundle.task.value == "reduction" else predictor.predict
    )
    assert operation(dict(reversed(list(records[0].items())))) == operation(records[0])
    record = copy.deepcopy(records[0])
    record["x"] = None
    record["z"] = 999.0
    if "city" in record:
        record["city"] = "new category"
    result = operation(record)
    codes = {warning["code"] for warning in result["warnings"]}
    assert {"MISSING_IMPUTED", "OUTSIDE_TRAINING_RANGE"} <= codes
    assert ("UNKNOWN_CATEGORY" in codes) == ("city" in record)
    assert not any(
        w["code"] == "UNKNOWN_CATEGORY" for w in operation(records[2])["warnings"]
    )


def test_whole_batch_validation_and_metadata_copy(fitted_bundle, monkeypatch):
    bundle, predictor, _, records, _ = fitted_bundle
    operation = (
        predictor.transform_many
        if bundle.task.value == "reduction"
        else predictor.predict_many
    )
    method = "transform" if bundle.task.value == "reduction" else "predict"
    calls = []
    monkeypatch.setattr(
        predictor._pipeline, method, lambda matrix: calls.append(matrix)
    )
    with pytest.raises(InputValidationError, match="Record 1"):
        operation([records[0], {}])
    assert calls == []
    assert operation([]) == []
    with pytest.raises(InputValidationError, match="BATCH_LIMIT"):
        operation([records[0]] * 1001)
    metadata = predictor.metadata
    metadata["environment"]["dependencies"]["numpy"] = "changed"
    assert predictor.metadata["environment"]["dependencies"]["numpy"] != "changed"


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        float("nan"),
        float("inf"),
        2**53,
        "9007199254740992",
        "1e400",
        "",
        "1,000",
        "NA",
        [],
        object(),
    ],
)
def test_invalid_numbers(value):
    with pytest.raises(InputValidationError):
        number(value, "measurement")


@pytest.mark.parametrize(
    "value,expected",
    [(" 1.5 ", 1.5), ("-2e-2", -0.02), (2**53 - 1, float(2**53 - 1)), (".2", 0.2)],
)
def test_valid_numbers(value, expected):
    assert number(value, "measurement") == expected


def test_boolean_category_and_sentinel():
    fields = [
        {"name": "flag", "type": "Boolean", "categories": ["true", "false"]},
        {"name": "label", "type": "Category", "categories": ["m:", ""]},
    ]
    values, warnings = normalize_record({"flag": "TRUE", "label": "m:"}, fields)
    assert values == ["v:true", "v:m:"] and not warnings
    assert normalize_record({"flag": False, "label": ""}, fields)[0] == [
        "v:false",
        "v:",
    ]
    with pytest.raises(InputValidationError):
        normalize_record({"flag": 1, "label": "x"}, fields)
    with pytest.raises(InputValidationError):
        normalize_record({"flag": True, "label": 1}, fields)
    with pytest.raises(InputValidationError):
        normalize_record({"flag": True, "label": "x", "target": "secret"}, fields)
