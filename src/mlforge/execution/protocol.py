"""Strict wire records and owned-file integrity; no domain services or processes."""

import hashlib
import json
import math
import os
import re
import stat
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from mlforge.contracts import DomainError

VERSION = 1
MAX_EVENT = 16 * 1024
MAX_MESSAGE = 64 * 1024
MAX_FILE = 512 * 1024 * 1024
MAX_STDERR = 64 * 1024


class Operation(StrEnum):
    PARSE = "parse"
    INSPECT = "inspect"
    REVIEW = "review"
    PREFLIGHT = "preflight"
    PREPARE = "prepare"
    TRAIN = "train"
    PREDICT = "predict"
    EXPORT = "export"


OUTPUTS = {
    Operation.PARSE: ("dataset.json", "schema.json"),
    Operation.INSPECT: ("schema.json",),
    Operation.REVIEW: ("review.json",),
    Operation.PREFLIGHT: ("prepared.json",),
    Operation.PREPARE: ("prepared.json",),
    Operation.TRAIN: ("candidate.json", "schema.json", "metadata.json", "model.skops"),
    Operation.PREDICT: ("predictions.json",),
    Operation.EXPORT: ("export.json",),
}


def output_names(identity):
    return tuple(
        f"{identity.operation_id}/{name}" for name in OUTPUTS[identity.operation]
    )


class EventKind(StrEnum):
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"


PHASES = frozenset(
    {
        "parsing",
        "inspecting",
        "preparing",
        "preprocessing",
        "training",
        "evaluating",
        "validating_artifact",
        "predicting",
        "exporting",
    }
)

OPERATION_PHASES = {
    Operation.PARSE: {"parsing"},
    Operation.INSPECT: {"inspecting"},
    Operation.REVIEW: {"inspecting"},
    Operation.PREFLIGHT: {"preparing"},
    Operation.PREPARE: {"preparing"},
    Operation.TRAIN: {"preprocessing", "training", "evaluating", "validating_artifact"},
    Operation.PREDICT: {"predicting"},
    Operation.EXPORT: {"exporting", "validating_artifact"},
}


class ProtocolError(DomainError):
    def __init__(self):
        super().__init__(
            "PROTOCOL",
            "The operation returned invalid or incomplete data.",
            "Retry the operation; the incomplete result was not accepted.",
        )


def _require(condition):
    if not condition:
        raise ProtocolError()


def _integer(value, maximum=2**53 - 1):
    return type(value) is int and 0 <= value <= maximum


def _match(value, pattern):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def _name(value):
    # Owned names only: never absolute paths, dot segments or user-selected paths.
    return _match(value, r"[a-z0-9][a-z0-9_.-]{0,79}(?:/[a-z0-9][a-z0-9_.-]{0,79})?")


def _tree(value, depth=0):
    _require(depth <= 12)
    if type(value) is dict:
        _require(all(type(k) is str for k in value))
        for key, child in value.items():
            _tree(key, depth + 1)
            _tree(child, depth + 1)
    elif type(value) is list:
        for child in value:
            _tree(child, depth + 1)
    else:
        _require(value is None or type(value) in (str, bool, int, float))
        if type(value) is float:
            _require(math.isfinite(value))
        if type(value) is int:
            _require(abs(value) <= 2**53 - 1)
        if type(value) is str:
            try:
                value.encode("utf-8", errors="strict")
            except UnicodeError:
                raise ProtocolError() from None


def json_data(value, limit=MAX_MESSAGE):
    _tree(value)
    try:
        data = (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
    except (ValueError, TypeError, RecursionError):
        raise ProtocolError() from None
    _require(len(data) <= limit)
    return data


def parse_json(data, limit=MAX_MESSAGE):
    _require(type(data) is bytes and 0 < len(data) <= limit)

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result)
            result[key] = value
        return result

    def invalid(value):
        raise ProtocolError()

    try:
        value = json.loads(
            data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid
        )
        _tree(value)
        return value
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise ProtocolError() from None


