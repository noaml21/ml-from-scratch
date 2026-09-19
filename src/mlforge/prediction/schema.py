"""Construct and persist inference-only metadata from the evaluated pipeline."""

import hashlib
import json
import os
import platform
from pathlib import Path

import numpy as np
import skops.io as sio

from mlforge.contracts import ModelBundle, TaskKind
from mlforge.prediction.runtime import (
    ESTIMATORS,
    PRESENT,
    environment,
    load_pipeline,
    normalize_record,
    validate_schema,
)


def json_bytes(value) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n"
    ).encode("utf-8")


def fitted_schema(pipeline, fields: list[dict], train_records: list[dict]) -> dict:
    """Only fitted-row numeric ranges and fitted encoder vocabularies are retained."""
    matrix = np.asarray(
        [normalize_record(row, fields)[0] for row in train_records], dtype=object
    )
    result = [{"name": field["name"], "type": field["type"]} for field in fields]
    for index, field in enumerate(result):
        if field["type"] == "Number":
            values = np.asarray(matrix[:, index], dtype=float)
            present = values[np.isfinite(values)]
            field["minimum"] = float(present.min()) if len(present) else None
            field["maximum"] = float(present.max()) if len(present) else None
    for name, transform, columns in pipeline.steps[0][1].transformers_:
        if name == "category":
            for index, categories in zip(
                columns, transform.steps[-1][1].categories_, strict=True
            ):
                result[index]["categories"] = [
                    str(value)[len(PRESENT) :]
                    for value in categories
                    if str(value).startswith(PRESENT)
                ]
    schema = {"schema_version": 1, "normalization_version": 1, "fields": result}
    validate_schema(schema)
    return schema


def _write(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def save_bundle(
    directory: Path,
    pipeline,
    schema: dict,
    model_id: str,
    *,
    training_count: int,
    test_count: int,
    metrics: dict | None = None,
    diagnostics: dict | None = None,
    warnings: tuple[str, ...] = (),
    partial: bool = False,
) -> ModelBundle:
    """Save exact fitted state; inputs deliberately omit paths, rows and split IDs."""
    validate_schema(schema)
    if model_id not in ESTIMATORS:
        raise ValueError("Unknown model ID")
    model_data = sio.dumps(pipeline)
    load_pipeline(model_data, model_id)
    schema_data = json_bytes(schema)
    meta = {
        "schema_version": 1,
        "normalization_version": 1,
        "model_id": model_id,
        "task": ESTIMATORS[model_id][0],
        "tool": "mlforge",
        "tool_version": "0.1.0",
        "python_version": platform.python_version(),
        "seed": 42,
        "training_count": training_count,
        "test_count": test_count,
        "split_policy": "80/20 shuffled holdout"
        if test_count
        else "all-row exploration",
        "estimator_params": pipeline.steps[-1][1].get_params(),
        "metrics": metrics or {},
        "diagnostics": diagnostics or {},
        "warnings": list(warnings),
        "partial_run": partial,
        "environment": environment(),
        "model_sha256": hashlib.sha256(model_data).hexdigest(),
        "schema_sha256": hashlib.sha256(schema_data).hexdigest(),
    }
    metadata_data = json_bytes(meta)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, data in (
        ("schema.json", schema_data),
        ("metadata.json", metadata_data),
        ("model.skops", model_data),
    ):
        _write(directory / name, data)
    return ModelBundle(
        str(directory),
        model_id,
        TaskKind(meta["task"]),
        meta["model_sha256"],
        meta["schema_sha256"],
        metadata_data.decode(),
    )
