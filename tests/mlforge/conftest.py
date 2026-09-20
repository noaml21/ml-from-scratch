"""Provisional persistence fixtures and real canonical evaluated candidates."""

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


@pytest.fixture(scope="module", params=MODELS, ids=lambda model: model.id)
def prepared_candidate(request, tmp_path_factory):
    """Real canonical input and preparation, including categorical supervised inputs."""
    from dataclasses import replace

    from mlforge.contracts import ExperimentSpec
    from mlforge.datasets.importers import load_dataset
    from mlforge.datasets.inference import infer_schema
    from mlforge.preprocessing import prepare_run
    from mlforge.tasks import review_warnings

    model = request.param
    source = tmp_path_factory.mktemp("canonical") / "input.csv"
    lines = ["x,z,city,flag,outcome"]
    for i in range(60):
        x = "" if i == 7 else str(i % 13)
        z = str(i // 5 + 0.1 * (i % 3))
        outcome = (
            str(i * 1.5) if model.id.startswith("regression") else ["no", "yes"][i % 2]
        )
        lines.append(
            f"{x},{z},{['north', 'south', 'm:'][i % 3]},"
            f"{['false', 'true'][i % 2]},{outcome}"
        )
    source.write_text("\n".join(lines) + "\n")
    dataset = load_dataset(source)
    schema = infer_schema(dataset)
    spec = ExperimentSpec(
        1,
        dataset.fingerprint,
        model.task,
        "c4" if model.task.supervised else None,
        ("c0", "c1", "c2", "c3") if model.task.supervised else ("c0", "c1"),
        (model.id,),
        1 if model.id == "reduction.pca" else 3 if not model.task.supervised else None,
    )
    spec = replace(
        spec,
        acknowledgements=tuple(w.code for w in review_warnings(dataset, schema, spec)),
    )
    return dataset, prepare_run(dataset, schema, spec), model


@pytest.fixture(scope="module")
def evaluated_bundle(prepared_candidate, tmp_path_factory):
    from pathlib import Path

    from mlforge.prediction.runtime import load_pipeline
    from mlforge.preprocessing import input_fields, raw_records
    from mlforge.training import train_candidate

    dataset, prepared, model = prepared_candidate
    result = train_candidate(
        dataset, prepared, model.id, tmp_path_factory.mktemp("evaluated") / "bundle"
    )
    bundle = result.bundle
    return (
        bundle,
        Predictor._from_directory(bundle.directory),
        load_pipeline((Path(bundle.directory) / "model.skops").read_bytes(), model.id),
        raw_records(
            dataset, prepared.experiment.feature_ids, tuple(range(len(dataset.rows)))
        ),
        input_fields(dataset, prepared.schema, prepared.experiment.feature_ids),
    )
