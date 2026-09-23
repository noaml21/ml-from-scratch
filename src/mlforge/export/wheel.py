"""Fixed-template offline wheel build, verification and no-overwrite publication."""

import base64
import csv
import hashlib
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import zipfile
from email.parser import BytesParser
from importlib import resources
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version

from mlforge.contracts import DomainError, ExportOptions, ModelBundle, distribution_name
from mlforge.prediction.runtime import (
    INFERENCE_DEPENDENCIES,
    ArtifactError,
    Predictor,
    validate_archive,
)

RESERVED = set(sys.stdlib_module_names) | {
    "mlforge",
    "numpy",
    "scipy",
    "sklearn",
    "skops",
    "packaging",
    "threadpoolctl",
    "joblib",
    "cloudpickle",
    "narwhals",
    "prettytable",
    "wcwidth",
}
RESERVED_DISTRIBUTIONS = {
    canonicalize_name(name) for name in (*RESERVED, *INFERENCE_DEPENDENCIES)
}
VERIFY_CODE = """
import importlib
import json
import sys
sys.path.insert(0, sys.argv[1])
model = importlib.import_module(sys.argv[2]).Predictor()
with open(sys.argv[3], encoding='utf-8') as stream:
    probes = json.load(stream)
operation = (
    model.transform_many
    if model.metadata['task'] == 'reduction' else model.predict_many
)
with open(sys.argv[4], 'w', encoding='utf-8') as stream:
    json.dump(operation(probes), stream, allow_nan=False)
"""


def validate_options(module_name: str, version: str) -> None:
    ExportOptions(module_name, version)
    if (
        module_name in RESERVED
        or distribution_name(module_name) in RESERVED_DISTRIBUTIONS
    ):
        raise DomainError(
            "PACKAGE_NAME",
            "Choose a valid, non-reserved module name.",
            "Use 3–50 lowercase letters, digits or underscores; start with a letter.",
        )
    if str(Version(version)) != version:
        raise DomainError(
            "PACKAGE_VERSION",
            "Use a three-part version such as 1.0.0.",
            "Use nonnegative integers without leading zeros.",
        )


def wheel_stem(module_name: str, version: str) -> str:
    return ExportOptions(module_name, version).wheel_stem


def validate_wheel(data: bytes, module_name: str, version: str) -> None:
    try:
        _validate_wheel(data, module_name, version)
    except (ValueError, KeyError, TypeError, UnicodeError, zipfile.BadZipFile) as exc:
        raise ArtifactError("WHEEL_METADATA: malformed wheel metadata") from exc


def _validate_wheel(data: bytes, module_name: str, version: str) -> None:
    validate_archive(data, members=200)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
        info = f"{wheel_stem(module_name, version)}.dist-info"
        required = {
            f"{module_name}/{name}"
            for name in (
                "__init__.py",
                "_runtime.py",
                "schema.json",
                "metadata.json",
                "model.skops",
                "MODEL_CARD.md",
            )
        } | {
            f"{info}/{name}"
            for name in ("METADATA", "WHEEL", "RECORD", "top_level.txt")
        }
        if names != required:
            raise ArtifactError(
                "WHEEL_CONTENTS: unexpected or missing package resource"
            )
        meta = json.loads(archive.read(f"{module_name}/metadata.json"))
        headers = BytesParser().parsebytes(archive.read(f"{info}/METADATA"))
        wheel_headers = BytesParser().parsebytes(archive.read(f"{info}/WHEEL"))
        minor = int(meta["environment"]["python_minor"].split(".")[1])
        expected_dependencies = {
            str(Requirement(f"{name}=={value}"))
            for name, value in meta["environment"]["dependencies"].items()
        }
        if (
            canonicalize_name(headers["Name"]) != distribution_name(module_name)
            or headers["Version"] != version
            or SpecifierSet(headers["Requires-Python"])
            != SpecifierSet(f">=3.{minor},<3.{minor + 1}")
            or {
                str(Requirement(value))
                for value in headers.get_all("Requires-Dist", [])
            }
            != expected_dependencies
            or wheel_headers.get_all("Tag") != ["py3-none-any"]
            or wheel_headers["Root-Is-Purelib"] != "true"
            or archive.read(f"{info}/top_level.txt").decode().strip() != module_name
        ):
            raise ArtifactError("WHEEL_METADATA: incompatible distribution metadata")
        records = list(csv.reader(io.StringIO(archive.read(f"{info}/RECORD").decode())))
        if len(records) != len(names) or {row[0] for row in records} != names:
            raise ArtifactError("WHEEL_RECORD: incomplete resource manifest")
        for name, digest, size in records:
            if name.endswith("/RECORD"):
                if digest or size:
                    raise ArtifactError("WHEEL_RECORD: invalid RECORD self-entry")
                continue
            content = archive.read(name)
            expected = (
                "sha256="
                + base64.urlsafe_b64encode(hashlib.sha256(content).digest())
                .rstrip(b"=")
                .decode()
            )
            if digest != expected or size != str(len(content)):
                raise ArtifactError("WHEEL_RECORD: resource digest or size differs")
        validate_archive(archive.read(f"{module_name}/model.skops"), members=2000)


