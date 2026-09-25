# Architecture

## Package and direction
Add `src/mlforge/`; do not move the original `src/{kmeans,logistic_regression,pca}.py`. Setuptools src-layout discovery includes only `mlforge*`. Original checkout imports `src.kmeans` remain valid and original demos remain runnable. Distribution provides `mlforge = mlforge.__main__:main` and `python -m mlforge`; noninteractive `--version` and `--help` do not enter full screen.

Planned cohesive modules (paths below are contracts for implementation, not existing code):
```text
src/mlforge/
  __main__.py        command-line bootstrap; compose application and TUI
  contracts.py       shared task/error/experiment/result records; no services
  application/       state.py, service.py
  datasets/          records.py, importers.py, inference.py, validation.py, prepare.py
  tasks.py           task descriptions, eligibility and feature/target rules
  preprocessing.py   prepare shared split/policy; build unfitted transforms
  models.py          concrete ModelSpec registry + estimator factories
  training.py        fit and evaluate one candidate; no process management
  execution/         protocol.py, coordinator.py, worker.py
  evaluation.py      metric/diagnostic calculations and ranking rules
  prediction/        runtime.py, schema.py
  export/            wheel.py, templates/
  tui/               app.py, screens/, widgets/, theme.tcss, help.py
  examples/          packaged synthetic datasets + provenance
```
`execution` is named for its real responsibility: parse/prepare/train/predict/export child operations, not just training. `training.py` owns candidate fitting. `datasets/prepare.py` generates the Prepare with AI text; it never performs ML preprocessing. `prediction/schema.py` builds and validates export metadata; `datasets/inference.py` infers column types, not model predictions. Keep these meanings in module docstrings. Split files only when a cohesive implementation becomes unwieldy; do not create a generic utils/common/services hierarchy.

No abstract base class for every module, plugin system, database, HTTP server or event bus. A small importer dispatch map and concrete model registry provide real extension seams. Plain functions and typed records suffice. [EXTENDING_MLFORGE](../EXTENDING_MLFORGE.md) gives practical change locations; it cannot authorize new V1 scope. [HOW_IT_WORKS](../HOW_IT_WORKS.md) explains the flow; this document remains the canonical boundary owner.

## Dependency boundaries
Public direction: TUI → application → execution/core. The child dispatcher invokes core services; core services never call back into the application or presentation. Cross-process messages are data, not Python imports in the reverse direction.

The table lists permitted first-party dependencies across module boundaries. Imports within one listed package must also be acyclic. A new edge requires an explained contract change here and corresponding architecture-test update, not a blanket exception.

| Importing module/package | Permitted other MLForge modules |
|---|---|
| datasets.records | None; stdlib value records only |
| contracts | datasets.records only; otherwise stdlib |
| datasets (other modules) | contracts, datasets.records and cohesive dataset helpers |
| tasks | contracts, datasets.records |
| models | contracts |
| prediction.runtime | None, including no relative MLForge imports; stdlib and declared inference dependencies only |
| prediction.schema | contracts, datasets.records, prediction.runtime |
| preprocessing | contracts, datasets.records, tasks, prediction.runtime |
| evaluation | contracts |
| training | contracts, datasets.records, tasks, preprocessing, models, evaluation, prediction |
| export | contracts, prediction |
| execution.protocol | contracts |
| execution.coordinator | contracts, execution.protocol |
| execution.worker | contracts, execution.protocol, datasets, tasks, preprocessing, models, training, evaluation, prediction, export |
| application | contracts, datasets.records, datasets.importers (format/example descriptors), datasets.prepare (safe prompt generation/publication), tasks, models, evaluation (ranking), execution.coordinator, execution.protocol |
| tui | application, contracts, datasets.records; never execution/core service entrypoints |
| __main__ | application, tui; explicit composition only |

Only `tui/` imports Textual or Rich. Bootstrap imports the TUI lazily after handling --help/--version. No sklearn fitting, raw subprocess management or metrics calculations in widgets/application. Application may inspect lightweight importer/task/model descriptions and call core ranking over accepted metric records; expensive work goes through execution. Importer descriptors perform no file I/O at import time. Model factories import estimators when invoked, not as a package-initializer side effect. Package `__init__.py` files remain minimal: no eager service/UI re-exports, runtime auto-registration or discovery. No runtime import cycle or type-check-only reverse dependency used to evade the direction.

