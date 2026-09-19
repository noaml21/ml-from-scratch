"""Synthetic provisional vertical slice; P04 supplies canonical dataset training."""

import numpy as np
import pytest

from mlforge.models import MODELS
from mlforge.prediction.runtime import Predictor, normalize_record
from mlforge.prediction.schema import fitted_schema, save_bundle
from mlforge.preprocessing import build_pipeline


@pytest.fixture(scope="module", params=MODELS, ids=lambda model: model.id)
def fitted_bundle(request, tmp_path_factory):
    model = request.param
    fields = [{"name": "x", "type": "Number"}, {"name": "z", "type": "Number"}]
    if model.task.supervised:
        fields += [
            {"name": "city", "type": "Category"},
            {"name": "flag", "type": "Boolean"},
        ]
    records = []
    for index in range(60):
        record = {
            "x": None if index == 7 else float(index % 13),
            "z": float(index // 5) + 0.1 * (index % 3),
        }
        if model.task.supervised:
            record.update(city=["north", "south", "m:"][index % 3], flag=index % 2 == 0)
        records.append(record)
    training = records[:48] if model.task.supervised else records
    matrix = np.asarray(
        [normalize_record(row, fields)[0] for row in training], dtype=object
    )
    option = 1 if model.id == "reduction.pca" else None
    pipeline = build_pipeline(
        fields, model.factory(option), scale_numeric=model.scale_numeric
    )
    target = np.asarray(["yes" if i % 2 else "no" for i in range(48)])
    if model.id.startswith("regression"):
        target = np.arange(48, dtype=float) * 1.5
    pipeline.fit(matrix, target if model.task.supervised else None)
    schema = fitted_schema(pipeline, fields, training)
    directory = tmp_path_factory.mktemp("bundles") / "accepted"
    bundle = save_bundle(
        directory,
        pipeline,
        schema,
        model.id,
        training_count=len(training),
        test_count=60 - len(training),
    )
    predictor = Predictor._from_directory(directory)
    return bundle, predictor, pipeline, records, fields
