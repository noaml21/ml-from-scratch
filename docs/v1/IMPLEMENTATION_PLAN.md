# Ordered implementation plan

V1 was delivered in the ten gated phases below. A phase was complete only when its tests, canonical documentation and diff review passed; each landed as several small verified commits, and the commit boundaries listed here map onto the Git history. The ordering is risk-first: export and installation feasibility (P02) was proven before any UI work. PRODUCT_SPEC owns scope; this document owns ordering.

## Checkpoint-sized work units

Each phase was executed as three numbered units in order; the phase sections below keep the full scope, tests and completion gate. Each unit ended with a targeted check of its outcome. Unit completion was not phase verification: the phase gate reran the full checks.

| Phase | Unit .1 | Unit .2 | Unit .3 |
|---|---|---|---|
| P01 | P01.1 inspect branch/baseline and seed checkpoint | P01.2 package/constraints/installed entrypoint | P01.3 CI baseline + phase gate |
| P02 | P02.1 typed core/model contracts | P02.2 shared prediction/persistence contracts | P02.3 six model wheel roundtrips + phase gate |
| P03 | P03.1 bounded canonical importers | P03.2 inference/override/Prepare rules | P03.3 examples + adversarial data tests + phase gate |
| P04 | P04.1 eligibility/features/split | P04.2 fitted transforms and model defaults | P04.3 evaluation/no-leakage/bundle tests + phase gate |
| P05 | P05.1 worker protocol and ownership | P05.2 cancellation/timeouts/failure isolation | P05.3 state invalidation and lifecycle tests + phase gate |
| P06 | P06.1 styled shell/help/focus | P06.2 picker/path/examples/preview | P06.3 override/errors/resize + UX checklist + phase gate |
| P07 | P07.1 goal/target/features/preprocessing | P07.2 model selection/live training | P07.3 task results/inspection + UX checklist + phase gate |
| P08 | P08.1 Try forms and runtime parity | P08.2 export flow and atomic/error paths | P08.3 installed-wheel checks + UX checklist + phase gate |
| P09 | P09.1 full installed-app E2E | P09.2 keyboard/visual/resize polish | P09.3 release verifier/CI/acceptance evidence + phase gate |
| P10 | P10.1 freeze and verify code candidate | P10.2 build report/log/doc consistency | P10.3 evidence commit and clean status |

## P01 — Baseline, branch and packaging foundation
**Depends:** complete planning branch.
**Objective:** retain educational behavior and make an installable minimal package with reproducible dependencies.
**Work:** create v1/mlforge from the verified planning base; record baseline SHAs/status/tests; add explicit setuptools discovery, __main__/--help/--version, runtime/dev/demo extras, tested constraints, test markers and CI skeleton; preserve original algorithms/imports/assets. Update README to distinguish current workbench implementation status and educational track.
**Tests:** original 15 tests, all three comparisons, dependency resolution/pip check, wheel/sdist metadata/package contents, clean installed --help/--version; both Python CI versions.
**Docs:** audit baseline additions, architecture dependency choices.
**Complete when:** source checkout and clean installed namespace both work; constraints resolve; no broad legacy rewrite.
**Commit boundary:** "build: establish MLForge package and preserve educational baseline".

## P02 — Core contracts and export feasibility
**Depends:** P01.
**Objective:** remove serialization/installation risk before UI construction.
**Work:** shared contracts.py records/task enums/errors with dataset records in datasets/records.py; stdlib-AST dependency guard and fixtures per TEST_PLAN; concrete six-model factories; provisional pipeline builder from tiny in-memory fixtures; shared inference runtime contract; fixed wheel template; skops type review. Create parametrized tests for all six fit→serialize→wheel→clean-install→infer paths. This minimal vertical slice uses final exporter structure and is refined later, not disposable duplicate runtime code.
**Tests:** architecture guard positive/negative fixtures and fresh-process imports without Textual/Rich; six real pipelines roundtrip; compatibility/type/hash failures; consumer doesn't depend on MLForge; number/category/missing normalization; output API per task. No UI yet.
**Docs:** align HOW_IT_WORKS and EXTENDING_MLFORGE with implemented boundaries; exact resolved versions/trust allowlist rationale; fill EXPORT_SPEC implementation notes without changing policy.
**Complete when:** all six pipelines can safely ship with exact preprocessing and install independently. Fix compatibility here before next phase.
**Commit boundaries:** "feat(core): define task and prediction contracts"; "feat(export): prove standalone wheel roundtrips".