def _equal(expected, actual):
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and expected.keys() == actual.keys()
            and all(_equal(v, actual[k]) for k, v in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(_equal(a, b) for a, b in zip(expected, actual, strict=True))
        )
    if type(expected) is float:
        return type(actual) in {float, int} and math.isclose(
            expected, actual, rel_tol=1e-8, abs_tol=1e-10
        )
    return type(expected) is type(actual) and expected == actual


def _card(meta: dict, fields: list[dict], module_name: str) -> str:
    example = {
        field["name"]: 0.0
        if field["type"] == "Number"
        else False
        if field["type"] == "Boolean"
        else "example"
        for field in fields
    }
    operation = "transform" if meta["task"] == "reduction" else "predict"
    return f"""# Fitted model package

Task: {meta["task"]}. Model: {meta["model_id"]}.
Training rows: {meta["training_count"]}. Evaluation rows: {meta["test_count"]}.
Split: {meta["split_policy"]}. Partial run: {meta["partial_run"]}.
Created by MLForge {meta["tool_version"]}; seed 42.

The exact evaluated preprocessing and estimator are retained; no full-data refit.
Numeric inputs use fitted median defaults and model-specific scaling. Categories
use a reserved missing marker and bounded one-hot encoding; unseen categories
produce warnings. None explicitly requests missing-value handling.

Metrics: {json.dumps(meta["metrics"], ensure_ascii=False)}.
Classification accuracy is fraction correct; Macro F1 averages class F1 scores.
Regression MAE is mean absolute error; R² compares squared error to test variance.
Holdout model selection can be optimistic: validate independently before relying
on predictions. Unsupervised diagnostics describe this dataset, not accuracy.
Cluster IDs are arbitrary. PCA components are standardized-space coordinates.

No original rows or probe inputs are bundled. Fitted parameters, categories and
labels can still reveal information; the model is not an anonymization guarantee.
Only install wheels from a trusted publisher. SHA-256 detects corruption, not
authenticity. Forests are restricted to trusted MLForge-generated artifacts.

Environment: {json.dumps(meta["environment"], sort_keys=True)}.
Use the exporting CPython minor on supported Linux x86_64 with exact dependencies.
Predictor eagerly validates its bundled resources. No arbitrary load(path) API.

```python
from {module_name} import Predictor
model = Predictor()
result = model.{operation}({example!r})
```

Install the local wheel with `python -m pip install /path/to/the/wheel.whl`.
Batch API: {operation}_many, at most 1000 records; empty batches return [].
No license grant or publication is implied by this local artifact.
"""


