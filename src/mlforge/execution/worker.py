"""Headless operation dispatcher; coordinator owns lifetime and acceptance."""

import hashlib
import os
import re
import sys
from pathlib import Path

from mlforge.contracts import (
    DomainError,
    candidate_data,
    candidate_from_data,
    experiment_from_data,
    prepared_data,
    prepared_from_data,
)
from mlforge.datasets.records import (
    ColumnType,
    dataset_data,
    dataset_from_data,
    schema_data,
    schema_from_data,
)
from mlforge.execution.protocol import (
    MAX_FILE,
    MAX_MESSAGE,
    Artifact,
    EventKind,
    Operation,
    ProtocolError,
    Request,
    Result,
    RunEvent,
    decode,
    encode,
    json_data,
    output_names,
    parse_json,
    read_owned,
    verify_artifact,
    write_owned,
)

INPUT_COUNTS = {
    Operation.PARSE: 0,
    Operation.INSPECT: 2,
    Operation.REVIEW: 2,
    Operation.PREFLIGHT: 3,
    Operation.PREPARE: 3,
    Operation.TRAIN: 2,
    Operation.PREDICT: 5,
    Operation.EXPORT: 5,
}
OPTION_KEYS = {
    Operation.PARSE: {"path"},
    Operation.INSPECT: {"column_id", "kind"},
    Operation.REVIEW: {
        "task",
        "target_id",
        "feature_ids",
        "model_ids",
        "option",
        "initialized",
    },
    Operation.PREFLIGHT: set(),
    Operation.PREPARE: set(),
    Operation.TRAIN: set(),
    Operation.PREDICT: set(),
    Operation.EXPORT: {
        "module_name",
        "version",
        "publication_directory",
    },
}


def _check(condition):
    if not condition:
        raise ProtocolError()


def _json_input(root, artifact):
    return parse_json(verify_artifact(root, artifact), MAX_FILE)


def _save(root, name, value):
    return write_owned(root, name, json_data(value, MAX_FILE))


def _dataset_schema(root, request):
    dataset = dataset_from_data(_json_input(root, request.inputs[0]))
    schema = schema_from_data(_json_input(root, request.inputs[1]))
    _check(
        tuple(c.id for c in dataset.columns)
        == tuple(c.column_id for c in schema.columns)
    )
    _check(
        all(
            p.missing_count + p.distinct_count <= len(dataset.rows)
            for p in schema.columns
        )
    )
    return dataset, schema


def _parse(root, request, options, progress):
    from mlforge.datasets.importers import load_dataset
    from mlforge.datasets.inference import infer_schema

    progress("parsing")
    _check(type(options["path"]) is str and 0 < len(options["path"]) <= 4096)
    _check(Path(options["path"]).is_absolute())
    dataset = load_dataset(options["path"])
    return [
        _save(root, request.outputs[0], dataset_data(dataset)),
        _save(root, request.outputs[1], schema_data(infer_schema(dataset))),
    ]


def _inspect(root, request, options, progress):
    from mlforge.datasets.validation import change_type

    progress("inspecting")
    dataset, schema = _dataset_schema(root, request)
    _check(type(options["column_id"]) is str)
    kind = ColumnType(options["kind"]) if options["kind"] is not None else None
    schema = change_type(dataset, schema, options["column_id"], kind)
    return [_save(root, request.outputs[0], schema_data(schema))]


def _prepare(root, request, options, progress):
    from mlforge.preprocessing import prepare_run

    progress("preparing")
    dataset, schema = _dataset_schema(root, request)
    spec = experiment_from_data(_json_input(root, request.inputs[2]))
    prepared = prepare_run(dataset, schema, spec)
    return [_save(root, request.outputs[0], prepared_data(prepared))]


def _review(root, request, options, progress):
    from mlforge.tasks import configuration_review, review_data

    progress("inspecting")
    dataset, schema = _dataset_schema(root, request)
    return [
        _save(
            root,
            request.outputs[0],
            review_data(configuration_review(dataset, schema, options)),
        )
    ]