@dataclass(frozen=True)
class Identity:
    run_id: str
    revision: int
    operation_id: str
    operation: Operation
    model_id: str | None = None

    def __post_init__(self):
        _require(_match(self.run_id, r"[0-9a-f]{32}"))
        _require(_match(self.operation_id, r"[0-9a-f]{32}"))
        _require(_integer(self.revision) and type(self.operation) is Operation)
        _require(self.model_id is None or _match(self.model_id, r"[a-z]+\.[a-z]+"))
        _require(self.operation != Operation.TRAIN or self.model_id is not None)


@dataclass(frozen=True)
class Artifact:
    name: str
    size: int
    sha256: str

    def __post_init__(self):
        _require(_name(self.name) and _integer(self.size, MAX_FILE))
        _require(_match(self.sha256, r"[0-9a-f]{64}"))


def _artifacts(values):
    copied = tuple(values)
    _require(len(copied) <= 8 and all(type(v) is Artifact for v in copied))
    _require(len({v.name for v in copied}) == len(copied))
    return copied


@dataclass(frozen=True)
class Request:
    identity: Identity
    inputs: tuple[Artifact, ...]
    outputs: tuple[str, ...]
    options_json: str = "{}"

    def __post_init__(self):
        _require(type(self.identity) is Identity)
        object.__setattr__(self, "inputs", _artifacts(self.inputs))
        outputs = tuple(self.outputs)
        _require(0 < len(outputs) <= 8 and all(_name(n) for n in outputs))
        _require(len(set(outputs)) == len(outputs))
        _require(not {a.name for a in self.inputs} & set(outputs))
        _require(
            not {"request.json", "result.json"}
            & (set(outputs) | {a.name for a in self.inputs})
        )
        object.__setattr__(self, "outputs", outputs)
        _require(type(self.options_json) is str)
        try:
            options = parse_json(self.options_json.encode())
        except UnicodeError:
            raise ProtocolError() from None
        _require(type(options) is dict)
        object.__setattr__(self, "options_json", json_data(options).decode())


@dataclass(frozen=True)
class Result:
    identity: Identity
    artifacts: tuple[Artifact, ...]

    def __post_init__(self):
        _require(type(self.identity) is Identity)
        object.__setattr__(self, "artifacts", _artifacts(self.artifacts))
        _require(bool(self.artifacts))


@dataclass(frozen=True)
class RunEvent:
    identity: Identity
    sequence: int
    kind: EventKind
    phase: str | None = None
    error_code: str | None = None

    def __post_init__(self):
        _require(type(self.identity) is Identity and _integer(self.sequence))
        _require(type(self.kind) is EventKind)
        _require((self.kind == EventKind.PROGRESS) == (self.phase is not None))
        _require(self.phase is None or self.phase in PHASES)
        _require(
            self.phase is None
            or self.phase in OPERATION_PHASES[self.identity.operation]
        )
        _require((self.kind == EventKind.FAILED) == (self.error_code is not None))
        _require(
            self.error_code is None or _match(self.error_code, r"[A-Z][A-Z0-9_]{0,63}")
        )


def encode(message):
    _require(type(message) in (Request, Result, RunEvent))
    value = asdict(message)
    # StrEnum is an intentional protocol scalar; no arbitrary object coercion.
    value["identity"]["operation"] = message.identity.operation.value
    if isinstance(message, RunEvent):
        value["kind"] = message.kind.value
    for name in ("inputs", "outputs", "artifacts"):
        if name in value:
            value[name] = list(value[name])
    value.update(protocol_version=VERSION, message_type=type(message).__name__)
    return json_data(value, MAX_EVENT if isinstance(message, RunEvent) else MAX_MESSAGE)


