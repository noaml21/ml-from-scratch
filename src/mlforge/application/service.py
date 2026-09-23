"""Session commands and semantic acceptance; no widgets, fitting or process code."""

import asyncio
import uuid
from dataclasses import replace
from pathlib import Path

from mlforge.application.state import (
    ActiveOperation,
    Activity,
    Configuration,
    Revisions,
    Run,
    RunStatus,
    Session,
)
from mlforge.contracts import CandidateStatus, DomainError, ExperimentSpec, TaskKind
from mlforge.datasets.records import (
    ColumnType,
    dataset_data,
    dataset_from_data,
    schema_data,
    schema_from_data,
)
from mlforge.evaluation import ranked_candidates
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

    def __init__(self):
        self._state = Session()
        self._closing = False
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

            artifacts, interrupted = await _settle(
                asyncio.create_task(asyncio.to_thread(inputs))
            )
            if interrupted:
                raise asyncio.CancelledError
            if not self._current(identity):
                return False
            request = Request(
                identity, artifacts, output_names(identity), json_data(options).decode()
            )
            outcome = await self._coordinator.run(request, on_event=self._event)
            if not outcome.completed:
                self._end_operation(identity, error_code=outcome.error_code)
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
            exported_path=None,
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
            exported_path=None,
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
            run.id if training else uuid.uuid4().hex,
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
        self._state = Session(
            revisions=Revisions(old.dataset, old.schema + 1, old.experiment + 1),
            dataset=self._state.dataset,
            schema=schema,
        )
        return True

    def _accept_candidate(self, identity, candidate):
        if not self._current(identity) or identity.operation != Operation.TRAIN:
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

    def _end_training(self, run_id):
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
            if cancelled and successful
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
        self._state = replace(self._state, selected_model_id=model_id)

    def _closed(self):
        """Called only after the operation owner has completed cleanup."""
        self._state = replace(
            self._state, activity=Activity.CLOSED, active=None, selected_model_id=None
        )