The coordinator knows operation kinds, deadlines, ordered requests and result envelopes, not estimator/importer/metric-specific branches. The worker uses one explicit operation dispatch table and sets thread limits before importing numerical libraries. It does not import the coordinator, application or TUI. Core operations can be called in headless tests without launching a process; worker entrypoint adapts them to files/events. Application owns semantic decisions and accepted state; coordinator owns child lifetime and transport validation.

Use a small stdlib-AST pytest architecture check, specified in TEST_PLAN, starting in P02. Enforce the table, no direct Textual/Rich outside TUI, no first-party import cycles, and the standalone runtime boundary. Keep the guard local to tests: no dependency-injection container, import-linter framework or architecture runtime library. Static checks supplement real headless import and installed-wheel tests; they do not prove absence of every possible dynamic behavior.

Importer format descriptors come from datasets/importers.py, task capabilities from tasks.py, model choices from models.py, and metric/diagnostic keys plus ordering from evaluation.py. Application exposes these as snapshot data; the TUI keeps help prose and rendering only. Do not duplicate supported-extension/model lists or ranking rules in screens. Scalar/table diagnostics use simple data descriptors; a new diagnostic shape may need one explicit renderer, not a generic visualization framework.

## Core contracts
Prefer frozen dataclasses/enums and explicit validated JSON serialization for crossing process boundaries. Shared TaskKind, DomainError, ExperimentSpec, PreparedRun, CandidateResult and ModelBundle metadata/handle records live in contracts.py, not application/state.py. Dataset records/schema live in datasets/records.py; ModelSpec lives with models.py; RunEvent and wire codecs live in execution/protocol.py. Contracts contain no widgets, process objects, service locators or callable factories (ModelSpec is a local-only registry record, never serialized).

PreparedRun is a plan with row IDs/policy, not a globally fitted preprocessor. Each candidate owns its fitted transform objects. ModelBundle denotes the fitted pipeline plus metadata; in parent-facing records it is an opaque validated artifact handle with immutable metadata. The actual estimator is created/loaded only in operation children or headless tests. Frozen dataclasses alone do not freeze nested arrays/dicts: copy or expose read-only views and never return a mutable estimator to a screen. CandidateResult is accepted only after process/output validation; a worker success event is provisional.

- TabularDataset / Cell / Column: DATASET_SPEC.
- Schema: inferred/effective types, overrides, counts, warnings; original values retained separately.
- ExperimentSpec: schema_version=1, dataset revision/fingerprint, task, target ID or null, ordered feature IDs, model IDs, task options, seed, acknowledgements.
- PreparedRun: immutable effective schema, eligible rows and exact split row IDs, preprocessing policy and dependency versions.
- ModelSpec: stable ID, task, factory, scale-numeric flag, help key. Only one sklearn backend in V1.
- CandidateResult: status, elapsed, metrics with nullable values/reasons, diagnostics, warnings, optional validated ModelBundle handle.
- ModelBundle: fitted pipeline, ordered input schema, label mapping, normalization version, estimator params, seed, split counts, sanitized diagnostics and environment. No training matrix or raw dataset retained inside export state.
- RunEvent: protocol_version, run_id, revision, sequence, event kind, optional model_id, bounded safe payload.
- DomainError: stable code, short safe message, action, optional record/column location; never raw stack/data in ordinary UI.

Test pure use without importing Textual. Domain services return records or report simple progress through a supplied callback, not widget messages or wire events. The worker wraps progress in RunEvent; core functions do not import execution.protocol. The application consumes validated wire events and exposes snapshots/notifications; the UI converts those application notifications to Textual messages on its event loop, without importing the wire protocol.

## State and invalidation
Session is in memory: dataset_revision + schema_revision + experiment_revision + run_id. Only application/service.py mutates authoritative state held in application/state.py. Screens render snapshots and issue commands. Local focus, scroll position and unsubmitted text belong to screens; committed selections, revisions, accepted results and selected bundle belong to application state. No parallel widget-owned experiment or module-global session.