def decode(data, expected_type):
    _require(expected_type in (Request, Result, RunEvent))
    limit = MAX_EVENT if expected_type is RunEvent else MAX_MESSAGE
    if expected_type is RunEvent:
        _require(
            type(data) is bytes and data.endswith(b"\n") and b"\n" not in data[:-1]
        )
    value = parse_json(data, limit)
    _require(
        type(value) is dict
        and value.pop("message_type", None) == expected_type.__name__
    )
    version = value.pop("protocol_version", None)
    _require(type(version) is int and version == VERSION)
    try:
        identity = value.pop("identity")
        identity["operation"] = Operation(identity["operation"])
        value["identity"] = Identity(**identity)
        if expected_type is Request:
            _require(type(value["inputs"]) is list and type(value["outputs"]) is list)
            value["inputs"] = tuple(Artifact(**a) for a in value["inputs"])
        elif expected_type is Result:
            _require(type(value["artifacts"]) is list)
            value["artifacts"] = tuple(Artifact(**a) for a in value["artifacts"])
        else:
            value["kind"] = EventKind(value["kind"])
        return expected_type(**value)
    except (KeyError, TypeError, ValueError):
        raise ProtocolError() from None


class EventStream:
    """Per-operation monotonic stream; completion remains provisional until exit."""

    def __init__(self, identity):
        self.identity = identity
        self.sequence = -1
        self.terminal = False

    def accept(self, data):
        event = decode(data, RunEvent)
        _require(event.identity == self.identity and not self.terminal)
        _require(event.sequence == self.sequence + 1)
        _require((event.kind == EventKind.STARTED) == (event.sequence == 0))
        self.sequence = event.sequence
        self.terminal = event.kind in (EventKind.COMPLETED, EventKind.FAILED)
        return event


def _private(info, *, directory=False):
    _require(info.st_uid == os.getuid())
    _require(stat.S_IMODE(info.st_mode) == (0o700 if directory else 0o600))
    _require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
    if not directory:
        _require(info.st_nlink == 1)


@contextmanager
def _parent(root, name):
    _require(_name(name))
    descriptors = []
    try:
        descriptor = os.open(Path(root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(descriptor)
        _private(os.fstat(descriptor), directory=True)
        parts = name.split("/")
        if len(parts) == 2:
            descriptor = os.open(
                parts[0],
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
            descriptors.append(descriptor)
            _private(os.fstat(descriptor), directory=True)
        yield descriptor, parts[-1]
    except OSError:
        raise ProtocolError() from None
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def read_owned(root, name, limit=MAX_FILE):
    """Read a bounded regular owner-only file without following links or FIFOs."""
    _require(_integer(limit, MAX_FILE))
    with _parent(root, name) as (parent, basename):
        descriptor = os.open(
            basename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
        )
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            _private(before)
            _require(before.st_size <= limit)
            data = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
            _require(len(data) <= limit and len(data) == before.st_size)
            _require(
                (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            )
            return data


def write_owned(root, name, data):
    """Publish one new private output atomically, without replacing any file."""
    _require(type(data) is bytes and len(data) <= MAX_FILE)
    with _parent(root, name) as (parent, basename):
        temporary = "tmp-" + uuid.uuid4().hex
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(
                temporary,
                basename,
                src_dir_fd=parent,
                dst_dir_fd=parent,
                follow_symlinks=False,
            )
            os.unlink(temporary, dir_fd=parent)
            temporary = None
            os.fsync(parent)
        finally:
            if temporary is not None:
                os.unlink(temporary, dir_fd=parent)
    return Artifact(name, len(data), hashlib.sha256(data).hexdigest())


def verify_artifact(root, artifact):
    _require(type(artifact) is Artifact)
    data = read_owned(root, artifact.name, artifact.size)
    _require(
        len(data) == artifact.size
        and hashlib.sha256(data).hexdigest() == artifact.sha256
    )
    return data


def validate_result(request, result, root, *, returncode, completed, cancelled):
    """Parent acceptance barrier: cancellation wins over provisional completion."""
    _require(type(request) is Request and type(result) is Result)
    _require(
        type(returncode) is int
        and returncode == 0
        and completed is True
        and cancelled is False
    )
    _require(result.identity == request.identity)
    _require({a.name for a in result.artifacts} == set(request.outputs))
    for artifact in result.artifacts:
        verify_artifact(root, artifact)
    return result
