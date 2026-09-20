"""Real consumer installs; source/editable packages cannot satisfy these checks."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from mlforge.export.wheel import _equal, export_wheel

ROOT = Path(__file__).resolve().parents[3]
WHEELHOUSE = ROOT / ".mlforge-build/wheelhouse"
NETWORK_GUARD = """
import os
import sys
def reject_network(event, args):
    if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo",
                 "socket.gethostbyname", "socket.sendto"}:
        os._exit(93)
sys.addaudithook(reject_network)
"""
CONSUMER = """
import importlib
import importlib.util
import json
import sys
from importlib.metadata import distributions, version
from pathlib import Path
assert "sitecustomize" in sys.modules, "Network guard was not loaded"
assert not any(Path(p).resolve() == Path(sys.argv[4]).resolve() for p in sys.path if p)
for name in ("mlforge", "textual", "rich"):
    assert importlib.util.find_spec(name) is None, name
package = importlib.import_module(sys.argv[1])
from sklearn.pipeline import Pipeline
def no_refit(*args, **kwargs):
    raise AssertionError("Consumer attempted to fit")
Pipeline.fit = no_refit
model = package.Predictor()
probes = json.loads(Path(sys.argv[2]).read_text())
reduction = model.metadata["task"] == "reduction"
single = model.transform if reduction else model.predict
batch = model.transform_many if reduction else model.predict_many
wrong = model.predict if reduction else model.transform
result = batch(probes)
assert single(probes[0]) == result[0]
assert batch([]) == []
assert not hasattr(package.Predictor, "load")
for invalid in (
    {}, dict(probes[0], extra="not a selected feature"), dict(probes[0], x=True)
):
    try:
        single(invalid)
    except package.InputValidationError:
        pass
    else:
        raise AssertionError("Invalid record accepted")
try:
    batch([probes[0], {}])
except package.InputValidationError as error:
    assert "Record 1" in str(error)
else:
    raise AssertionError("Invalid batch accepted")
try:
    wrong(probes[0])
except package.UnsupportedOperationError:
    pass
else:
    raise AssertionError("Unsupported task API accepted")
meta = model.metadata
for name, expected in meta["environment"]["dependencies"].items():
    assert version(name) == expected
copy = model.metadata
copy["environment"]["dependencies"].clear()
assert model.metadata["environment"]["dependencies"]
package_path = Path(package.__file__).parent
metadata_path = package_path / "metadata.json"
original_metadata = metadata_path.read_bytes()
bad = json.loads(original_metadata)
bad["environment"]["python_minor"] = "0.0"
metadata_path.write_text(json.dumps(bad))
try:
    package.Predictor()
except package.CompatibilityError:
    pass
else:
    raise AssertionError("Incompatible artifact accepted")
metadata_path.write_bytes(original_metadata)
model_path = package_path / "model.skops"
original_model = model_path.read_bytes()
model_path.write_bytes(b"corrupt")
try:
    package.Predictor()
except package.ArtifactError:
    pass
else:
    raise AssertionError("Corrupt artifact accepted")
model_path.write_bytes(original_model)
assert batch(probes) == result
installed = {d.metadata["Name"].lower(): d.version for d in distributions()}
assert not {"mlforge", "textual", "rich"} & installed.keys()
Path(sys.argv[3]).write_text(json.dumps({"results": result, "versions": installed,
    "model_id": meta["model_id"], "network_guard": "active; zero attempts",
    "status": "passed"}, allow_nan=False))
"""


def run(command, cwd, env):
    result = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True, timeout=300
    )
    assert result.returncode == 0, (
        f"Command failed ({result.returncode}): {command}\n"
        f"{result.stdout}\n{result.stderr}"
    )
    return result.stdout.strip()


@pytest.mark.install
def test_fresh_installed_consumer(evaluated_bundle, tmp_path):
    assert WHEELHOUSE.is_dir() and any(WHEELHOUSE.glob("*.whl")), (
        "Prepare dependencies first: "
        "python scripts/verify_package.py --prepare-wheelhouse"
    )
    assert ROOT not in tmp_path.resolve().parents, "Consumer must be outside checkout"
    bundle, predictor, _, records, _ = evaluated_bundle
    module_name = (
        "installed__model" if bundle.model_id.endswith("forest") else "installed_model_"
    )
    missing = dict(records[0], x=None, z=999.0)
    if "city" in missing:
        missing["city"] = "consumer unknown category"
    probes = [records[0], missing, records[2]]
    operation = (
        predictor.transform_many
        if bundle.task.value == "reduction"
        else predictor.predict_many
    )
    expected = operation(probes)
    wheel = export_wheel(bundle, tmp_path / "exports", module_name, "1.0.0", probes)
    env = dict(os.environ, PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    env.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="consumer-", dir=tmp_path) as temporary:
        cwd = Path(temporary)
        venv = cwd / "venv"
        run([sys.executable, "-m", "venv", str(venv)], cwd, env)
        python = str(venv / "bin/python")
        site = Path(
            run(
                [
                    python,
                    "-I",
                    "-c",
                    "import sysconfig; print(sysconfig.get_path('purelib'))",
                ],
                cwd,
                env,
            )
        )
        (site / "sitecustomize.py").write_text(NETWORK_GUARD)
        run(
            [
                python,
                "-I",
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-compile",
                "--find-links",
                str(WHEELHOUSE),
                str(wheel),
            ],
            cwd,
            env,
        )
        pip_check = run([python, "-I", "-m", "pip", "check"], cwd, env)
        inputs, output, script = (
            cwd / "probes.json",
            cwd / "result.json",
            cwd / "consumer.py",
        )
        inputs.write_text(json.dumps(probes))
        script.write_text(CONSUMER)
        run(
            [
                python,
                "-I",
                str(script),
                module_name,
                str(inputs),
                str(output),
                str(ROOT),
            ],
            cwd,
            env,
        )
        evidence = json.loads(output.read_text())
        assert _equal(expected, evidence.pop("results"))
        evidence.update(
            pip_check=pip_check,
            python=sys.version,
            module=module_name,
            wheel=wheel.name,
            outside_checkout=True,
            parity="passed",
        )
        report = (
            ROOT
            / ".mlforge-build"
            / f"consumer-{sys.version_info.minor}-{bundle.model_id}.json"
        )
        report.write_text(json.dumps(evidence, indent=2) + "\n")
