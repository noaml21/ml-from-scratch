# Architecture

## Package and direction
Add `src/mlforge/`; do not move the original `src/{kmeans,logistic_regression,pca}.py`. Setuptools src-layout discovery includes only `mlforge*`. Original checkout imports `src.kmeans` remain valid and original demos remain runnable. Distribution provides `mlforge = mlforge.__main__:main` and `python -m mlforge`; noninteractive `--version` and `--help` do not enter full screen.

Suggested cohesive modules (subdivide only with a concrete need):
```text
src/mlforge/
  __main__.py
  application/       state.py, service.py
  datasets/          records.py, importers.py, inference.py, validation.py, prepare.py
  preprocessing.py
  models.py          concrete ModelSpec registry + estimator factories
  training/          protocol.py, coordinator.py, worker.py
  evaluation.py
  prediction/        runtime.py, schema.py
  export/            wheel.py, templates/
  tui/               app.py, screens/, widgets/, theme.tcss, help.py
  examples/          packaged synthetic datasets + provenance
```
No abstract base class for every module, plugin system, database, HTTP server or event bus. A small importer dispatch map and concrete model registry provide real extension seams. Add a new importer at the canonical table boundary; a model at ModelSpec factory/task support; preprocessing at the pipeline builder; an exporter as a callable receiving a validated ModelBundle. New tasks must extend task contracts and tests explicitly.

Dependency arrows: tui → application → datasets/preprocessing/models/training/evaluation/prediction/export. Training worker invokes core services; core never imports tui. Prediction runtime is independent of application/Textual and is the same source shipped in generated wheels. Keep runtime.py self-contained apart from stdlib and declared inference libraries; schema.py builds/validates authoring metadata but is not a hidden runtime import from MLForge. No object in a core public contract contains a Textual widget.

## Core contracts
Prefer frozen dataclasses/enums and explicit validated JSON serialization for crossing process boundaries.
- TabularDataset / Cell / Column: DATASET_SPEC.
- Schema: inferred/effective types, overrides, counts, warnings; original values retained separately.
- ExperimentSpec: schema_version=1, dataset revision/fingerprint, task, target ID or null, ordered feature IDs, model IDs, task options, seed, acknowledgements.
- PreparedRun: immutable effective schema, eligible rows and exact split row IDs, preprocessing policy and dependency versions.
- ModelSpec: stable ID, task, factory, scale-numeric flag, help key. Only one sklearn backend in V1.
- CandidateResult: status, elapsed, metrics with nullable values/reasons, diagnostics, warnings, optional validated ModelBundle handle.
- ModelBundle: fitted pipeline, ordered input schema, label mapping, normalization version, estimator params, seed, split counts, sanitized diagnostics and environment. No training matrix or raw dataset retained inside export state.
- RunEvent: protocol_version, run_id, revision, sequence, event kind, optional model_id, bounded safe payload.
- DomainError: stable code, short safe message, action, optional record/column location; never raw stack/data in ordinary UI.

Test pure use without importing Textual. Domain services return results/events, not widget messages. UI converts events to Textual messages on its event loop.

## State and invalidation
Session is in memory: dataset_revision + schema_revision + experiment_revision + run_id. Only application service mutates it. Screens render snapshots and issue commands.

New dataset invalidates everything downstream. Type override invalidates confirmation, goal eligibility, target, features, preprocessing plan, models and results. Goal change invalidates target and later stages. Target change invalidates features and later stages. Feature/task-option/model changes invalidate current results; mere Back navigation does not. Keep local form choices where still valid but never present old results as current.

Changing configuration after results asks once whether to discard current results; no confirmation for harmless back navigation. Active run locks configuration. Cancel then edit; events tagged with old revision/run ID are ignored. Duplicate completion events are idempotent; sequence is monotonic. Freeze accepted ModelBundle before enabling Try/Export. An export failure retains that bundle for retry.

## Execution and cancellation
All expensive parsing, inference, preprocessing, fitting, metrics, prediction and wheel generation run off the Textual event loop. UI async workers supervise operations; CPU work uses an owned subprocess, not a Python thread advertised as cancellable.

Use `asyncio.create_subprocess_exec(sys.executable, "-m", "mlforge.training.worker", ...)`, argument arrays, `shell=False`, and `start_new_session=True` to create an operation-owned process group. One active operation child, sequential candidates; one model child per candidate is preferred for fault isolation. Shared prepared dataset/split are serialized once in a private per-session directory, then read by each candidate child. Operations parse/prepare/train/predict/export may share worker entrypoint and coordinator; no general RPC service.