def export_wheel(
    bundle: ModelBundle,
    destination: Path,
    module_name: str,
    version: str,
    probes: list[dict],
) -> Path:
    """Called in an owned operation child; descendants inherit its process group."""
    validate_options(module_name, version)
    destination = destination.expanduser().resolve()
    final = destination / f"{wheel_stem(module_name, version)}-py3-none-any.whl"
    if final.exists():
        raise DomainError(
            "EXPORT_EXISTS",
            "That wheel already exists.",
            "Change name, version or destination.",
        )
    source = Path(bundle.directory)
    predictor = Predictor._from_directory(source)
    meta = predictor.metadata
    if (
        meta != json.loads(bundle.metadata_json)
        or meta["model_sha256"] != bundle.model_sha256
        or meta["schema_sha256"] != bundle.schema_sha256
    ):
        raise ArtifactError(
            "BUNDLE_CHANGED: accepted model no longer matches its handle"
        )
    if not probes:
        raise ValueError("Export verification requires an observed probe input")
    operation = (
        predictor.transform_many
        if meta["task"] == "reduction"
        else predictor.predict_many
    )
    expected = operation(probes)
    env = dict(os.environ, PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    env.pop("PYTHONPATH", None)
    try:
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="export-", dir=source.parent
        ) as stage_name:
            stage = Path(stage_name)
            package = stage / module_name
            package.mkdir(mode=0o700)
            runtime = (
                resources.files("mlforge.prediction")
                .joinpath("runtime.py")
                .read_bytes()
            )
            init = (
                resources.files("mlforge.export")
                .joinpath("templates/init.txt")
                .read_bytes()
            )
            schema_data = (source / "schema.json").read_bytes()
            model_data = (source / "model.skops").read_bytes()
            metadata_data = (source / "metadata.json").read_bytes()
            if (
                hashlib.sha256(model_data).hexdigest() != bundle.model_sha256
                or hashlib.sha256(schema_data).hexdigest() != bundle.schema_sha256
                or json.loads(metadata_data) != json.loads(bundle.metadata_json)
            ):
                raise ArtifactError("BUNDLE_CHANGED: resources changed during export")
            fields = json.loads(schema_data)["fields"]
            for name, data in (
                ("__init__.py", init),
                ("_runtime.py", runtime),
                ("schema.json", schema_data),
                ("metadata.json", metadata_data),
                ("model.skops", model_data),
                ("MODEL_CARD.md", _card(meta, fields, module_name).encode()),
            ):
                (package / name).write_bytes(data)
                (package / name).chmod(0o600)
            minor = int(meta["environment"]["python_minor"].split(".")[1])
            dependencies = [
                f"{name}=={value}"
                for name, value in meta["environment"]["dependencies"].items()
            ]
            (stage / "pyproject.toml").write_text(f'''[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"
[project]
name = "{distribution_name(module_name)}"
version = "{version}"
description = "A locally fitted MLForge model"
requires-python = ">=3.{minor},<3.{minor + 1}"
dependencies = {json.dumps(dependencies)}
[tool.setuptools]
packages = ["{module_name}"]
[tool.setuptools.package-data]
"{module_name}" = ["*.json", "*.skops", "*.md"]
''')
            with (stage / "build.log").open("wb") as log:
                result = subprocess.run(
                    [sys.executable, "-m", "build", "--wheel", "--no-isolation"],
                    cwd=stage,
                    env=env,
                    stdout=log,
                    stderr=log,
                )
            if result.returncode:
                raise DomainError(
                    "EXPORT_BUILD",
                    "Wheel build failed.",
                    "Check installed build dependencies and retry.",
                )
            wheel = stage / "dist" / final.name
            data = wheel.read_bytes()
            validate_wheel(data, module_name, version)
            probe_path, result_path = stage / "probes.json", stage / "verified.json"
            probe_path.write_text(json.dumps(probes, allow_nan=False))
            probe_path.chmod(0o600)
            with (stage / "verify.log").open("wb") as log:
                checked = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-c",
                        VERIFY_CODE,
                        str(wheel),
                        module_name,
                        str(probe_path),
                        str(result_path),
                    ],
                    cwd=stage,
                    env=env,
                    stdout=log,
                    stderr=log,
                )
            if checked.returncode or not _equal(
                expected, json.loads(result_path.read_text())
            ):
                raise ArtifactError("EXPORT_PARITY: packaged predictions differ")
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    prefix=".mlforge-", dir=destination, delete=False
                ) as output:
                    temporary = Path(output.name)
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                os.link(temporary, final)
                directory_fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return final
    except FileExistsError as exc:
        raise DomainError(
            "EXPORT_EXISTS",
            "That wheel already exists.",
            "Change name, version or destination.",
        ) from exc
    except OSError as exc:
        raise DomainError(
            "EXPORT_IO",
            "Could not write and publish the wheel safely.",
            "Choose a writable destination with free space and retry.",
        ) from exc