New dataset invalidates everything downstream. Type override invalidates confirmation, goal eligibility, target, features, preprocessing plan, models and results. Goal change invalidates target and later stages. Target change invalidates features and later stages. Feature/task-option/model changes invalidate current results; mere Back navigation does not. Keep local form choices where still valid but never present old results as current.

Changing configuration after results asks once whether to discard current results; no confirmation for harmless back navigation. Active run locks configuration. Cancel then edit; events tagged with old revision/run ID are ignored. Duplicate completion events are idempotent; sequence is monotonic. Freeze accepted ModelBundle before enabling Try/Export. An export failure retains that bundle for retry.

## Execution and cancellation
All expensive parsing, inference, preprocessing, fitting, metrics, prediction and wheel generation run off the Textual event loop. UI async workers supervise operations; CPU work uses an owned subprocess, not a Python thread advertised as cancellable.

Use `asyncio.create_subprocess_exec(sys.executable, "-m", "mlforge.execution.worker", ...)`, argument arrays, `shell=False`, and `start_new_session=True` to create an operation-owned process group. One active operation child, sequential candidates; one model child per candidate is preferred for fault isolation. Shared prepared dataset/split are serialized once in a private per-session directory, then read by each candidate child. Operations parse/inspect/review/preflight/prepare/train/predict/export share the worker entrypoint and coordinator; no general RPC service.

Files: canonical JSON for raw cells/spec/events, .skops for fitted standard sklearn pipeline, JSON metadata. Do not use pickle for user-controlled data or arbitrary model paths. Atomic child outputs are accepted only after successful child exit, expected run/model/revision, complete metadata, bounds and integrity checks. Output paths are assigned by parent, never taken unchecked from worker JSON. No partial artifact can become success.

Events over stdout are bounded JSONL (<=16 KiB/event); stderr is bounded and sanitized (keep at most 64 KiB, no rows/paths). Drain both concurrently to prevent pipe deadlocks. No estimator object on event stream. Child abnormal exit, malformed/truncated protocol or broken output is a failed candidate. Coordinator continues remaining candidates after a model-local fault. Dataset/preprocessing contract failure, disk failure or invalid shared state aborts run; previous accepted results remain available.

Deadlines (monotonic): parse/inspect/review/preflight/predict 30s each, each model fit+evaluation+serialization 120s, wheel generation 60s, supervised run total 300s. No percent unless it describes completed candidates; current fit uses spinner + elapsed + operation. Timeouts are failures with retry/back and concrete limits, not successful partial fits.

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

## P01 implementation notes
Package discovery now includes only `mlforge*`; the bootstrap handles help/version without presentation imports. The no-argument workflow now lazily composes the P06 Textual shell with one application Service; the full journey remains in progress. Runtime constraints resolve NumPy 2.5.3, SciPy 1.18.1, sklearn 1.9.1, skops 0.15.0 and Textual 8.2.8, with full transitive pins in requirements/constraints-runtime.txt. Development/demo pins are separate in constraints-dev.txt. The P01 package verifier builds wheel/sdist, installs in isolated environments and checks entrypoints outside the source import path with pip indexes disabled; model-export and TUI verification are later gates.

## P02.1 implemented contracts
`datasets/records.py` stores copied immutable raw rows and separate schema profiles. `contracts.py` defines task/status enums, safe DomainError, experiment/split/result records and an opaque ModelBundle directory/hash/JSON handle. JSON strings keep nested metadata immutable in parent-facing records; operation codecs will validate their contents before accepting worker results. `models.py` has six concrete lazy-import factories and immutable descriptors. The AST guard now checks present modules, including relative/nested/type-only imports, initializer edges, cycles, UI isolation and dynamic/star imports; fresh-process tests block Textual/Rich. This does not claim that future modules or persistence are implemented.