Files: canonical JSON for raw cells/spec/events, .skops for fitted standard sklearn pipeline, JSON metadata. Do not use pickle for user-controlled data or arbitrary model paths. Atomic child outputs are accepted only after successful child exit, expected run/model/revision, complete metadata, bounds and integrity checks. Output paths are assigned by parent, never taken unchecked from worker JSON. No partial artifact can become success.

Events over stdout are bounded JSONL (<=16 KiB/event); stderr is bounded and sanitized (keep at most 64 KiB, no rows/paths). Drain both concurrently to prevent pipe deadlocks. No estimator object on event stream. Child abnormal exit, malformed/truncated protocol or broken output is a failed candidate. Coordinator continues remaining candidates after a model-local fault. Dataset/preprocessing contract failure, disk failure or invalid shared state aborts run; previous accepted results remain available.

Deadlines (monotonic): parse/inspect/preflight/predict 30s each, each model fit+evaluation+serialization 120s, wheel generation 60s, supervised run total 300s. No percent unless it describes completed candidates; current fit uses spinner + elapsed + operation. Timeouts are failures with retry/back and concrete limits, not successful partial fits.

Cancel:
1. Set cancelling state immediately and stop scheduling new children.
2. Request the owned operation process group to stop via SIGTERM; a native ML call may not cooperate.
3. After 2s terminate grace, SIGKILL the recorded operation-owned group if still live; await/reap the direct child and drain pipes. Verify descendant disappearance. Never signal the app group, unrelated processes, wildcard PIDs, or a reused/released group handle.
4. Discard incomplete outputs, retain prior validated candidates, emit one terminal cancelled state. Quit follows the same lifecycle before leaving terminal mode.
5. A cancellation request wins over a candidate completion not yet accepted by the coordinator. Already accepted completion stays valid. Start/cancel races and repeated cancel/quit are tested.

Training/prediction workers must not spawn grandchildren: forests n_jobs=1; BLAS/OpenMP thread environment set to 1 before imports. The export build frontend may launch its build backend; it must inherit the operation-owned group, never detach, and cancellation/timeout tests must verify both disappear. The coordinator owns build and verification operations sequentially and cleans the group on failure even if its leader exits first. A killed model process has no user dataset write authority beyond owned output files. Parent signal/normal exception paths use finally cleanup. Parent SIGKILL/power loss can leave temporary files; document that limitation rather than promise perfect cleanup. Kernel scheduling/uninterruptible I/O can exceed nominal deadlines; UI stays in cancelling state until reaped, never falsely reports success.

## Persistence and privacy
Use one random owner-only (0700) TemporaryDirectory per session in the user's local runtime/temp area; files 0600. Its contents include bounded canonical data and fitted intermediates, so explain local temporary storage in privacy docs. Clean only exact owned paths on normal exit; no sweeping other directories. No persistence/history default. No global data logging, autosaved source paths or crash upload. Offer safe error codes, not a raw data dump.

Implementation artifacts/tests stay under repository-owned build/tmp paths where possible. Generated examples contain synthetic data only. User exports are explicit destinations. Never modify source datasets, .env, unrelated repositories or system configuration.

## Dependencies and packaging
Runtime: numpy, scipy, scikit-learn, textual, skops, threadpoolctl, packaging, build, setuptools, wheel. Use stdlib CSV/JSON, dataclasses, subprocess, pathlib, tempfile, hashlib and logging with redaction; no pandas/openpyxl needed. If a direct dependency is used, declare it directly. Matplotlib only in demos extra; pytest, pytest-asyncio, ruff, build/twine validation tools in dev as appropriate.

P01 resolves published compatible releases for both supported Pythons, commits exact full runtime/dev constraint files and records pip freeze/test environment. pyproject uses bounded supported ranges; constraints are authoritative tested combinations. Textual 8.2.8 in the reference is evidence, not an automatic mandatory choice. Never copy hypothetical version numbers or substitute dependencies silently. Runtime/export integrity/version policy is EXPORT_SPEC.

Setuptools build for app and generated wheels, standard build frontend with --no-isolation during offline app export. Build tools must already be installed as runtime dependencies. No pip install/subprocess network operation during application use. CI validates both supported Python versions and wheel/sdist contents. Lint new code; avoid mass formatting legacy files merely for a clean diff (configure scoped exclusions if needed without disabling their tests).

Before large UI work, prove all six standard pipelines round-trip with skops and the dependency set. This is a gated technical spike with tests, not a second exporter.
