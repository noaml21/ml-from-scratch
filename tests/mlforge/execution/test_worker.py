"""Real worker children, strict service data and private resource ownership."""

import json
import os
import subprocess
import sys
import uuid
from dataclasses import replace

import pytest

from mlforge.contracts import candidate_from_data, experiment_data, prepared_from_data
from mlforge.datasets.records import dataset_from_data, schema_from_data
from mlforge.execution.protocol import (
    MAX_FILE,
    EventKind,
    EventStream,
    Identity,
    Operation,
    Request,
    Result,
    decode,
    encode,
    json_data,
    parse_json,
    read_owned,
    validate_result,
    verify_artifact,
    write_owned,
)
from mlforge.execution.worker import output_names


@pytest.fixture(autouse=True)
def inherited_network_guard(tmp_path, monkeypatch):
    guard = tmp_path / "network-guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text("""import os, sys
os.environ["MLFORGE_TEST_GUARD"] = "active"
def guard(event, args):
    if event in {"socket.connect", "socket.connect_ex",
                 "socket.getaddrinfo", "socket.sendto"}:
        os._exit(93)
sys.addaudithook(guard)
""")
    monkeypatch.setenv("PYTHONPATH", str(guard))


@pytest.fixture
def root(tmp_path):
    path = tmp_path / "private"
    path.mkdir(mode=0o700)
    return path


def request(root, operation, inputs=(), options=None, model=None):
    identity = Identity("a" * 32, 7, uuid.uuid4().hex, operation, model)
    return Request(identity, inputs, output_names(identity), json.dumps(options or {}))


def run(root, req, *, env=None):
    write_owned(root, f"request-{req.identity.operation_id}.json", encode(req))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mlforge.execution.worker",
            str(root),
            req.identity.operation_id,
        ],
        capture_output=True,
        timeout=45,
        env=env,
    )
    stream = EventStream(req.identity)
    events = [stream.accept(line) for line in result.stdout.splitlines(keepends=True)]
    assert result.stderr == b""
    assert events and stream.terminal
    manifest = decode(
        read_owned(root, f"result-{req.identity.operation_id}.json"), Result
    )
    if result.returncode == 0:
        assert events[-1].kind == EventKind.COMPLETED
        validate_result(
            req, manifest, root, returncode=0, completed=True, cancelled=False
        )
    else:
        assert events[-1].kind == EventKind.FAILED
        assert manifest.artifacts[0].name == f"error-{req.identity.operation_id}.json"
        verify_artifact(root, manifest.artifacts[0])
    return result, events, manifest


def data(root, artifact):
    return parse_json(verify_artifact(root, artifact), MAX_FILE)


def test_parse_inspect_and_invalid_override_preserve_source(root, tmp_path):
    source = tmp_path / "space שלום.csv"
    contents = b"zip,amount\n001,2\n002,3\n"
    source.write_bytes(contents)
    result, events, parsed = run(
        root, request(root, Operation.PARSE, options={"path": str(source)})
    )
    assert result.returncode == 0
    assert [e.phase for e in events if e.kind == EventKind.PROGRESS] == ["parsing"]
    dataset = dataset_from_data(data(root, parsed.artifacts[0]))
    schema = schema_from_data(data(root, parsed.artifacts[1]))
    assert (
        dataset.rows[0][0].raw_text == "001"
        and schema.columns[0].effective.value == "Category"
    )
    inspected = request(
        root, Operation.INSPECT, parsed.artifacts, {"column_id": "c0", "kind": "Number"}
    )
    result, _, changed = run(root, inspected)
    assert result.returncode == 0
    new = schema_from_data(data(root, changed.artifacts[0]))
    assert new.revision == 1 and new.columns[0].effective.value == "Number"
    reset = request(
        root,
        Operation.INSPECT,
        (parsed.artifacts[0], changed.artifacts[0]),
        {"column_id": "c0", "kind": None},
    )
    result, _, restored = run(root, reset)
    assert (
        schema_from_data(data(root, restored.artifacts[0])).columns[0].effective.value
        == "Category"
    )
    result, _, failure = run(
        root,
        request(
            root,
            Operation.INSPECT,
            parsed.artifacts,
            {"column_id": "c0", "kind": "Boolean"},
        ),
    )
    assert (
        result.returncode == 1
        and data(root, failure.artifacts[0])["code"] == "TYPE_VALUES"
    )
    assert source.read_bytes() == contents


def test_six_models_real_worker_prepare_train_predict(prepared_candidate, root):
    from mlforge.datasets.records import dataset_data, schema_data
    from mlforge.preprocessing import raw_records

    dataset, prepared, model = prepared_candidate
    d = write_owned(root, "data.json", json_data(dataset_data(dataset), MAX_FILE))
    s = write_owned(root, "schema.json", json_data(schema_data(prepared.schema)))
    spec = write_owned(
        root, "experiment.json", json_data(experiment_data(prepared.experiment))
    )
    result, _, plan = run(root, request(root, Operation.PREPARE, (d, s, spec)))
    assert result.returncode == 0
    restored = prepared_from_data(data(root, plan.artifacts[0]))
    assert restored == prepared
    result, events, trained = run(
        root, request(root, Operation.TRAIN, (d, plan.artifacts[0]), model=model.id)
    )
    assert result.returncode == 0
    assert [e.phase for e in events if e.kind == EventKind.PROGRESS] == [
        "preprocessing",
        "training",
        "evaluating",
        "validating_artifact",
    ]
    candidate = candidate_from_data(
        data(root, trained.artifacts[0]), str(root / trained.identity.operation_id)
    )
    assert candidate.bundle.model_id == model.id
    assert str(root) not in json.dumps(data(root, trained.artifacts[0]))
    records = raw_records(dataset, prepared.experiment.feature_ids, (0, 1))
    probes = write_owned(root, "probes.json", json_data(records))
    result, _, predictions = run(
        root,
        request(root, Operation.PREDICT, (*trained.artifacts, probes), model=model.id),
    )
    assert result.returncode == 0 and len(data(root, predictions.artifacts[0])) == 2
    from mlforge.prediction.runtime import Predictor

    predictor = Predictor._from_directory(candidate.bundle.directory)
    operation = (
        predictor.transform_many
        if model.task.value == "reduction"
        else predictor.predict_many
    )
    assert data(root, predictions.artifacts[0]) == operation(records)
    # Actual worker export for one model; all runtime contracts are unchanged.
    if model.id == "classification.logistic":
        result, _, exported = run(
            root,
            request(
                root,
                Operation.EXPORT,
                (*trained.artifacts, probes),
                {
                    "destination": str(root.parent / "exports"),
                    "module_name": "worker_model",
                    "version": "1.0.0",
                },
                model.id,
            ),
        )
        assert result.returncode == 0
        assert (
            root.parent / "exports" / data(root, exported.artifacts[0])["name"]
        ).is_file()


def test_malformed_request_has_no_output_or_private_log(root):
    operation_id = uuid.uuid4().hex
    write_owned(
        root, f"request-{operation_id}.json", b'{"private":"secret fixture",broken}'
    )
    result = subprocess.run(
        [sys.executable, "-m", "mlforge.execution.worker", str(root), operation_id],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 2 and result.stdout == result.stderr == b""
    assert len(list(root.iterdir())) == 1


def test_parent_assignment_symlink_and_existing_outputs(root, tmp_path):
    source = tmp_path / "valid.csv"
    source.write_text("x,y\n1,2\n")
    req = request(root, Operation.PARSE, options={"path": str(source)})
    req = replace(req, outputs=("unrelated.json", "schema.json"))
    result, _, _ = run(root, req)
    assert result.returncode == 2 and not (root / "unrelated.json").exists()
    for symlink in (False, True):
        req = request(root, Operation.PARSE, options={"path": str(source)})
        sentinel = tmp_path / ("sentinel-link" if symlink else "sentinel-dir")
        sentinel.mkdir()
        (sentinel / "keep").write_text("unrelated")
        owned = root / req.identity.operation_id
        if symlink:
            owned.symlink_to(sentinel, target_is_directory=True)
        else:
            owned.mkdir(mode=0o700)
            (owned / "keep").write_text("existing")
        result, _, _ = run(root, req)
        assert result.returncode != 0
        assert list(sentinel.iterdir()) == [sentinel / "keep"]
        assert not (owned / "dataset.json").exists()


def test_invalid_service_data_cannot_succeed(root):
    d = write_owned(
        root, "data.json", json_data({"rows": [], "private": "must not escape"})
    )
    s = write_owned(root, "schema.json", b"{}")
    result, _, failure = run(
        root,
        request(root, Operation.INSPECT, (d, s), {"column_id": "c0", "kind": "Number"}),
    )
    assert result.returncode == 2
    assert "must not escape" not in json.dumps(data(root, failure.artifacts[0]))


def test_worker_runs_without_network_and_import_has_no_work(root, tmp_path):
    guard = tmp_path / "guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text("""import os, sys