## P02.2 implemented inference/export slice
`prediction/runtime.py` is standalone and eagerly validates bundled schema, environment, archive bounds, hashes, fixed model identity and forest structure before inference. `prediction/schema.py` constructs only fitted ranges/vocabularies and inference metadata, then saves the exact fitted pipeline. `preprocessing.build_pipeline` creates fresh unfitted sklearn transforms; canonical splitting and task eligibility remain P04. `export/wheel.py` builds fixed templates offline, verifies metadata/RECORD and predictions in another interpreter, and publishes by no-replace hard link. Its build/verification descendants inherit the operation group; full process supervision/cancellation is still P05. The headless test simulates absent presentation packages with ModuleNotFoundError and checks none load; this permits sklearn 1.9.1’s optional Rich import fallback without permitting direct first-party presentation imports.

## P03 implemented datasets
`datasets/importers.py` owns bounded local reads and static format/example descriptors. `inference.py` derives descriptive types/statistics; `validation.py` applies atomic overrides/reset and prepares bounded escaped previews/provenance; `prepare.py` generates structural help locally and saves it exclusively. These modules import only permitted dataset helpers/contracts and standard-library dependencies. Five deterministic example resources ship in the app wheel. Training eligibility, process supervision, application state and TUI remain later phases.

## P05.1.a implemented wire and owned-file boundary
`execution/protocol.py` contains frozen Identity, Request, Result, Artifact and RunEvent records, explicit operation/event enums, and strict version-1 JSON codecs. Requests/results are bounded to 64 KiB; JSONL events to 16 KiB including the newline. Unknown fields, duplicate JSON keys, nonfinite numbers, invalid UTF-8, excessive nesting, bool-as-integer and invalid identities are refused. Events expose only known operation phases or safe error codes, never free-form worker logs/data. A per-operation stream requires sequence zero STARTED, contiguous sequence numbers and one terminal event; mismatched identities and duplicates cannot advance it.

Parents assign at most eight input/output resource names (one or two safe relative segments); request/result envelopes are reserved names. Artifacts carry size and SHA-256. Owned-file helpers require owner-only directories/files, use directory file descriptors and O_NOFOLLOW, refuse hardlinks/nonregular files, bound reads to 512 MiB and detect changes while reading. New files are written privately, fsynced and linked without replacement; failure removes only the writer's temporary file. This internal ceiling does not increase dataset/archive budgets. Result validation requires successful child exit, a completed event, no pending cancellation, exact identity and assigned output set, and every resource's integrity. Coordinator lifecycle is the next unit; these helpers alone do not establish process cleanup.


## P05.1.b implemented worker boundary
`execution/worker.py` dispatches only parse, inspect, prepare, train, predict and export. It validates the parent request and service codecs, pins the checked private directory, and writes fresh operation-ID subdirectories. Shared dataset/schema/prepared files are read with size/hash validation. JSON codecs live beside their records in `datasets/records.py` and `contracts.py`; no reverse dependency is introduced. Dataset revisions identify imported data; event revisions identify the current operation/configuration and need not equal them.

The worker emits bounded phase events on a separate stdout descriptor; numerical/native stdout and stderr are discarded. Exit 0 requires a complete integrity-checked result manifest, exit 1 reports a safe service failure and exit 2 a protocol failure. A missing terminal event/manifest is always failure. These are provisional outputs until coordinator acceptance. Prediction/export reconstruct only parent-assigned bundle paths, check handle hashes/metadata and reuse the exact evaluated pipeline. Parse input and private export staging are absolute parent-supplied paths; the worker receives no final destination option; all intermediate outputs stay in the private session directory. Module import performs no work. Process deadlines/cancellation/reaping remain P05.2.

## P05.2.a implemented process supervisor
`execution/coordinator.py` owns a private TemporaryDirectory and one active operation. It spawns the documented argument-array worker in a fresh session, drains bounded JSONL and stderr concurrently, and retains only a capped stderr byte count (never raw data). Result hashes are checked in a tracked I/O thread so the application event loop remains responsive. Cancellation during spawn, validation or cleanup is remembered while owned work finishes; cancellation before acceptance discards provisional completion.

On supported Linux, the session temporarily enables child-subreaper status to collect orphaned export descendants. It waits only for the recorded operation group, never arbitrary children, restores the previous setting on close, and releases a group handle permanently once disappearance is observed. SIGTERM has a two-second grace before SIGKILL; direct child and adopted descendants are reaped before returning. The application composes one coordinator per session. Serial failure-isolation policy, export publication cleanup and application lifecycle integration remain subsequent P05 work; this slice alone is not the P05 gate.

