"""Session commands and semantic acceptance; no widgets, fitting or process code."""

import asyncio
import time
import uuid
from dataclasses import replace
from importlib.resources import as_file, files
from pathlib import Path

from mlforge.application import artifacts
from mlforge.application.state import (
    ActiveOperation,
    Activity,
    Configuration,
    Failure,
    Prediction,
    Revisions,
    Run,
    RunStatus,
    Session,
)
from mlforge.contracts import (
    CandidateResult,
    CandidateStatus,
    DomainError,
    ExperimentSpec,
    ExportOptions,
    TaskKind,
)
from mlforge.datasets.importers import EXAMPLES, FORMATS
from mlforge.datasets.records import (
    ColumnType,
    dataset_data,
    dataset_from_data,
    raw_records,
    schema_data,
    schema_from_data,
)
from mlforge.evaluation import ranked_candidates, recommendation
from mlforge.execution.coordinator import Coordinator, _settle
from mlforge.execution.protocol import (
    MAX_FILE,
    EventKind,
    Identity,
    Operation,
    Request,
    json_data,
    output_names,
    parse_json,
    verify_artifact,
    write_owned,
)
from mlforge.models import MODELS


def _error(code, message, action):
    raise DomainError(code, message, action)


class Service:
    """One authoritative in-memory session, exposed only through frozen snapshots."""

    formats = FORMATS
    examples = EXAMPLES

    def __init__(self):
        self._state = Session()
        self._closing = False
        self._bundles = {}
        self._coordinator = Coordinator()
        self._idle = asyncio.Event()
        self._idle.set()

    async def __aenter__(self):
        await self._coordinator.__aenter__()
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def close(self):
        if self._state.activity == Activity.CLOSED:
            return
        self._closing = True
        self.cancel()
        self._state = replace(self._state, activity=Activity.CANCELLING)
        _, interrupted = await _settle(asyncio.create_task(self._idle.wait()))
        await self._coordinator.close()
        self._closed()
        if interrupted:
            raise asyncio.CancelledError

    async def _operate(self, identity, values, options, decode_result, accept):
        """Adapt one concrete command; all model/data services run in the child."""
        self._idle.clear()
        try:

            def inputs():
                return tuple(
                    write_owned(
                        self._coordinator.root,
                        f"input-{identity.operation_id}-{index}.json",
                        json_data(value, MAX_FILE),
                    )
                    for index, value in enumerate(values())
                )

            input_artifacts, interrupted = await _settle(
                asyncio.create_task(asyncio.to_thread(inputs))
            )
            if interrupted:
                raise asyncio.CancelledError
            if not self._current(identity):
                return False
            request = Request(
                identity,
                input_artifacts,
                output_names(identity),
                json_data(options).decode(),
            )
            outcome = await self._coordinator.run(request, on_event=self._event)
            if not outcome.completed:
                if outcome.cancelled:
                    return False
                failure = await self._io(
                    artifacts.failure_result, self._coordinator.root, outcome
                )
                self._end_operation(identity, error_code=outcome.error_code)
                self._failure(failure)
                return False

            def decoded():
                by_name = {a.name: a for a in outcome.result.artifacts}
                values = tuple(
                    parse_json(
                        verify_artifact(self._coordinator.root, by_name[name]), MAX_FILE
                    )
                    for name in request.outputs
                )
                return decode_result(values)

            value, interrupted = await _settle(
                asyncio.create_task(asyncio.to_thread(decoded))
            )
            if interrupted:
                raise asyncio.CancelledError
            return accept(identity, *value)
        except asyncio.CancelledError:
            self.cancel()
            raise
        except (OSError, ValueError) as error:
            self._end_operation(
                identity,
                error_code=error.code
                if isinstance(error, DomainError)
                else "STORAGE"
                if isinstance(error, OSError)
                else "PROTOCOL",
            )
            return False
        finally:
            self._end_operation(identity)
            self._idle.set()

    def _open_command(self, discard=False):
        self._editable(discard)
        if self._coordinator.root is None:
            _error(
                "SESSION",
                "The session is not open.",
                "Open the application session first.",
            )

    async def load(self, path, *, discard=False):
        self._open_command(discard)
        if "://" in str(path):
            _error(
                "LOCAL_FILE", "Choose a local file.", "Enter a file path, not a URL."
            )
        path = str(Path(path).expanduser().absolute())
        identity = self._begin_operation(Operation.PARSE)
        return await self._operate(
            identity,
            lambda: (),
            {"path": path},
            lambda values: (dataset_from_data(values[0]), schema_from_data(values[1])),
            self._accept_dataset,
        )

    async def load_example(self, filename, *, discard=False):
        if filename not in {example.filename for example in self.examples}:
            _error("EXAMPLE", "Choose a packaged example.", "Return to examples.")
        with as_file(files("mlforge").joinpath("examples", filename)) as path:
            return await self.load(path, discard=discard)

    async def change_type(self, column_id, kind, *, discard=False):
        self._open_command(discard)
        if self._state.dataset is None or column_id not in {
            c.id for c in self._state.dataset.columns
        }:
            _error("COLUMN", "Choose a current column.", "Return to Preview.")
        kind = ColumnType(kind) if kind is not None else None
        dataset, schema = self._state.dataset, self._state.schema

        def values():
            return dataset_data(dataset), schema_data(schema)

        identity = self._begin_operation(Operation.INSPECT)
        return await self._operate(
            identity,
            values,
            {"column_id": column_id, "kind": kind.value if kind else None},
            lambda values: (schema_from_data(values[0]),),
            self._accept_schema,
        )

    @property
    def snapshot(self):
        return self._state

    def _editable(self, discard=False):
        if self._closing or self._state.activity != Activity.IDLE:
            _error(
                "BUSY", "Configuration is locked.", "Cancel and wait before editing."
            )
        if self._state.results and not discard:
            _error(
                "DISCARD",
                "Changing this discards current results.",
                "Confirm discard or go back.",
            )

    def _change(self, configuration, *, discard=False):
        if configuration == self._state.configuration:
            return
        self._editable(discard)
        self._bundles.clear()
        self._state = replace(
            self._state,
            revisions=replace(
                self._state.revisions, experiment=self._state.revisions.experiment + 1
            ),
            configuration=configuration,
            prepared=None,
            run=None,
            selected_model_id=None,
            error_code=None,
            failure=None,
            exported_path=None,
            export_options=None,
            prediction=None,
        )

    def confirm_schema(self):
        if self._state.confirmed:
            return
        self._editable()
        if self._state.dataset is None or self._state.schema is None:
            _error("DATASET", "Load and review a dataset first.", "Return to Load.")
        self._state = replace(self._state, confirmed=True)

    def choose_task(self, task, *, discard=False):
        if not self._state.confirmed:
            _error(
                "CONFIRM", "Review the preview first.", "Confirm the schema in Preview."
            )
        try:
            task = TaskKind(task)
        except ValueError:
            _error("GOAL", "Choose an available goal.", "Return to Goal.")
        if task == self._state.configuration.task:
            return
        self._change(
            Configuration(
                task=task, model_ids=tuple(m.id for m in MODELS if m.task == task)
            ),
            discard=discard,
        )

    def choose_target(self, column_id, *, discard=False):
        config = self._state.configuration
        if config.task is None or not config.task.supervised:
            _error(
                "TARGET",
                "This goal has no target selection.",
                "Choose a supervised goal first.",
            )
        if column_id not in {c.id for c in self._state.dataset.columns}:
            _error("TARGET", "Choose a current column.", "Return to Target.")
        if config.target_id == column_id:
            return
        self._change(
            replace(
                config,
                target_id=column_id,
                feature_ids=(),
                model_ids=tuple(m.id for m in MODELS if m.task == config.task),
                option=None,
                acknowledgements=(),
            ),
            discard=discard,
        )

    def choose_features(self, column_ids, *, discard=False):
        config = self._state.configuration
        ids = tuple(column_ids)
        if config.task is None or (config.task.supervised and config.target_id is None):
            _error(
                "FEATURE",
                "Choose the goal and target first.",
                "Return to Goal or Target.",
            )
        available = {c.id for c in self._state.dataset.columns} - {config.target_id}
        if len(set(ids)) != len(ids) or not set(ids) <= available:
            _error(
                "FEATURE",
                "Choose distinct current inputs without the target.",
                "Return to Features.",
            )
        if ids == config.feature_ids:
            return
        self._change(
            replace(config, feature_ids=ids, acknowledgements=()), discard=discard
        )

    def choose_models(self, model_ids, *, discard=False):
        config = self._state.configuration
        ids = tuple(model_ids)
        available = {m.id for m in MODELS if m.task == config.task}
        if (
            config.task is None
            or len(set(ids)) != len(ids)
            or not set(ids) <= available
        ):
            _error("MODEL", "Choose models for the current goal.", "Return to Models.")
        self._change(replace(config, model_ids=ids), discard=discard)

    def choose_option(self, option, *, discard=False):
        config = self._state.configuration
        if (
            config.task is None
            or (option is not None and type(option) is not int)
            or (config.task.supervised and option is not None)
        ):
            _error("OPTION", "Choose an integer task option.", "Return to Models.")
        self._change(replace(config, option=option), discard=discard)

    def acknowledge(self, codes, *, discard=False):
        values = tuple(codes)
        if any(type(c) is not str for c in values) or len(set(values)) != len(values):
            _error(
                "ACKNOWLEDGEMENT",
                "Choose the displayed warning acknowledgements.",
                "Return to Features.",
            )
        self._change(
            replace(self._state.configuration, acknowledgements=values), discard=discard
        )

    def experiment(self):
        config = self._state.configuration
        if not self._state.confirmed or config.task is None:
            _error(
                "CONFIGURATION",
                "Confirm the dataset and choose a goal.",
                "Return to Preview.",
            )
        try:
            return ExperimentSpec(
                self._state.revisions.dataset,
                self._state.dataset.fingerprint,
                config.task,
                config.target_id,
                config.feature_ids,
                config.model_ids,
                config.option,
                acknowledgements=config.acknowledgements,
            )
        except ValueError:
            _error(
                "CONFIGURATION",
                "Complete the target, features and model choices.",
                "Return to the unfinished selection.",
            )

    def _begin_training(self, *, discard=False):
        self._editable(discard)
        spec = self.experiment()
        run = Run(uuid.uuid4().hex, self._state.revisions, spec)
        self._state = replace(
            self._state,
            run=run,
            prepared=None,
            selected_model_id=None,
            activity=Activity.RUNNING,
            error_code=None,
            failure=None,
            exported_path=None,
            export_options=None,
            prediction=None,
        )
        return run

    def _begin_operation(self, operation, model_id=None):
        if (
            self._state.activity not in (Activity.IDLE, Activity.RUNNING)
            or self._state.active is not None
        ):
            _error("BUSY", "Another operation is still active.", "Wait for cleanup.")
        run = self._state.run
        training = operation in {Operation.PREPARE, Operation.TRAIN}
        if self._state.activity == Activity.RUNNING and not training:
            _error(
                "BUSY", "Training is still active.", "Cancel and wait before editing."
            )
        if operation == Operation.TRAIN and (
            run is None or model_id not in run.experiment.model_ids
        ):
            _error(
                "MODEL", "This model is not in the current run.", "Return to Models."
            )
        if training and (run is None or run.status != RunStatus.RUNNING):
            _error("RUN", "No current training run.", "Start training from Models.")
        identity = Identity(
            run.id
            if run is not None
            and operation
            in {Operation.PREPARE, Operation.TRAIN, Operation.PREDICT, Operation.EXPORT}
            else uuid.uuid4().hex,
            self._state.revisions.experiment,
            uuid.uuid4().hex,
            operation,
            model_id,
        )
        self._state = replace(
            self._state,
            active=ActiveOperation(identity, self._state.revisions),
            activity=Activity.RUNNING,
            error_code=None,
            failure=None,
        )
        return identity

    def _current(self, identity, *, allow_cancelling=False):
        active = self._state.active
        return bool(
            active
            and active.identity == identity
            and active.revisions == self._state.revisions
            and self._state.activity
            in (
                (Activity.RUNNING, Activity.CANCELLING)
                if allow_cancelling
                else (Activity.RUNNING,)
            )
        )

    def _event(self, event):
        if not self._current(event.identity):
            return False
        active = self._state.active
        if active.terminal or event.sequence != active.sequence + 1:
            return False
        if (active.sequence == -1) != (event.kind == EventKind.STARTED):
            return False
        self._state = replace(
            self._state,
            active=replace(
                active,
                sequence=event.sequence,
                phase=event.phase or active.phase,
                terminal=event.kind
                if event.kind in {EventKind.COMPLETED, EventKind.FAILED}
                else None,
            ),
        )
        return True

    def _accept_dataset(self, identity, dataset, schema):
        if (
            not self._current(identity)
            or identity.operation != Operation.PARSE
            or self._state.active.terminal != EventKind.COMPLETED
        ):
            return False
        if tuple(c.id for c in dataset.columns) != tuple(
            p.column_id for p in schema.columns
        ):
            return False
        old = self._state.revisions
        self._bundles.clear()
        self._state = Session(
            revisions=Revisions(old.dataset + 1, old.schema + 1, old.experiment + 1),
            dataset=dataset,
            schema=schema,
        )
        return True

    def _accept_schema(self, identity, schema):
        if (
            not self._current(identity)
            or identity.operation != Operation.INSPECT
            or self._state.active.terminal != EventKind.COMPLETED
        ):
            return False
        if tuple(c.id for c in self._state.dataset.columns) != tuple(
            p.column_id for p in schema.columns
        ):
            return False
        old = self._state.revisions
        self._bundles.clear()
        self._state = Session(
            revisions=Revisions(old.dataset, old.schema + 1, old.experiment + 1),
            dataset=self._state.dataset,
            schema=schema,
        )
        return True

    def _accept_candidate(self, identity, candidate, *, accepted_before_cancel=False):
        if (
            not self._current(identity, allow_cancelling=accepted_before_cancel)
            or identity.operation != Operation.TRAIN
        ):
            return False
        run = self._state.run
        if (
            run is None
            or run.id != identity.run_id
            or candidate.model_id != identity.model_id
            or candidate.model_id not in run.experiment.model_ids
            or any(c.model_id == candidate.model_id for c in run.candidates)
        ):
            return False
        if candidate.status not in (CandidateStatus.COMPLETED, CandidateStatus.FAILED):
            return False
        if (
            candidate.status == CandidateStatus.COMPLETED
            and self._state.active.terminal != EventKind.COMPLETED
        ):
            return False
        if (
            candidate.bundle is not None
            and candidate.bundle.task != run.experiment.task
        ):
            return False
        self._state = replace(
            self._state, run=replace(run, candidates=(*run.candidates, candidate))
        )
        return True

    def _end_operation(self, identity, *, error_code=None):
        if not self._current(identity, allow_cancelling=True):
            return False
        training = identity.operation in {Operation.PREPARE, Operation.TRAIN}
        self._state = replace(
            self._state,
            active=None,
            activity=self._state.activity if training else Activity.IDLE,
            error_code=error_code,
        )
        return True

    def _end_training(self, run_id, *, aborted=False):
        run = self._state.run
        if (
            run is None
            or run.id != run_id
            or run.status != RunStatus.RUNNING
            or self._state.activity == Activity.CLOSED
            or self._state.active is not None
        ):
            return False
        successful = any(c.status == CandidateStatus.COMPLETED for c in run.candidates)
        cancelled = self._state.activity == Activity.CANCELLING
        status = (
            RunStatus.PARTIAL
            if (cancelled or aborted) and successful
            else RunStatus.CANCELLED
            if cancelled
            else RunStatus.COMPLETED
            if successful
            else RunStatus.FAILED
        )
        self._state = replace(
            self._state,
            run=replace(run, status=status),
            active=None,
            activity=Activity.IDLE,
        )
        return True

    async def _io(self, function, *args):
        value, interrupted = await _settle(
            asyncio.create_task(asyncio.to_thread(function, *args))
        )
        if interrupted:
            raise asyncio.CancelledError
        return value

    def _failure(self, failure):
        self._state = replace(self._state, error_code=failure.code, failure=failure)

    @property
    def ranked_results(self):
        run = self._state.run
        return ranked_candidates(run.experiment.task, run.candidates) if run else ()

    @property
    def recommended(self):
        run = self._state.run
        return recommendation(run.experiment.task, run.candidates) if run else None

    async def train(self, *, discard=False):
        self._open_command(discard)
        run = self._begin_training(discard=discard)
        self._idle.clear()
        self._bundles.clear()
        deadline = time.monotonic() + 300
        aborted = False
        try:
            identity = self._begin_operation(Operation.PREPARE)
            inputs = await self._io(
                artifacts.preparation_inputs,
                self._coordinator.root,
                identity,
                self._state.dataset,
                self._state.schema,
                run.experiment,
            )
            if not self._current(identity):
                return False
            prepared_request = Request(identity, inputs, output_names(identity))
            outcome = await self._coordinator.run(
                prepared_request, on_event=self._event, deadline=deadline
            )
            if not outcome.completed:
                if outcome.cancelled:
                    return False
                failure = await self._io(
                    artifacts.failure_result, self._coordinator.root, outcome
                )
                self._end_operation(identity, error_code=failure.code)
                self._failure(failure)
                return False
            prepared = await self._io(
                artifacts.prepared_result,
                self._coordinator.root,
                outcome,
                run.experiment,
                self._state.schema,
                len(self._state.dataset.rows),
            )
            if not self._current(identity):
                return False
            self._state = replace(self._state, prepared=prepared)
            self._end_operation(identity)
            requests = []
            for model_id in run.experiment.model_ids:
                candidate_id = Identity(
                    run.id,
                    run.revisions.experiment,
                    uuid.uuid4().hex,
                    Operation.TRAIN,
                    model_id,
                )
                requests.append(
                    Request(
                        candidate_id,
                        (inputs[0], outcome.result.artifacts[0]),
                        output_names(candidate_id),
                    )
                )
            expected = {request.identity for request in requests}
            started = {}

            def activate(identity):
                if (
                    identity not in expected
                    or self._state.run is None
                    or self._state.run.id != run.id
                    or self._state.revisions != run.revisions
                ):
                    return False
                if (
                    self._state.active is None
                    and self._state.activity == Activity.RUNNING
                ):
                    self._state = replace(
                        self._state, active=ActiveOperation(identity, run.revisions)
                    )
                    started[identity] = time.monotonic()
                return self._current(identity)

            def event(value):
                if activate(value.identity):
                    self._event(value)

            async def accepted(outcome):
                identity = outcome.request.identity
                lease = activate(identity)
                if not lease:
                    return
                if outcome.completed:
                    try:
                        (candidate, refs), interrupted = await _settle(
                            asyncio.create_task(
                                asyncio.to_thread(
                                    artifacts.candidate_result,
                                    self._coordinator.root,
                                    outcome,
                                    prepared,
                                )
                            )
                        )
                        if interrupted:
                            self.cancel()
                    except (ValueError, KeyError, TypeError):
                        candidate = CandidateResult(
                            identity.model_id,
                            CandidateStatus.FAILED,
                            time.monotonic() - started[identity],
                            error_code="PROTOCOL",
                            error_message="The candidate returned invalid data.",
                        )
                    else:
                        if self._accept_candidate(
                            identity, candidate, accepted_before_cancel=lease
                        ):
                            self._bundles[identity.model_id] = refs
                        self._end_operation(identity)
                        if interrupted:
                            raise asyncio.CancelledError
                        return
                else:
                    failure = await self._io(
                        artifacts.failure_result, self._coordinator.root, outcome
                    )
                    candidate = CandidateResult(
                        identity.model_id,
                        CandidateStatus.FAILED,
                        time.monotonic() - started[identity],
                        error_code=failure.code,
                        error_message=failure.message,
                    )
                self._accept_candidate(
                    identity, candidate, accepted_before_cancel=lease
                )
                self._end_operation(identity)

            results = await self._coordinator.run_many(
                requests,
                on_event=event,
                on_result=accepted,
                deadline=deadline,
                abort_codes=frozenset(
                    {
                        "STORAGE",
                        "STALE_RUN",
                        "STALE_DATA",
                        "INPUT_SCHEMA",
                        "MATRIX_LIMIT",
                    }
                ),
            )
            aborted = results.aborted
            if aborted and results.outcomes:
                self._failure(
                    await self._io(
                        artifacts.failure_result,
                        self._coordinator.root,
                        results.outcomes[-1],
                    )
                )
        except asyncio.CancelledError:
            self.cancel()
            raise
        except (OSError, ValueError) as error:
            aborted = True
            self._failure(
                Failure(
                    error.code
                    if isinstance(error, DomainError)
                    else "STORAGE"
                    if isinstance(error, OSError)
                    else "PROTOCOL",
                    "Training could not complete safely.",
                    "Review the configuration and retry.",
                )
            )
        finally:
            if self._state.active is not None:
                self._end_operation(
                    self._state.active.identity, error_code=self._state.error_code
                )
            self._end_training(run.id, aborted=aborted)
            if (
                self._state.run.status == RunStatus.FAILED
                and self._state.error_code is None
            ):
                self._failure(
                    Failure(
                        "ALL_FAILED",
                        "No model completed successfully.",
                        "Review candidate errors or return to configuration.",
                    )
                )
            self._idle.set()
        return self._state.run.status == RunStatus.COMPLETED

    def _selected_bundle(self):
        self._open_command(discard=True)
        selected = self._state.selected
        run = self._state.run
        if (
            selected is None
            or run is None
            or run.revisions != self._state.revisions
            or run.status not in (RunStatus.COMPLETED, RunStatus.PARTIAL)
            or selected.model_id not in self._bundles
        ):
            _error("RESULT", "Choose a completed current model.", "Return to Results.")
        return selected, self._bundles[selected.model_id]

    async def predict(self, records):
        selected, refs = self._selected_bundle()
        if type(records) not in (list, tuple) or len(records) > 1000:
            _error(
                "PREDICT_INPUT", "Provide at most 1000 records.", "Correct the inputs."
            )
        records = [dict(row) if type(row) is dict else row for row in records]
        identity = self._begin_operation(Operation.PREDICT, selected.model_id)
        self._state = replace(self._state, prediction=None)
        self._idle.clear()
        try:
            inputs = await self._io(
                artifacts.bundle_inputs, self._coordinator.root, identity, refs, records
            )
            if not self._current(identity):
                return None
            outcome = await self._coordinator.run(
                Request(identity, inputs, output_names(identity)), on_event=self._event
            )
            if not outcome.completed:
                if not outcome.cancelled:
                    self._failure(
                        await self._io(
                            artifacts.failure_result, self._coordinator.root, outcome
                        )
                    )
                return None
            payload = await self._io(
                artifacts.prediction_result,
                self._coordinator.root,
                outcome,
                selected.bundle.task,
                len(records),
                self._state.run.experiment.option,
            )
            if not self._current(identity) or self._state.selected is not selected:
                return None
            prediction = Prediction(
                self._state.run.id, self._state.revisions, selected.model_id, payload
            )
            self._state = replace(self._state, prediction=prediction)
            return prediction
        except asyncio.CancelledError:
            self.cancel()
            raise
        except (OSError, ValueError, KeyError, TypeError) as error:
            self._failure(
                Failure(
                    error.code
                    if isinstance(error, DomainError)
                    else "STORAGE"
                    if isinstance(error, OSError)
                    else "PROTOCOL",
                    "Prediction could not complete safely.",
                    "Correct the inputs and retry.",
                )
            )
            return None
        finally:
            self._end_operation(identity, error_code=self._state.error_code)
            self._idle.set()

    async def export(self, destination, module_name="my_model", version="1.0.0"):
        selected, refs = self._selected_bundle()
        options = ExportOptions(module_name, version)
        run = self._state.run
        partial = (
            run.status == RunStatus.PARTIAL
            or len(run.candidates) != len(run.experiment.model_ids)
            or any(c.status != CandidateStatus.COMPLETED for c in run.candidates)
        )
        identity = self._begin_operation(Operation.EXPORT, selected.model_id)
        self._state = replace(self._state, exported_path=None, export_options=options)
        self._idle.clear()
        try:
            observed = raw_records(
                self._state.dataset,
                run.experiment.feature_ids,
                (self._state.prepared.train_rows[0],),
            )
            inputs = await self._io(
                artifacts.bundle_inputs,
                self._coordinator.root,
                identity,
                refs,
                observed,
            )
            if not self._current(identity):
                return None
            async with self._coordinator.publication_staging(destination) as staging:
                request = Request(
                    identity,
                    inputs,
                    output_names(identity),
                    json_data(
                        {
                            "module_name": module_name,
                            "version": version,
                            "publication_directory": str(staging),
                            "partial_run": partial,
                        }
                    ).decode(),
                )
                outcome = await self._coordinator.run(request, on_event=self._event)
                if not outcome.completed:
                    if not outcome.cancelled:
                        self._failure(
                            await self._io(
                                artifacts.failure_result,
                                self._coordinator.root,
                                outcome,
                            )
                        )
                    return None
                # Parent publication already crossed its acceptance barrier. Do not
                # turn this committed success into a cancelled provisional result.
                self._state = replace(self._state, exported_path=outcome.published_path)
            return self._state.exported_path
        except asyncio.CancelledError:
            self.cancel()
            raise
        except (OSError, ValueError) as error:
            self._failure(
                Failure(
                    error.code if isinstance(error, DomainError) else "EXPORT_IO",
                    "Export could not complete safely.",
                    "Choose a writable destination or different name and retry.",
                )
            )
            return None
        finally:
            self._end_operation(identity, error_code=self._state.error_code)
            self._idle.set()

    def cancel(self):
        self._coordinator.cancel()
        if self._state.activity == Activity.RUNNING:
            self._state = replace(self._state, activity=Activity.CANCELLING)

    def select_candidate(self, model_id):
        self._editable(discard=True)
        run = self._state.run
        if (
            run is None
            or run.status not in (RunStatus.COMPLETED, RunStatus.PARTIAL)
            or model_id
            not in {
                c.model_id
                for c in ranked_candidates(run.experiment.task, run.candidates)
            }
        ):
            _error("RESULT", "Choose a completed current model.", "Return to Results.")
        if model_id != self._state.selected_model_id:
            self._state = replace(
                self._state,
                selected_model_id=model_id,
                prediction=None,
                exported_path=None,
                export_options=None,
            )

    def _closed(self):
        """Called only after the operation owner has completed cleanup."""
        self._state = replace(
            self._state,
            activity=Activity.CLOSED,
            active=None,
            selected_model_id=None,
            prediction=None,
        )