## P03 — Canonical datasets, import and schema
**Depends:** P02.
**Objective:** all supported formats and type verification are reliable headlessly.
**Work:** bounded strict CSV/TSV/JSONL importers, immutable cells, provenance, safe errors, full-table inference, stats/preview, validated overrides/reset, Prepare prompt, synthetic examples and file checks.
**Tests:** entire dataset matrix in TEST_PLAN including hostile structure/control characters/limits; examples equivalence; original file immutability.
**Docs:** dataset edge-case examples, synthetic generation provenance.
**Complete when:** no silently lost/coerced rows, leading-zero values survive overrides, ambiguous cases remain correctable.
**Commit boundaries:** "feat(data): add bounded canonical importers"; "feat(data): add schema review and preparation guidance".

## P04 — ML preparation, models and evaluation
**Depends:** P03.
**Objective:** implement all task semantics without TUI.
**Work:** tasks.py eligibility/feature rules, preprocessing.py shared split and transform construction, training.py candidate fit/evaluation orchestration, warnings/acknowledgements, fitted pipelines per candidate, actual limits, k/components controls, metrics/baselines/diagnostics/recommendation, immutable evaluated bundles. Connect P02 runtime/export to real canonical input and metadata.
**Tests:** all no-leakage sentinels, eligibility boundaries, deterministic split/model results, hand-checked metrics, unsupervised degeneracy, exact evaluated pipeline export, unknown categories.
**Docs:** help-content facts from ML_PIPELINE; record decisions in the canonical owner.
**Complete when:** all four tasks succeed on valid fixtures and fail safely on invalid ones; no preprocessing fitted on holdout.
**Commit boundaries:** "feat(ml): add validated preprocessing and task models"; "feat(ml): evaluate and retain reproducible candidates".

## P05 — Process orchestration and state machine
**Depends:** P04.
**Objective:** bounded background operations, safe cancel and correct session transitions.
**Work:** execution/worker.py entrypoint, protocol.py and coordinator.py with responsibilities per ARCHITECTURE; JSONL protocol, private temporary ownership, coordinator serial candidates/deadlines, integrity-checked outputs, error isolation, event revisions, state invalidation, quit/cleanup. Offload parse/preflight/train/predict/export. No widgets required.
**Tests:** real child cancellation/kill/reap, sentinel survives, complete-vs-cancel races, timeouts/crash/malformed output/stderr flood, partial/all failures, disk errors, stale/duplicate events, no child networking, source unchanged.
**Docs:** actual lifecycle notes consistent with ARCHITECTURE; update both practical guides to real code paths.
**Complete when:** a blocked model cannot trap UI-facing async supervision, no invalid result accepted, normal cancellation leaves no owned live child.
**Commit boundaries:** "feat(execution): isolate operations and enforce lifecycle"; "feat(application): manage immutable run revisions".

## P06 — TUI shell and dataset journey
**Depends:** P05.
**Objective:** polished Welcome→Load→Preview, not a terminal questionnaire.
**Work:** shell/theme/footer/help focus per DESIGN_SYSTEM; separate screens; file picker/manual/examples; parsing states; preview/table/type override; Prepare Copy/Save/fallback; responsive resize guard. Wire real application services.
**Tests:** Pilot keyboard only, text-key conflicts, load failures/cancel, override/reset, incorrect preview action, clipboard/save errors, literal untrusted content, 100x30/80x24/below minimum.
**Docs:** README launch/first dataset, UX capture evidence.
**Complete when:** all supported formats reach explicit correct preview confirmation without mouse/browser.
**Commit boundaries:** "feat(tui): establish accessible terminal shell"; "feat(tui): load and verify local datasets".

## P07 — Configuration, training and results
**Depends:** P06.
**Objective:** complete task journeys with honest model comparison.
**Work:** clean goal list/context help; suggested/all targets; feature reasons/leakage acknowledgement; short automatic-preprocess summary; model selection/task controls; responsive training/failure/cancel; results and task-specific inspection; selected-model screen.
**Tests:** four real task journeys, no-target unsupervised navigation, gates/invalidation, partial results/ranking, timer/help/cancel during real child work, metric help/focus, below-minimum cancel.
**Docs:** user walkthrough, final metric text/help, synthetic screenshots.
**Complete when:** each goal is trainable and inspectable entirely inside terminal, and no stale/failed model is selectable.
**Commit boundaries:** "feat(tui): guide task and model selection"; "feat(tui): train and inspect reliable results".