def _train(root, request, options, progress):
    from mlforge.training import train_candidate

    dataset = dataset_from_data(_json_input(root, request.inputs[0]))
    prepared = prepared_from_data(_json_input(root, request.inputs[1]))
    _check(len(prepared.train_rows) + len(prepared.test_rows) == len(dataset.rows))
    _check(prepared.experiment.task.supervised == bool(prepared.test_rows))
    candidate = train_candidate(
        dataset,
        prepared,
        request.identity.model_id,
        root / request.identity.operation_id,
        progress,
    )
    artifacts = [_save(root, request.outputs[0], candidate_data(candidate))]
    for name in request.outputs[1:]:
        data = read_owned(root, name)
        artifacts.append(Artifact(name, len(data), hashlib.sha256(data).hexdigest()))
    return artifacts


def _bundle_inputs(root, request):
    candidate, schema, metadata, model, probes = request.inputs
    names = [a.name.split("/") for a in (candidate, schema, metadata, model)]
    _check(all(len(n) == 2 for n in names))
    _check(len({n[0] for n in names}) == 1)
    _check(
        [n[1] for n in names]
        == ["candidate.json", "schema.json", "metadata.json", "model.skops"]
    )
    for artifact in (schema, metadata, model):
        verify_artifact(root, artifact)
    result = candidate_from_data(
        _json_input(root, candidate), str((root / names[0][0]).absolute())
    )
    _check(result.bundle is not None and result.model_id == request.identity.model_id)
    meta = parse_json(verify_artifact(root, metadata), MAX_FILE)
    _check(meta == parse_json(result.bundle.metadata_json.encode(), MAX_FILE))
    _check(
        result.bundle.schema_sha256 == schema.sha256
        and result.bundle.model_sha256 == model.sha256
    )
    records = _json_input(root, probes)
    _check(type(records) is list and len(records) <= 1000)
    return result.bundle, records


def _predict(root, request, options, progress):
    from mlforge.prediction.runtime import InputValidationError, Predictor

    progress("predicting")
    bundle, records = _bundle_inputs(root, request)
    predictor = Predictor._from_directory(bundle.directory)
    operation = (
        predictor.transform_many
        if bundle.task.value == "reduction"
        else predictor.predict_many
    )
    try:
        predictions = operation(records)
    except InputValidationError as error:
        raise DomainError(
            "PREDICT_INPUT", str(error), "Correct the selected inputs."
        ) from None
    return [_save(root, request.outputs[0], predictions)]


