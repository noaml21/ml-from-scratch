"""Standalone inference source copied unchanged into generated model packages.

Predictor eagerly validates its own bundled resources. Private helpers support
MLForge's operation children; there is no public arbitrary-model loading API.
"""

import copy
import hashlib
import io
import json
import math
import platform
import re
import sys
import zipfile
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from importlib import metadata, resources
from pathlib import Path, PurePosixPath

import numpy as np
import skops.io as sio

MAX_ARCHIVE = 100 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MISSING = "m:"
PRESENT = "v:"
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
INFERENCE_DEPENDENCIES = (
    "numpy",
    "scipy",
    "scikit-learn",
    "skops",
    "packaging",
    "threadpoolctl",
    "joblib",
    "cloudpickle",
    "narwhals",
    "prettytable",
    "wcwidth",
)
ESTIMATORS = {
    "classification.logistic": ("classification", "LogisticRegression"),
    "classification.forest": ("classification", "RandomForestClassifier"),
    "regression.linear": ("regression", "LinearRegression"),
    "regression.forest": ("regression", "RandomForestRegressor"),
    "clustering.kmeans": ("clustering", "KMeans"),
    "reduction.pca": ("reduction", "PCA"),
}


class InputValidationError(ValueError):
    """Record does not match the exported input schema."""


class CompatibilityError(RuntimeError):
    """Use a fresh environment with the exact exported dependency versions."""


class ArtifactError(RuntimeError):
    """The bundled model failed integrity or structural validation."""


class UnsupportedOperationError(ValueError):
    """The requested operation does not apply to this task."""


