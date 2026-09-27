"""Private service records reject malformed nested data without object loading."""

import pytest

from mlforge.contracts import (
    CandidateResult,
    CandidateStatus,
    candidate_data,
    candidate_from_data,
    prepared_data,
    prepared_from_data,
)
from mlforge.datasets.records import dataset_data, dataset_from_data


@pytest.mark.parametrize(
    "text",
    [
        '{"x":1,"x":2}',
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":1e999}',
        '{"x":9007199254740992}',
        '{"x":"\\ud800"}',
        "[]",
        '{"x":' * 14 + "0" + "}" * 14,
    ],
)
def test_nested_metadata_rejected(text):
    value = candidate_data(
        CandidateResult("classification.logistic", CandidateStatus.FAILED, 0)
    )
    value["diagnostics_json"] = text
    with pytest.raises(ValueError):
        candidate_from_data(value, "/parent/assigned")


def test_prepared_and_raw_data_roundtrip_and_corruption(prepared_candidate):
    dataset, prepared, _ = prepared_candidate
    assert dataset_from_data(dataset_data(dataset)) == dataset
    assert prepared_from_data(prepared_data(prepared)) == prepared
    for field in ("policy_json", "environment_json"):
        value = prepared_data(prepared)
        value[field] = '{"x":NaN}'
        with pytest.raises(ValueError):
            prepared_from_data(value)
    value = dataset_data(dataset)
    value["rows"][0][0][0] = "tampered"
    with pytest.raises(ValueError):
        dataset_from_data(value)
    value = prepared_data(prepared)
    value["train_rows"][0] = True
    with pytest.raises(ValueError):
        prepared_from_data(value)
