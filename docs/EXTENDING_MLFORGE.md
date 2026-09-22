# Extending MLForge

Read [AGENTS](../AGENTS.md) first. These are practical recipes for **later authorized changes**, not extra V1 requirements. Core/dataset records, model registry, preprocessing builder, prediction runtime/schema and wheel exporter are implemented alongside the bootstrap; bounded dataset importers, inference, schema validation and local Prepare services are also implemented; task eligibility/review policy and shared split preparation are implemented; training-only fitting, task evaluation/ranking and immutable evaluated bundles are implemented; bounded execution protocol and owned-file validation are implemented; worker dispatch, coordinator lifecycle, application state and TUI remain planned. [ARCHITECTURE](v1/ARCHITECTURE.md) owns dependency/contracts; [PRODUCT_SPEC](v1/PRODUCT_SPEC.md) owns scope. Keep this guide synchronized with the actual code instead of maintaining parallel interfaces here.

Use the existing functions, dispatch maps and records first. Keep mathematical/domain decisions out of widgets, and UI copy/layout out of core services. Update the canonical contract when public behavior or a dependency edge changes; add relevant tests and update this guide. No automatic plugin discovery, registration decorators, abstract factories or speculative interfaces.

## Add a model to an existing task
- Add a concrete ModelSpec/factory with stable ID, task, explicit defaults, scale policy and help key in `models.py`; the model screen obtains its choices through the application, not a second hard-coded estimator list.
- Add help content in `tui/help.py` and update ML_PIPELINE. Reuse `training.py` and the task evaluator; do not add model-name branches to the coordinator or screens.
- Check serialization allowlist/structural validation in `prediction/runtime.py` under EXPORT_SPEC, captured dependency versions and export size bounds. A model needing a different output API/backend is a contract change, not a drop-in factory.
- Tests: fit/failure/reproducibility, no-leakage and all relevant Try→wheel→fresh-install parity/security cases. Unchanged: importers, process protocol/lifecycle and unrelated screens.

## Add an importer
- Implement a bounded parser in `datasets/importers.py` (split a substantial parser into a neighboring file only when justified), register its extension in the existing dispatch map, return TabularDataset records defined in `datasets/records.py`.
- Preserve original lexical values, provenance, limits and safe errors under DATASET_SPEC; inference and overrides run after every importer. Load's supported-format filter comes from importer descriptors returned by the application; no independent extension list in the picker or worker.
- Tests: equivalent canonical values/order, malformed files, limits, controls, no data mutation and one Load/Preview integration case. Unchanged: training, preprocessing, evaluation and exporter if the canonical contract is preserved.

## Add a preprocessing strategy
- Change the policy selection/build functions in `preprocessing.py`; pass explicit task/schema/model requirements. Keep stateless input normalization in `prediction/runtime.py` shared with training; fitted sklearn steps belong inside the pipeline. Do not fit anything in a screen or shared holdout preflight.
- Update ML_PIPELINE and normalization/schema version only when its semantics change. Review export trust/compatibility if a new transformer type is needed. Do not invent a strategy class hierarchy or user-facing tuning control to introduce one alternative.
- Tests: train-only fitting sentinels, feature order/missing/unseen values, determinism and installed prediction parity. Unchanged: process lifecycle, importers and forms unless the input contract actually changes.

## Add a metric or diagnostic
- Implement calculation and task-specific presentation metadata (stable key, direction when ranked, nullable-value reason) in `evaluation.py`. Return data in CandidateResult; calculation and recommendation ordering have one core owner.
- Update ML_PIPELINE and `tui/help.py`. Existing scalar/table renderers should consume descriptors; add a specialized result renderer only for a genuinely new diagnostic shape. The TUI formats numbers but never recalculates metrics. Extra metrics do not automatically become primary table columns or change ranking.
- Tests: independent expected values, degenerate/N/A cases, ordering and rendering/help where affected. Unchanged: importer, preprocessing, estimator factory and coordinator for metrics using existing predictions. If new estimator outputs are required, explicitly update training/runtime contracts instead of fetching them from widgets.

## Add an exporter
- Add a concrete callable/module beside `export/wheel.py` consuming the validated ModelBundle handle, explicit options and owned staging/output paths. Reuse prediction metadata/runtime; never re-fit or access original source paths through global state.
- After authorization, wire its operation in `execution/worker.py`, application command and export UI. Keep coordinator lifecycle generic to operation requests; use explicit limits in its operation policy if a new operation kind needs them.
- Tests: artifact usability in isolation, exact inference identity where relevant, privacy/version/trust policy, no-network execution, atomic failure/no-overwrite and cancellation. Unchanged: importers, model factories and metrics. Do not build an exporter registry/base class while V1 has one exporter.

## Add an ML task
A task changes product semantics across multiple **related** boundaries; promising a one-file change would hide those contracts.
- Define task identity in `contracts.py` and eligibility/target/feature/options rules in `tasks.py`. Update PRODUCT_SPEC/ML_PIPELINE first; reuse the existing four-task table/functions rather than introducing a generic task engine.
- Add appropriate model factories, preparation policy, task evaluator and output contract in their owning modules. Generic train orchestration may need one explicit task dispatch branch when sklearn fit/transform semantics differ; no per-widget algorithm code.
- Review `prediction/runtime.py`, export metadata compatibility and Try form/output mapping. Wire goal/help/task controls in the TUI and state invalidation through application/service.py. Record changes to serialized task/schema versions if needed.
- Tests: eligibility, preparation/leakage, training/evaluation, installed export/runtime API, complete keyboard journey and back/invalidation. Existing importer and process transport/lifecycle should remain unchanged unless the new task explicitly requires a different input or execution contract.

## Add a TUI screen
- Add one screen in `tui/screens/` and route it from `tui/app.py` using application snapshots/commands. Use `tui/widgets/` only for UI behavior actually shared by existing screens, `theme.tcss` tokens and `help.py` entries.
- If a new command is needed, application/service.py validates it and updates application/state.py. The screen keeps focus/scroll/unsubmitted text locally, never an independent experiment or fitted pipeline.
- Update UX_FLOW and use DESIGN_SYSTEM's checklist. Tests: Pilot keyboard/help/focus, validation/empty/busy/error, 100x30/80x24/resize and state preservation. Unchanged: core services when the screen only presents existing capabilities.

## Before submitting any extension
Run targeted tests, architecture import checks and the existing suite; use [TEST_PLAN](v1/TEST_PLAN.md) for export/process/TUI integration gates. Update canonical specs and guides only where affected. Record decisions/evidence in BUILD_LOG and next action in BUILD_STATE. If a small extension touches unrelated importers, lifecycle code and many screens, inspect the coupling before adding another abstraction. Locality means understandable responsibilities, not an arbitrary maximum file count.

Current inference extension points are `normalize_record`, `load_pipeline`, `validate_tree_state`, `fitted_schema`, and `save_bundle`. Export uses `distribution_name`/`wheel_stem` independently of Python import names; changes must preserve repeated/trailing underscore regression coverage and reserved distribution checks. The exact runtime source is packaged, not maintained as a second template.

Worker dispatch is an explicit table in `execution/worker.py`. Change concrete service codecs in their existing record owners when inputs/results change. Preserve private parent-assigned output names, strict nested JSON validation, safe exit/events and real child tests; never serialize Python callables or estimator objects into the wire protocol.
