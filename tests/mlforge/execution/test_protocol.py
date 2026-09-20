"""Adversarial wire and ownership checks without launching domain services."""

import hashlib
import json
import os
from dataclasses import FrozenInstanceError, replace

import pytest

from mlforge.execution.protocol import (
    MAX_EVENT,
    Artifact,
    EventKind,
    EventStream,
    Identity,
    Operation,
    ProtocolError,
    Request,
    Result,
    RunEvent,
    decode,
    encode,
    json_data,
    parse_json,
    read_owned,
    validate_result,
    verify_artifact,
    write_owned,
)


@pytest.fixture
def identity():
    return Identity("a" * 32, 1, "b" * 32, Operation.PARSE)


@pytest.fixture
def root(tmp_path):
    tmp_path.chmod(0o700)
    return tmp_path


@pytest.mark.parametrize("operation", list(Operation))
def test_envelopes_roundtrip_and_immutable(identity, operation):
    identity = replace(
        identity,
        operation=operation,
        model_id="classification.logistic" if operation == Operation.TRAIN else None,
    )
    artifact = Artifact("data.json", 2, hashlib.sha256(b"{}").hexdigest())
    for message in (
        Request(identity, [artifact], ["output.json"], '{"path":"a b/שלום.csv"}'),
        Result(identity, [artifact]),
        RunEvent(identity, 0, EventKind.STARTED),
        RunEvent(identity, 1, EventKind.FAILED, error_code="DATA_LIMIT"),
    ):
        assert decode(encode(message), type(message)) == message
        with pytest.raises(FrozenInstanceError):
            message.identity = None
    output = ["output.json"]
    request = Request(identity, (), output)
    output.clear()
    assert request.outputs == ("output.json",)


@pytest.mark.parametrize(
    "data",
    [
        b'{"a":1,"a":2}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1e999}',
        b'{"x":9007199254740992}',
        b'{"x":"\\ud800"}',
        b"\xff",
        b"{",
        b"{}{}",
        b"[" * 2000,
    ],
)
def test_json_rejects_ambiguous_nonfinite_invalid_or_deep_data(data):
    with pytest.raises(ProtocolError) as error:
        parse_json(data)
    assert error.value.code == "PROTOCOL" and data.decode(errors="replace") not in str(
        error.value
    )


@pytest.mark.parametrize(
    "value",
    [{1: "key"}, {"x": float("nan")}, {"x": object()}, {"x": (1, 2)}, {"x": 2**53}],
)
def test_encoder_never_coerces_objects_or_invalid_json(value):
    with pytest.raises(ProtocolError):
        json_data(value)


@pytest.mark.parametrize(
    "change",
    [
        {"protocol_version": True},
        {"protocol_version": 2},
        {"unexpected": 1},
        {"message_type": "Result"},
        {"identity": None},
        {"kind": "made_up"},
        {"sequence": True},
        {"sequence": -1},
        {"phase": "private row value"},
    ],
)
def test_invalid_event_fields_fail_safely(identity, change):
    data = json.loads(encode(RunEvent(identity, 0, EventKind.STARTED)))
    data.update(change)
    with pytest.raises(ProtocolError):
        decode(json_data(data), RunEvent)


def test_event_framing_and_utf8_byte_limit(identity):
    event = encode(RunEvent(identity, 0, EventKind.STARTED))
    for data in (event[:-1], event + event, b"\n" + event, b" " * MAX_EVENT + event):
        with pytest.raises(ProtocolError):
            decode(data, RunEvent)
    assert len(json_data("א" * 10, limit=23)) == 23
    with pytest.raises(ProtocolError):
        json_data("א" * 10, limit=22)


def test_sequence_revision_duplicates_and_terminal_events(identity):
    stream = EventStream(identity)
    started = encode(RunEvent(identity, 0, EventKind.STARTED))
    stream.accept(started)
    for event in (
        RunEvent(identity, 0, EventKind.STARTED),
        RunEvent(identity, 2, EventKind.PROGRESS, phase="parsing"),
        RunEvent(replace(identity, revision=2), 1, EventKind.COMPLETED),
        RunEvent(replace(identity, operation_id="c" * 32), 1, EventKind.COMPLETED),
    ):
        with pytest.raises(ProtocolError):
            stream.accept(encode(event))
    assert stream.sequence == 0  # rejected events cannot advance the stream
    stream.accept(encode(RunEvent(identity, 1, EventKind.PROGRESS, phase="parsing")))
    stream.accept(encode(RunEvent(identity, 2, EventKind.COMPLETED)))
    with pytest.raises(ProtocolError):
        stream.accept(encode(RunEvent(identity, 3, EventKind.COMPLETED)))
    with pytest.raises(ProtocolError):
        EventStream(identity).accept(encode(RunEvent(identity, 0, EventKind.COMPLETED)))