## P08 — Try and complete exporter experience
**Depends:** P07.
**Objective:** selected models become useful installed artifacts.
**Work:** task-aware forms and exact shared runtime; wheel destination/name/version UI, privacy/compatibility note; finish atomic publish/size/collision/security checks; task-specific install/API usage screen; offline export + all model roundtrip and failure tests.
**Tests:** Try input errors/missing/new categories/PCA vector; comparison with installed wheel; six-model export install suite; atomic cancel/permissions/disk/collision, no raw dataset leakage.
**Docs:** README export tutorial, model-card template, EXPORT_SPEC implementation details.
**Complete when:** user can skip Try, export from any goal, pip install in a fresh venv and reproduce in-app outputs without preprocessing code.
**Commit boundaries:** "feat(prediction): add typed in-terminal model trials"; "feat(export): deliver verified local model packages".

## P09 — Integration, polish and adversarial verification
**Depends:** P08.
**Objective:** remove severe usability/reliability gaps before release.
**Work:** finish TEST_PLAN full matrix, installed-app E2E, full-flow keyboard/resize/error inspection, minimum terminal sizing, statuses and focus; implement deterministic release verifier/wheelhouse setup; final CI matrix. Keep scope fixed; repair root causes.
**Tests:** full suite/lint/build/twine/comparisons, every release verifier step and no-network mode, visual/PTY checks, bounded-input performance guard.
**Docs:** README supported environments, installation/troubleshooting/privacy/limitations; screenshots; acceptance evidence.
**Complete when:** every acceptance ID has passing evidence or an explicit blocker (a blocker prevents P10 completion).
**Commit boundaries:** "test: verify installed workflows and adversarial cases"; "fix(tui): complete keyboard and responsive polish".

## P10 — Release evidence
**Depends:** P09, all acceptance gates passed.
**Objective:** a reviewable V1 release candidate, not a merge/publish.
**Work:** final verification on release candidate, clean git audit, documentation consistency, write V1_BUILD_REPORT with full architecture/scope/tests/install/export/UX/limitations/review hotspots. Separate the verified implementation SHA from the evidence-only commit that records it.
**Tests:** final TEST_PLAN commands and both supported CI versions; rerun relevant checks for any fixes, never reuse stale evidence after code changes.
**Docs:** acceptance matrix evidence, final report, README final verified scope; both practical guides match actual files/contracts and no longer describe completed modules as merely planned.
**Complete when:** code candidate is immutable and verified; final evidence-only commit exists; working tree has no unexplained changes; the report states the SHA, branch and honest remaining limitations.
**Commit boundary:** "docs: record verified MLForge V1 release candidate".

A blocked phase was not to be bypassed: no jumping ahead, reducing scope, weakening tests or reporting success.

## Specifications per phase
Each phase was checked against the canonical owners below, plus the cross-cutting scope and architecture invariants.

| Phase | Canonical owners to reread |
|---|---|
| P01 | REPOSITORY_AUDIT, ARCHITECTURE dependency/packaging, TEST_PLAN baseline |
| P02 | ARCHITECTURE contracts, ML_PIPELINE model definitions, EXPORT_SPEC, TEST_PLAN export |
| P03 | DATASET_SPEC, TEST_PLAN datasets, UX_FLOW preview/Prepare |
| P04 | ML_PIPELINE, DATASET_SPEC schema, EXPORT_SPEC runtime, TEST_PLAN leakage/evaluation |
| P05 | ARCHITECTURE lifecycle, UX_FLOW training/quit, TEST_PLAN process/state |
| P06 | DESIGN_SYSTEM, UX_FLOW load/preview, DATASET_SPEC, TEST_PLAN Pilot |
| P07 | DESIGN_SYSTEM, UX_FLOW configuration/results, ML_PIPELINE, ARCHITECTURE events, TEST_PLAN |
| P08 | DESIGN_SYSTEM, UX_FLOW Try/export, EXPORT_SPEC, TEST_PLAN exported installation |
| P09 | TEST_PLAN, ACCEPTANCE_CRITERIA, DESIGN_SYSTEM, UX_FLOW |
| P10 | TEST_PLAN release, ACCEPTANCE_CRITERIA, all affected docs |

Every phase kept docs/HOW_IT_WORKS.md and docs/EXTENDING_MLFORGE.md aligned with implemented paths and contracts. The architecture guard was introduced in P02, runs in the ordinary suite and was part of P09/P10 release verification.