`Coordinator.run_many` serializes the selected one or two candidate requests under one busy/cancellation scope. Requests must share run/revision identity and have distinct operation/model IDs. Its absolute monotonic deadline allows preparation and candidates to share the supervised 300-second budget. It returns immutable ordered outcomes, retained successes, cancellation/abort flags and an all-failed predicate. The application supplies domain error codes requiring run abort; the coordinator distinguishes reported service errors from malformed worker output. Parent-detected corrupt shared inputs or storage failures are fatal; a malformed/crashed candidate cannot overwrite a previously accepted candidate and does not itself prevent the next request. Late events are still drained/validated but are not delivered after cancellation.

Export publication staging is an explicit owned resource: `Coordinator.publication_staging(destination)` creates a private random directory on the destination filesystem. The request contains only that registered directory, not the final destination. The worker validates its permissions/ownership and uses the existing exporter entirely within it, returning a bounded receipt for the fixed private `wheel.whl` leaf. Only after successful child exit, group reaping, valid terminal protocol and result integrity does the parent verify the expected normalized filename, receipt size/hash and owned staged file. Shared `ExportOptions` owns syntax/naming without importing the exporter into the coordinator. After a final cancellation/deadline barrier, the parent alone links the complete file to the destination without replacement and fsyncs it. No await separates that barrier from accepted publication. An fsync failure rolls back only the exact newly created link. Context exit cancels/reaps outstanding owned work before removing staging; session close also cleans outstanding reservations. Replaced directory identities are refused rather than deleting an unrelated path. Existing destination files and accepted wheels are never swept.


## P05.3.a implemented session rules
`application/state.py` holds frozen Session, Configuration, Revisions, ActiveOperation and Run snapshots. `application/service.py` is the sole authoritative mutator. Committed changes invalidate downstream state and monotonically advance revisions; same-value choices and harmless navigation do not. Busy operations lock edits; result-discard confirmation is an explicit command argument. Task/model registry descriptions and core ranking are reused without fitting or UI imports.

Operation identity, captured revisions, contiguous event sequence and terminal uniqueness guard semantic acceptance. A wire completion alone never enables selection: an accepted matching CandidateResult is required. Cancellation rejects unaccepted completion; previously accepted candidates remain immutable and can become partial results after cleanup. Dataset/type changes clear configuration, preparation, results and selection. Export failure retains selection. These headless rules are implemented and tested; real application command adapters and quit/reaping integration remain P05.3.b, so this slice does not complete P05.


## P05.3.b.1 implemented application worker commands
`async with Service()` owns one coordinator. `load` and `change_type` issue the fixed protocol requests and decode validated artifacts into immutable records; schema reset is `change_type(column, None)`. Fixed output names are shared in `execution/protocol.py`, avoiding an application-to-worker import. Bounded JSON/file adaptation runs off the event loop; parsing and type inference remain in the existing worker services. Pending adaptation is settled before session-directory cleanup.

Cancel immediately changes activity and signals the coordinator; command completion returns to idle only after child cleanup. Close persistently locks new commands, cancels, waits for the active command and then closes the coordinator. This covers the finish/close scheduling gap. Failed load or override preserves the previous accepted dataset/schema. Worker errors remain safe codes and staging disk failures use STORAGE. Training/preparation, detailed failure presentation, prediction/export application adapters and their complete lifecycle integration remain P05.3.b.2; the P05 gate is still pending.


## P05.3.b.2.a implemented application training integration
`Service.train` creates one immutable run and absolute preparation/candidate deadline, stages dataset/schema/experiment once and sends shared dataset/prepared references to serial candidate requests. Application artifact adaptation checks prepared identity, candidate model/task, hashes, metrics/diagnostics, counts, acknowledgements and environment before storing accepted handles. `application/artifacts.py` is stateless JSON/file adaptation; only service mutates session snapshots. It does not load estimators or fit data.