def _export(root, request, options, progress):
    from mlforge.export.wheel import export_wheel

    progress("exporting")
    bundle, records = _bundle_inputs(root, request)
    _check(
        all(
            type(options[key]) is str and len(options[key]) <= 4096
            for key in ("module_name", "version", "publication_directory")
        )
    )
    partial_run = options.get("partial_run", False)
    _check(type(partial_run) is bool)
    publication = Path(options["publication_directory"])
    _check(publication.is_absolute())
    descriptor = os.open(publication, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        _check(info.st_uid == os.getuid() and info.st_mode & 0o777 == 0o700)
    finally:
        os.close(descriptor)
    wheel = export_wheel(
        bundle,
        publication,
        options["module_name"],
        options["version"],
        records,
        partial_run=partial_run,
    )
    # The worker only stages bytes; final destination publication belongs to parent.
    os.link(wheel, publication / "wheel.whl", follow_symlinks=False)
    wheel.unlink()
    staged = publication / "wheel.whl"
    progress("validating_artifact")
    return [
        _save(
            root,
            request.outputs[0],
            {
                "name": wheel.name,
                "size": staged.stat().st_size,
                "sha256": hashlib.sha256(staged.read_bytes()).hexdigest(),
            },
        )
    ]


DISPATCH = {
    Operation.PARSE: _parse,
    Operation.INSPECT: _inspect,
    Operation.REVIEW: _review,
    Operation.PREFLIGHT: _prepare,
    Operation.PREPARE: _prepare,
    Operation.TRAIN: _train,
    Operation.PREDICT: _predict,
    Operation.EXPORT: _export,
}


def execute(root, operation_id, emit):
    """One request, no retries or acceptance. Exit 0 success; 1 service; 2 protocol."""
    request, sequence = None, 0

    def event(kind, **fields):
        nonlocal sequence
        emit(encode(RunEvent(request.identity, sequence, kind, **fields)))
        sequence += 1

    try:
        _check(
            type(operation_id) is str
            and re.fullmatch(r"[0-9a-f]{32}", operation_id) is not None
        )
        root = Path(root)
        request = decode(
            read_owned(root, f"request-{operation_id}.json", MAX_MESSAGE), Request
        )
        _check(request.identity.operation_id == operation_id)
        _check(request.outputs == output_names(request.identity))
        _check(len(request.inputs) == INPUT_COUNTS[request.identity.operation])
        options = parse_json(request.options_json.encode())
        allowed = OPTION_KEYS[request.identity.operation]
        _check(
            set(options) == allowed
            or (
                request.identity.operation == Operation.EXPORT
                and set(options) == allowed | {"partial_run"}
            )
        )
        # Hold the checked root's descriptor as cwd. Replacing a pathname cannot
        # redirect service writes through an unexpected new root or symlink.
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fchdir(root_fd)
            root = Path(".")
            _check(
                decode(
                    read_owned(root, f"request-{operation_id}.json", MAX_MESSAGE),
                    Request,
                )
                == request
            )
            for artifact in request.inputs:
                verify_artifact(root, artifact)
            event(EventKind.STARTED)
            if request.identity.operation != Operation.TRAIN:
                os.mkdir(operation_id, mode=0o700)
            artifacts = DISPATCH[request.identity.operation](
                root,
                request,
                options,
                lambda phase: event(EventKind.PROGRESS, phase=phase),
            )
            result = Result(request.identity, tuple(artifacts))
            _check({a.name for a in result.artifacts} == set(request.outputs))
            for artifact in result.artifacts:
                verify_artifact(root, artifact)
            write_owned(root, f"result-{operation_id}.json", encode(result))
            event(EventKind.COMPLETED)
            return 0
        finally:
            os.close(root_fd)
    except Exception as error:
        if (
            isinstance(error, ProtocolError)
            or isinstance(error, (ValueError, TypeError, KeyError))
            and not isinstance(error, DomainError)
        ):
            error, exit_code = ProtocolError(), 2
        elif isinstance(error, DomainError):
            exit_code = 1
        elif isinstance(error, OSError):
            error, exit_code = (
                DomainError(
                    "STORAGE",
                    "The operation could not save its private files.",
                    "Check free space and permissions, then retry.",
                ),
                1,
            )
        else:
            error, exit_code = (
                DomainError(
                    "WORKER_FAILED",
                    "The operation failed safely.",
                    "Retry or choose another configuration.",
                ),
                1,
            )
        if request is not None:
            try:
                if sequence == 0:
                    event(EventKind.STARTED)
                # Safe service error details stay in private artifacts, not logs.
                details = {
                    "code": error.code,
                    "message": error.message,
                    "action": error.action,
                    "row": error.row,
                    "column": error.column,
                }
                artifact = write_owned(
                    root, f"error-{operation_id}.json", json_data(details)
                )
                write_owned(
                    root,
                    f"result-{operation_id}.json",
                    encode(Result(request.identity, (artifact,))),
                )
                event(EventKind.FAILED, error_code=error.code)
            except Exception:
                pass  # Nonzero exit without terminal evidence is never success.
        return exit_code


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        return 2
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[name] = "1"
    os.umask(0o077)
    # Keep a private protocol descriptor. Native/library stdout/stderr is discarded
    # so a numerical exception cannot leak rows or corrupt the JSONL channel.
    with os.fdopen(os.dup(sys.stdout.fileno()), "wb", buffering=0) as protocol:
        with open(os.devnull, "wb") as sink:
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
            return execute(args[0], args[1], protocol.write)


if __name__ == "__main__":
    raise SystemExit(main())