from pathlib import Path
Path(os.environ["GUARD_MARKER"]).write_text("active")
def guard(event, args):
    if event in {"socket.connect", "socket.connect_ex",
                 "socket.getaddrinfo", "socket.sendto"}:
        os._exit(93)
sys.addaudithook(guard)
""")
    source = tmp_path / "data.csv"
    source.write_text("x,y\n1,2\n")
    marker = tmp_path / "guard-marker"
    env = dict(os.environ, PYTHONPATH=str(guard), GUARD_MARKER=str(marker))
    result, _, _ = run(
        root, request(root, Operation.PARSE, options={"path": str(source)}), env=env
    )
    assert marker.read_text() == "active" and result.returncode == 0
    result = subprocess.run(
        [sys.executable, "-c", "import mlforge.execution.worker"],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0 and result.stdout == result.stderr == b""


@pytest.mark.parametrize(
    "failure",
    [RuntimeError("private details"), OSError("private path"), ValueError("bad")],
)
def test_service_exceptions_are_safe(root, monkeypatch, failure):
    from mlforge.execution import worker

    req = request(root, Operation.PARSE, options={"path": "/unused"})
    write_owned(root, f"request-{req.identity.operation_id}.json", encode(req))
    events = []

    def broken(*args):
        raise failure

    monkeypatch.setitem(worker.DISPATCH, Operation.PARSE, broken)
    # execute is a child entrypoint and pins cwd; restore the test process only.
    cwd = os.getcwd()
    try:
        code = worker.execute(root, req.identity.operation_id, events.append)
    finally:
        os.chdir(cwd)
    assert code == (2 if type(failure) is ValueError else 1)
    stream = EventStream(req.identity)
    decoded = [stream.accept(line) for line in events]
    assert decoded[-1].kind == EventKind.FAILED
    assert b"private" not in b"".join(events)


@pytest.mark.parametrize("invalid", ["event", "result"])
def test_invalid_service_output_cannot_complete(root, monkeypatch, invalid):
    from mlforge.execution import worker

    req = request(root, Operation.PARSE, options={"path": "/unused"})
    write_owned(root, f"request-{req.identity.operation_id}.json", encode(req))

    def broken(root, req, options, progress):
        if invalid == "event":
            progress("arbitrary private data")
        return [object()]

    monkeypatch.setitem(worker.DISPATCH, Operation.PARSE, broken)
    events, cwd = [], os.getcwd()
    try:
        code = worker.execute(root, req.identity.operation_id, events.append)
    finally:
        os.chdir(cwd)
    assert code != 0
    stream = EventStream(req.identity)
    assert all(stream.accept(e).kind != EventKind.COMPLETED for e in events)


def test_oversized_input_refused_before_reading(root):
    from mlforge.execution.protocol import Artifact

    path = root / "oversized.json"
    with path.open("wb") as stream:
        stream.truncate(MAX_FILE + 1)
    path.chmod(0o600)
    ref = Artifact(path.name, MAX_FILE, "0" * 64)
    other = write_owned(root, "schema.json", b"{}")
    result, _, _ = run(
        root,
        request(
            root, Operation.INSPECT, (ref, other), {"column_id": "c0", "kind": None}
        ),
    )
    assert result.returncode == 2


@pytest.mark.parametrize(
    "payload",
    [
        b'{"identity":{"operation":"eval arbitrary"}}',
        b"x" * (65536 + 1),
    ],
)
def test_unsupported_or_oversized_request_is_silent(root, payload):
    operation_id = uuid.uuid4().hex
    write_owned(root, f"request-{operation_id}.json", payload)
    child = subprocess.run(
        [sys.executable, "-m", "mlforge.execution.worker", str(root), operation_id],
        capture_output=True,
        timeout=10,
    )
    assert child.returncode == 2 and child.stdout == child.stderr == b""