The existing coordinator result callback may now return an awaitable. Its transport acceptance occurs before that callback; application decoding uses owned, settled I/O. Cancellation before transport acceptance discards provisional output. Cancellation during decoding of an already accepted transport retains a semantically valid candidate, then stops queued work; no unchecked artifact becomes success. Candidate-local failures remain isolated, shared failures abort, core ranking is reused and quit waits for the full application command before coordinator cleanup. Prediction/export command integration and the full P05 gate remain pending.


## P05.3.b.2.b implemented selected-pipeline adapters
`Service.predict` and `Service.export` require a current selected accepted candidate and its retained owned artifact references. Request identities reuse the selected run/revision/model; active selection/configuration changes are locked. Prediction results are immutable JSON snapshots tagged with the selected identity, and disappear when selection/configuration changes. Failures retain the trained selection for retry. Export reserves coordinator staging and accepts only the parent's published path; publication already accepted by the parent remains committed if cancellation arrives during subsequent cleanup.

The existing raw-row projection helper now lives in datasets.records (also imported by preprocessing), so application can form observed verification inputs without importing preprocessing or duplicating normalization. Worker inference remains the shared standalone runtime. Training passes its actual prepared split policy into metadata. Export copies only run-level partial provenance into wheel metadata/card; accepted pipeline/schema bytes and bundle metadata stay unchanged. Its verification includes observed, all-missing and applicable unseen-category probes, batched within the inference limit; probes remain private temporary data.

## P06.1 implemented shell
The existing bootstrap composes `MLForgeApp(Service())`. Presentation owns screens, focus, help, unsubmitted path text and a temporary resize screen; Service remains the authoritative dataset/run owner. The app opens the service on mount and awaits its cleanup before exit and on unmount. Manual load runs the existing async Service command in a Textual worker, and defers navigation while help/resize owns focus. The shared theme resource is included in application packages. Dataset preview/picker/schema controls now use real services; Prepare follows in P06.3; this shell slice is not the P06 phase gate.

P06 source screens consume application-exposed format/example descriptors. `Service.load_example` resolves only allowlisted package resources and delegates to ordinary load. The shared stdlib-only `datasets.records.visible_text` helper escapes controls for presentation without touching canonical cell values; `datasets.validation` reuses it. No TUI import of importer/validation services is added.

P06 preview uses the pure `datasets.records.preview` projection over accepted records, with optional bounded text snippets. `datasets.validation.preview` remains an explicit compatibility import. TUI owns cell-width truncation and contextual detail rendering; full selected values come from immutable records. This adds no service dependency, file read, inference, or parallel session state.

P06 Prepare uses the narrow application→datasets.prepare edge: the service exposes safe generated text and invokes the existing small atomic no-overwrite writer through shielded I/O. `Activity.SAVING` locks commands; Back waits and quit explicitly waits for the writer and cleanup. This is not CPU execution or a cancellable model worker. Service.close waits for it through the same idle barrier. No raw data enters the prompt, and TUI never imports the writer.

## P07.1 configuration adapters
`tasks.ConfigurationReview` is an immutable, validated description of goal eligibility, suggested/all targets, feature defaults, warnings and option bounds. The REVIEW worker applies existing task rules over accepted data/schema; it performs no fitting. Application accepts only current matching completions. `Configuration.features_initialized` distinguishes first-entry defaults from an intentional empty feature selection; changing target resets initialization. Any configuration edit clears the derived review/prepared snapshot. Harmless review does not discard current results.

PREFLIGHT invokes the same `preprocessing.prepare_run` as training preparation, but without creating a training Run. It checks existing selection/acknowledgement rules and produces an immutable split/policy for the preprocessing summary; no pipeline is fitted. Application validates experiment/schema/row coverage before accepting it. Training still prepares its own current immutable run and fits only afterward. Both operations use existing bounded protocol, 30-second deadline, cancellation, reaping and stale-event barriers; no coordinator policy or dependency edge changes.

Changing features clears an out-of-range dependent PCA dimension so the next review initializes the canonical default; a still-valid dimension is preserved. Review acceptance checks complete column coverage as well as identity/name correspondence. No omitted-column result can silently replace valid choices.