@pytest.mark.parametrize(
    "name",
    [
        "../elsewhere",
        "/absolute",
        "a/../b",
        "a/b/c",
        "a\\b",
        ".",
        "..",
        "a/.",
        "a/..",
        "~/.env",
        "bad\x00name",
    ],
)
def test_names_cannot_escape_owned_root(name):
    with pytest.raises(ProtocolError):
        Artifact(name, 0, "0" * 64)


def test_private_atomic_publication_no_overwrite_and_integrity(root, identity):
    artifact = write_owned(root, "output.json", b'{"ok":true}')
    assert (root / "output.json").stat().st_mode & 0o777 == 0o600
    assert verify_artifact(root, artifact) == b'{"ok":true}'
    with pytest.raises(ProtocolError):
        write_owned(root, "output.json", b"replace")
    assert sorted(p.name for p in root.iterdir()) == ["output.json"]
    assert verify_artifact(root, artifact) == b'{"ok":true}'
    request = Request(identity, (), ("output.json",))
    result = Result(identity, (artifact,))
    assert (
        validate_result(
            request, result, root, returncode=0, completed=True, cancelled=False
        )
        == result
    )
    for kwargs in (
        {"returncode": 1, "completed": True, "cancelled": False},
        {"returncode": 0, "completed": False, "cancelled": False},
        {"returncode": 0, "completed": True, "cancelled": True},
    ):
        with pytest.raises(ProtocolError):
            validate_result(request, result, root, **kwargs)
    (root / "output.json").write_bytes(b"corruption")
    with pytest.raises(ProtocolError):
        verify_artifact(root, artifact)


def test_unassigned_outputs_or_identity_are_never_accepted(root, identity):
    artifact = write_owned(root, "other.json", b"{}")
    request = Request(identity, (), ("output.json",))
    for result in (
        Result(identity, (artifact,)),
        Result(replace(identity, revision=2), (artifact,)),
    ):
        with pytest.raises(ProtocolError):
            validate_result(
                request, result, root, returncode=0, completed=True, cancelled=False
            )
    for outputs in (("request.json",), ("result.json",), ("same", "same")):
        with pytest.raises(ProtocolError):
            Request(identity, (), outputs)
    with pytest.raises(ProtocolError):
        Request(identity, (artifact,), ("other.json",))


def test_symlinks_hardlinks_fifo_and_permissions_refused(root, tmp_path_factory):
    elsewhere = tmp_path_factory.mktemp("sentinel")
    target = elsewhere / "sentinel"
    target.write_bytes(b"unrelated")
    target.chmod(0o600)
    (root / "link").symlink_to(target)
    os.link(target, root / "hardlink")
    os.mkfifo(root / "fifo", 0o600)
    (root / "folder").symlink_to(elsewhere, target_is_directory=True)
    for name in ("link", "hardlink", "fifo", "folder/sentinel"):
        with pytest.raises(ProtocolError):
            read_owned(root, name, 100)
    with pytest.raises(ProtocolError):
        write_owned(root, "folder/new", b"unsafe")
    assert target.read_bytes() == b"unrelated" and not (elsewhere / "new").exists()
    artifact = write_owned(root, "private", b"safe")
    (root / "private").chmod(0o644)
    with pytest.raises(ProtocolError):
        verify_artifact(root, artifact)
    root.chmod(0o755)
    with pytest.raises(ProtocolError):
        read_owned(root, "private")


def test_read_limit_and_atomic_disk_failure(root, monkeypatch):
    write_owned(root, "bounded", b"12345")
    with pytest.raises(ProtocolError):
        read_owned(root, "bounded", 4)

    def no_space(*args, **kwargs):
        raise OSError("simulated disk full")

    monkeypatch.setattr(os, "fsync", no_space)
    with pytest.raises(ProtocolError):
        write_owned(root, "failed", b"123")
    assert sorted(p.name for p in root.iterdir()) == ["bounded"]


def test_missing_and_duplicate_artifact_fields_refused(identity):
    request = json.loads(encode(Request(identity, (), ("output.json",))))
    request["inputs"] = [{"name": "input", "size": 0, "sha256": "0" * 64, "extra": 1}]
    with pytest.raises(ProtocolError):
        decode(json_data(request), Request)
    artifact = Artifact("input", 0, "0" * 64)
    with pytest.raises(ProtocolError):
        Result(identity, (artifact, artifact))


def test_phase_and_request_limits(identity):
    with pytest.raises(ProtocolError):
        RunEvent(identity, 1, EventKind.PROGRESS, phase="training")
    for options in ("[]", '{"x":"' + "x" * 65536 + '"}'):
        with pytest.raises(ProtocolError):
            Request(identity, (), ("output",), options)
    with pytest.raises(ProtocolError):
        Request(identity, (), tuple(f"out-{i}" for i in range(9)))
    with pytest.raises(ProtocolError):
        Artifact("input", True, "0" * 64)
    with pytest.raises(ProtocolError):
        Artifact("input", 0, "not-a-sha")