def _json(data: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Nonfinite JSON")

    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ArtifactError("INVALID_JSON: bundled metadata is invalid") from exc


def _read(root, name: str, limit: int) -> bytes:
    try:
        with root.joinpath(name).open("rb") as stream:
            data = stream.read(limit + 1)
    except OSError as exc:
        raise ArtifactError("MISSING_RESOURCE: model package is incomplete") from exc
    if len(data) > limit:
        raise ArtifactError("RESOURCE_LIMIT: bundled resource is too large")
    return data


def validate_archive(data: bytes, *, members: int) -> None:
    """Check outer wheels and nested skops independently before deserialization."""
    if len(data) > MAX_ARCHIVE:
        raise ArtifactError("ARCHIVE_LIMIT: compressed archive exceeds 100 MiB")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > members or sum(i.file_size for i in infos) > MAX_EXPANDED:
                raise ArtifactError("ARCHIVE_LIMIT: archive expansion exceeds limits")
            names = set()
            for info in infos:
                path = PurePosixPath(info.filename)
                if (
                    not info.filename
                    or info.filename in names
                    or path.is_absolute()
                    or path.as_posix() != info.filename.rstrip("/")
                    or (path.parts and ":" in path.parts[0])
                    or ".." in path.parts
                    or "\\" in info.filename
                    or "\x00" in info.filename
                    or info.flag_bits & 1
                    or (info.external_attr >> 16) & 0o170000 == 0o120000
                ):
                    raise ArtifactError(
                        "ARCHIVE_PATH: unsafe or duplicate archive member"
                    )
                names.add(info.filename)
    except (zipfile.BadZipFile, ValueError, OSError) as exc:
        raise ArtifactError("INVALID_ARCHIVE: model archive is invalid") from exc


def environment() -> dict:
    return {
        "python_minor": f"{sys.version_info.major}.{sys.version_info.minor}",
        "platform": platform.system(),
        "implementation": platform.python_implementation(),
        "machine": platform.machine(),
        "dependencies": {
            name: metadata.version(name) for name in INFERENCE_DEPENDENCIES
        },
    }


def validate_environment(record: dict) -> None:
    actual = environment()
    if (
        actual["platform"] != "Linux"
        or actual["implementation"] != "CPython"
        or actual["machine"] != "x86_64"
        or actual["python_minor"] not in {"3.12", "3.13"}
        or record != actual
    ):
        raise CompatibilityError(
            "VERSION_MISMATCH: use a fresh supported Linux environment "
            "with its exact Python minor and pinned dependencies"
        )


def number(value, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise InputValidationError(f"NUMBER_REQUIRED: {field}")
    text = value.strip() if isinstance(value, str) else str(value)
    if not NUMBER.fullmatch(text):
        raise InputValidationError(f"NUMBER_REQUIRED: {field}")
    try:
        decimal = Decimal(text)
        result = float(decimal)
        if not math.isfinite(result):
            raise ValueError
        if decimal == decimal.to_integral_value() and abs(decimal) > 2**53 - 1:
            raise ValueError
    except (ValueError, OverflowError, InvalidOperation) as exc:
        raise InputValidationError(f"NUMBER_RANGE: {field}") from exc
    return result


def normalize_record(record, fields: list[dict]) -> tuple[list, list[dict]]:
    names = {field["name"] for field in fields}
    if not isinstance(record, Mapping) or set(record) != names:
        raise InputValidationError(
            "FIELD_NAMES: provide exactly the selected feature names"
        )
    values, warnings = [], []
    for field in fields:
        name, kind = field["name"], field["type"]
        raw = record[name]
        if raw is None:
            values.append(np.nan)
            warnings.append(
                {
                    "code": "MISSING_IMPUTED",
                    "field": name,
                    "message": "Missing input uses the fitted default.",
                }
            )
            continue
        if kind == "Number":
            value = number(raw, name)
            if field.get("minimum") is not None and (
                value < field["minimum"] or value > field["maximum"]
            ):
                warnings.append(
                    {
                        "code": "OUTSIDE_TRAINING_RANGE",
                        "field": name,
                        "message": "Input is outside the fitted data range.",
                    }
                )
        else:
            if kind == "Boolean":
                if isinstance(raw, bool):
                    raw = "true" if raw else "false"
                elif isinstance(raw, str) and raw.lower() in {"true", "false"}:
                    raw = raw.lower()
                else:
                    raise InputValidationError(f"BOOLEAN_REQUIRED: {name}")
            elif not isinstance(raw, str):
                raise InputValidationError(f"CATEGORY_TEXT_REQUIRED: {name}")
            value = PRESENT + raw
            if "categories" in field and raw not in field["categories"]:
                warnings.append(
                    {
                        "code": "UNKNOWN_CATEGORY",
                        "field": name,
                        "message": "Unknown category uses the fitted encoding.",
                    }
                )
        values.append(value)
    return values, warnings


def validate_schema(schema) -> list[dict]:
    if (
        not isinstance(schema, dict)
        or schema.get("schema_version") != 1
        or schema.get("normalization_version") != 1
        or not isinstance(schema.get("fields"), list)
        or not 1 <= len(schema["fields"]) <= 100
    ):
        raise ArtifactError("SCHEMA_VERSION: unsupported input schema")
    fields, names = schema["fields"], set()
    for field in fields:
        if (
            not isinstance(field, dict)
            or not isinstance(field.get("name"), str)
            or not field["name"]
            or len(field["name"]) > 128
            or field["name"] in names
            or not isinstance(field.get("type"), str)
            or field.get("type") not in {"Number", "Category", "Boolean"}
        ):
            raise ArtifactError("SCHEMA_FIELD: invalid input field")
        names.add(field["name"])
        if field["type"] == "Number":
            low, high = field.get("minimum"), field.get("maximum")
            if (low is None) != (high is None) or (
                low is not None
                and (
                    type(low) not in {float, int}
                    or type(high) not in {float, int}
                    or not math.isfinite(low)
                    or not math.isfinite(high)
                    or low > high
                )
            ):
                raise ArtifactError("SCHEMA_RANGE: invalid fitted range")
        else:
            categories = field.get("categories")
            if not isinstance(categories, list) or any(
                type(v) is not str for v in categories
            ):
                raise ArtifactError("SCHEMA_CATEGORIES: invalid fitted categories")
    return fields


def validate_tree_state(state, n_features: int, n_classes: int) -> None:
    """Inspect raw arrays without calling native tree inference."""
    try:
        count = state["node_count"]
        nodes, values = state["nodes"], state["values"]
        if (
            type(count) is not int
            or not 1 <= count <= 8191
            or not 1 <= n_features <= 512
            or not 0 <= state["max_depth"] <= 12
            or nodes.shape != (count,)
            or values.shape != (count, 1, n_classes)
            or not np.isfinite(values).all()
        ):
            raise ValueError
        left, right = nodes["left_child"], nodes["right_child"]
        features = nodes["feature"]
        if (
            any(
                nodes[key].dtype.kind not in "iu"
                for key in (
                    "left_child",
                    "right_child",
                    "feature",
                    "n_node_samples",
                    "missing_go_to_left",
                )
            )
            or not np.isin(nodes["missing_go_to_left"], [0, 1]).all()
        ):
            raise ValueError
        for key in ("threshold", "impurity", "weighted_n_node_samples"):
            if not np.isfinite(nodes[key]).all():
                raise ValueError
        if (nodes["n_node_samples"] < 1).any() or (
            nodes["weighted_n_node_samples"] < 0
        ).any():
            raise ValueError
        visited, stack = set(), [(0, 0)]
        while stack:
            index, depth = stack.pop()
            if index in visited or not 0 <= index < count or depth > 12:
                raise ValueError
            visited.add(index)
            if left[index] == -1 and right[index] == -1:
                if features[index] != -2 or nodes["threshold"][index] != -2:
                    raise ValueError
            else:
                if not 0 <= features[index] < n_features:
                    raise ValueError
                stack.extend(
                    [(int(left[index]), depth + 1), (int(right[index]), depth + 1)]
                )
        if len(visited) != count:
            raise ValueError
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise ArtifactError("TREE_STRUCTURE: malformed forest state") from exc


def load_pipeline(data: bytes, model_id: str):
    if not isinstance(model_id, str) or model_id not in ESTIMATORS:
        raise ArtifactError("MODEL_ID: unsupported estimator")
    validate_archive(data, members=2000)
    allowed = {"numpy.dtype"}
    if model_id.endswith("forest"):
        allowed.add("sklearn.tree._tree.Tree")
    try:
        discovered = set(sio.get_untrusted_types(data=data))
        if not discovered <= allowed:
            raise ArtifactError("UNTRUSTED_TYPE: model contains an unreviewed type")
        pipeline = sio.loads(data, trusted=sorted(allowed))
        from sklearn.compose import ColumnTransformer
        from sklearn.pipeline import Pipeline

        if type(pipeline) is not Pipeline or len(pipeline.steps) != 2:
            raise ArtifactError("PIPELINE_STRUCTURE: invalid fitted pipeline")
        estimator = pipeline.steps[-1][1]
        if (
            type(pipeline.steps[0][1]) is not ColumnTransformer
            or not 1 <= estimator.n_features_in_ <= 512
        ):
            raise ArtifactError("PIPELINE_STRUCTURE: invalid preprocessing shape")
        if type(estimator).__name__ != ESTIMATORS[model_id][1]:
            raise ArtifactError("MODEL_TYPE: estimator does not match metadata")
        if model_id.endswith("forest"):
            if len(estimator.estimators_) != 100 or estimator.n_outputs_ != 1:
                raise ArtifactError("TREE_STRUCTURE: invalid forest shape")
            classes = (
                int(estimator.n_classes_)
                if model_id.startswith("classification")
                else 1
            )
            if not 1 <= classes <= 20:
                raise ArtifactError("TREE_STRUCTURE: invalid class count")
            for tree in estimator.estimators_:
                if tree.tree_.n_features != estimator.n_features_in_:
                    raise ArtifactError("TREE_STRUCTURE: inconsistent feature count")
                validate_tree_state(
                    tree.tree_.__getstate__(), estimator.n_features_in_, classes
                )
        return pipeline
    except ArtifactError:
        raise
    except Exception as exc:
        raise ArtifactError("MODEL_LOAD: bundled model cannot be loaded") from exc


class Predictor:
    """Eagerly validated, task-aware inference over this package's own resources."""

    def __init__(self):
        self._initialize(resources.files(__package__))

    @classmethod
    def _from_directory(cls, directory):
        instance = cls.__new__(cls)
        instance._initialize(Path(directory))
        return instance

    def _initialize(self, root):
        schema_data = _read(root, "schema.json", 2 * 1024 * 1024)
        meta = _json(_read(root, "metadata.json", 4 * 1024 * 1024))
        if not isinstance(meta, dict) or meta.get("schema_version") != 1:
            raise ArtifactError("METADATA_VERSION: unsupported metadata")
        validate_environment(meta.get("environment"))
        model_id = meta.get("model_id")
        if (
            not isinstance(model_id, str)
            or model_id not in ESTIMATORS
            or meta.get("task") != ESTIMATORS[model_id][0]
        ):
            raise ArtifactError("TASK_MISMATCH: invalid task or model")
        model_data = _read(root, "model.skops", MAX_ARCHIVE)
        if hashlib.sha256(model_data).hexdigest() != meta.get(
            "model_sha256"
        ) or hashlib.sha256(schema_data).hexdigest() != meta.get("schema_sha256"):
            raise ArtifactError("HASH_MISMATCH: bundled resources changed")
        self._fields = validate_schema(_json(schema_data))
        self._pipeline = load_pipeline(model_data, model_id)
        if self._pipeline.n_features_in_ != len(self._fields):
            raise ArtifactError(
                "SCHEMA_SHAPE: input count differs from fitted pipeline"
            )
        self._metadata = meta

    @property
    def metadata(self) -> dict:
        return copy.deepcopy(self._metadata)

    def predict(self, record):
        return self.predict_many([record])[0]

    def transform(self, record):
        return self.transform_many([record])[0]

    def predict_many(self, records):
        if self._metadata["task"] == "reduction":
            raise UnsupportedOperationError("PCA uses transform or transform_many")
        return self._run(records, transform=False)

    def transform_many(self, records):
        if self._metadata["task"] != "reduction":
            raise UnsupportedOperationError("This task uses predict or predict_many")
        return self._run(records, transform=True)

    def _run(self, records, *, transform):
        if not isinstance(records, (list, tuple)) or len(records) > 1000:
            raise InputValidationError("BATCH_LIMIT: provide at most 1000 records")
        values, warnings = [], []
        for index, record in enumerate(records):
            try:
                row, notes = normalize_record(record, self._fields)
            except InputValidationError as exc:
                raise InputValidationError(f"Record {index}: {exc}") from exc
            values.append(row)
            warnings.append(notes)
        if not values:
            return []
        try:
            matrix = np.asarray(values, dtype=object)
            outputs = (
                self._pipeline.transform(matrix)
                if transform
                else self._pipeline.predict(matrix)
            )
            results = []
            for output, notes in zip(outputs, warnings, strict=True):
                task = self._metadata["task"]
                if task == "classification":
                    result = {"prediction": str(output)}
                elif task == "regression":
                    if not math.isfinite(float(output)):
                        raise ValueError
                    result = {"prediction": float(output)}
                elif task == "clustering":
                    result = {"cluster": int(output)}
                else:
                    if not np.isfinite(output).all():
                        raise ValueError
                    result = {"components": [float(value) for value in output]}
                result["warnings"] = notes
                results.append(result)
            return results
        except Exception as exc:
            raise ArtifactError(
                "INFERENCE_FAILED: model could not produce finite outputs"
            ) from exc
