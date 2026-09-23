"""Owned JSON adaptation and semantic checks, without fitting or session mutation."""

from mlforge.application.state import Failure
from mlforge.contracts import (
    CandidateStatus,
    candidate_from_data,
    experiment_data,
    prepared_from_data,
)
from mlforge.datasets.records import (
    dataset_data,
    record_count,
    record_keys,
    record_text,
    schema_data,
)
from mlforge.evaluation import ranked_candidates
from mlforge.execution.protocol import (
    MAX_FILE,
    MAX_MESSAGE,
    ProtocolError,
    Result,
    decode,
    json_data,
    parse_json,
    read_owned,
    verify_artifact,
    write_owned,
)


def preparation_inputs(root, identity, dataset, schema, experiment):
    return tuple(
        write_owned(
            root,
            f"input-{identity.operation_id}-{index}.json",
            json_data(value, MAX_FILE),
        )
        for index, value in enumerate(
            (dataset_data(dataset), schema_data(schema), experiment_data(experiment))
        )
    )


def prepared_result(root, outcome, experiment, schema, rows):
    prepared = prepared_from_data(
        parse_json(verify_artifact(root, outcome.result.artifacts[0]), MAX_FILE)
    )
    if (
        prepared.experiment != experiment
        or prepared.schema != schema
        or len(prepared.train_rows) + len(prepared.test_rows) != rows
    ):
        raise ProtocolError()
    return prepared


def candidate_result(root, outcome, prepared):
    experiment = prepared.experiment
    identity = outcome.request.identity
    by_name = {a.name.rsplit("/", 1)[-1]: a for a in outcome.result.artifacts}
    candidate = candidate_from_data(
        parse_json(verify_artifact(root, by_name["candidate.json"]), MAX_FILE),
        str(root / identity.operation_id),
    )
    bundle = candidate.bundle
    if (
        candidate.status != CandidateStatus.COMPLETED
        or candidate.model_id != identity.model_id
        or bundle.task != experiment.task
        or bundle.schema_sha256 != by_name["schema.json"].sha256
        or bundle.model_sha256 != by_name["model.skops"].sha256
    ):
        raise ProtocolError()
    metadata = parse_json(verify_artifact(root, by_name["metadata.json"]), MAX_FILE)
    if metadata != parse_json(bundle.metadata_json.encode(), MAX_FILE):
        raise ProtocolError()
    if (
        metadata["model_id"] != identity.model_id
        or metadata["task"] != experiment.task.value
        or metadata["seed"] != experiment.seed
        or metadata["training_count"] != len(prepared.train_rows)
        or metadata["test_count"] != len(prepared.test_rows)
        or metadata["review_acknowledgements"] != list(experiment.acknowledgements)
        or metadata["diagnostics"]
        != parse_json(candidate.diagnostics_json.encode(), MAX_FILE)
        or metadata["warnings"] != list(candidate.warnings)
        or metadata["environment"] != parse_json(prepared.environment_json.encode())
        or not ranked_candidates(experiment.task, (candidate,))
    ):
        raise ProtocolError()
    if metadata["metrics"] != {
        m.key: {"value": m.value, "reason": m.reason} for m in candidate.metrics
    }:
        raise ProtocolError()
    return candidate, tuple(
        by_name[name]
        for name in ("candidate.json", "schema.json", "metadata.json", "model.skops")
    )


def failure_result(root, outcome):
    """Service failures have a separate bounded manifest; never trust raw stderr."""
    fallback = Failure(
        outcome.error_code or "WORKER_FAILED",
        "The operation could not complete.",
        "Retry or go back and review the configuration.",
    )
    if not outcome.reported:
        return fallback
    identity = outcome.request.identity
    try:
        result = decode(
            read_owned(root, f"result-{identity.operation_id}.json", MAX_MESSAGE),
            Result,
        )
        if (
            result.identity != identity
            or len(result.artifacts) != 1
            or result.artifacts[0].name != f"error-{identity.operation_id}.json"
        ):
            raise ProtocolError()
        value = parse_json(verify_artifact(root, result.artifacts[0]))
        record_keys(value, "code message action row column")
        for key in ("code", "message", "action"):
            record_text(value[key])
        if value["code"] != outcome.error_code:
            raise ProtocolError()
        if value["row"] is not None:
            record_count(value["row"])
        if value["column"] is not None:
            record_text(value["column"])
        return Failure(**value)
    except (OSError, ValueError, KeyError, TypeError):
        return fallback
