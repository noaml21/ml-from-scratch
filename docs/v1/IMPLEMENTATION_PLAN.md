# Ordered implementation plan

Each phase is gated. Complete tests, canonical docs, BUILD_LOG evidence and diff review before moving on. Split a phase into smaller logical verified commits when useful; never one final giant commit. Dependencies below are hard sequencing, not an invitation to work ahead. PRODUCT_SPEC owns scope; this document owns ordering.

## P01 — Baseline, branch and packaging foundation
**Depends:** complete planning branch, AGENTS/CODEX_EXECUTION read.
**Objective:** retain educational behavior and make an installable minimal package with reproducible dependencies.
**Work:** create/continue v1/mlforge from planning tip; record baseline SHAs/status/tests; add explicit setuptools discovery, __main__/--help/--version, runtime/dev/demo extras, tested constraints, test markers and CI skeleton; preserve original algorithms/imports/assets. Update README to distinguish current workbench implementation status and educational track.
**Tests:** original 15 tests, all three comparisons, dependency resolution/pip check, wheel/sdist metadata/package contents, clean installed --help/--version; both Python CI versions.
**Docs:** audit baseline additions, architecture dependency choices, BUILD_LOG.
**Complete when:** source checkout and clean installed namespace both work; constraints resolve; no broad legacy rewrite.
**Commit boundary:** "build: establish MLForge package and preserve educational baseline".

## P02 — Core contracts and export feasibility
**Depends:** P01.
**Objective:** remove serialization/installation risk before UI construction.
**Work:** validated core dataclasses/task enums/error contract; concrete six-model factories; provisional pipeline builder from tiny in-memory fixtures; shared inference runtime contract; fixed wheel template; skops type review. Create parametrized tests for all six fit→serialize→wheel→clean-install→infer paths. This minimal vertical slice uses final exporter structure and is refined later, not disposable duplicate runtime code.
**Tests:** imports without Textual; six real pipelines roundtrip; compatibility/type/hash failures; consumer doesn't depend on MLForge; number/category/missing normalization; output API per task. No UI yet.
**Docs:** exact resolved versions/trust allowlist rationale in BUILD_LOG; fill EXPORT_SPEC implementation notes without changing policy.
**Complete when:** all six pipelines can safely ship with exact preprocessing and install independently. Fix compatibility here before next phase.
**Commit boundaries:** "feat(core): define task and prediction contracts"; "feat(export): prove standalone wheel roundtrips".

## P03 — Canonical datasets, import and schema
**Depends:** P02.
**Objective:** all supported formats and type verification are reliable headlessly.
**Work:** bounded strict CSV/TSV/JSONL importers, immutable cells, provenance, safe errors, full-table inference, stats/preview, validated overrides/reset, Prepare prompt, synthetic examples and file checks.
**Tests:** entire dataset matrix in TEST_PLAN including hostile structure/control characters/limits; examples equivalence; original file immutability.
**Docs:** dataset edge-case examples, synthetic generation provenance, BUILD_LOG.
**Complete when:** no silently lost/coerced rows, leading-zero values survive overrides, ambiguous cases remain correctable.
**Commit boundaries:** "feat(data): add bounded canonical importers"; "feat(data): add schema review and preparation guidance".

## P04 — ML preparation, models and evaluation
**Depends:** P03.
**Objective:** implement all task semantics without TUI.
**Work:** target/feature eligibility, warnings/acknowledgements, deterministic shared split, fitted pipelines per candidate, actual limits, k/components controls, metrics/baselines/diagnostics/recommendation, immutable evaluated bundles. Connect P02 runtime/export to real canonical input and metadata.
**Tests:** all no-leakage sentinels, eligibility boundaries, deterministic split/model results, hand-checked metrics, unsupervised degeneracy, exact evaluated pipeline export, unknown categories.
**Docs:** help-content facts from ML_PIPELINE, BUILD_LOG; record decisions in the canonical owner.
**Complete when:** all four tasks succeed on valid fixtures and fail safely on invalid ones; no preprocessing fitted on holdout.
**Commit boundaries:** "feat(ml): add validated preprocessing and task models"; "feat(ml): evaluate and retain reproducible candidates".

## P05 — Process orchestration and state machine
**Depends:** P04.
**Objective:** bounded background operations, safe cancel and correct session transitions.
**Work:** worker entrypoint/JSONL protocol, private temporary ownership, coordinator serial candidates/deadlines, integrity-checked outputs, error isolation, event revisions, state invalidation, quit/cleanup. Offload parse/preflight/train/predict/export. No widgets required.
**Tests:** real child cancellation/kill/reap, sentinel survives, complete-vs-cancel races, timeouts/crash/malformed output/stderr flood, partial/all failures, disk errors, stale/duplicate events, no child networking, source unchanged.
**Docs:** actual lifecycle notes consistent with ARCHITECTURE, BUILD_LOG.
**Complete when:** a blocked model cannot trap UI-facing async supervision, no invalid result accepted, normal cancellation leaves no owned live child.
**Commit boundaries:** "feat(training): isolate operations and enforce lifecycle"; "feat(application): manage immutable run revisions".

## P06 — TUI shell and dataset journey
**Depends:** P05.
**Objective:** polished Welcome→Load→Preview, not a terminal questionnaire.
**Work:** shell/theme/footer/help focus; separate screens; file picker/manual/examples; parsing states; preview/table/type override; Prepare Copy/Save/fallback; responsive resize guard. Wire real application services.
**Tests:** Pilot keyboard only, text-key conflicts, load failures/cancel, override/reset, incorrect preview action, clipboard/save errors, literal untrusted content, 100x30/80x24/below minimum.
**Docs:** README launch/first dataset, UX capture evidence, BUILD_LOG.
**Complete when:** all supported formats reach explicit correct preview confirmation without mouse/browser.
**Commit boundaries:** "feat(tui): establish accessible terminal shell"; "feat(tui): load and verify local datasets".

## P07 — Configuration, training and results
**Depends:** P06.
**Objective:** complete task journeys with honest model comparison.
**Work:** clean goal list/context help; suggested/all targets; feature reasons/leakage acknowledgement; short automatic-preprocess summary; model selection/task controls; responsive training/failure/cancel; results and task-specific inspection; selected-model screen.
**Tests:** four real task journeys, no-target unsupervised navigation, gates/invalidation, partial results/ranking, timer/help/cancel during real child work, metric help/focus, below-minimum cancel.
**Docs:** user walkthrough, final metric text/help, synthetic screenshots, BUILD_LOG.
**Complete when:** each goal is trainable and inspectable entirely inside terminal, and no stale/failed model is selectable.
**Commit boundaries:** "feat(tui): guide task and model selection"; "feat(tui): train and inspect reliable results".

## P08 — Try and complete exporter experience
**Depends:** P07.
**Objective:** selected models become useful installed artifacts.
**Work:** task-aware forms and exact shared runtime; wheel destination/name/version UI, privacy/compatibility note; finish atomic publish/size/collision/security checks; task-specific install/API usage screen; offline export + all model roundtrip and failure tests.
**Tests:** Try input errors/missing/new categories/PCA vector; comparison with installed wheel; six-model export install suite; atomic cancel/permissions/disk/collision, no raw dataset leakage.
**Docs:** README export tutorial, model-card template, EXPORT_SPEC implementation details, BUILD_LOG.
**Complete when:** user can skip Try, export from any goal, pip install in a fresh venv and reproduce in-app outputs without preprocessing code.
**Commit boundaries:** "feat(prediction): add typed in-terminal model trials"; "feat(export): deliver verified local model packages".

## P09 — Integration, polish and adversarial verification
**Depends:** P08.
**Objective:** remove severe usability/reliability gaps before release.
**Work:** finish TEST_PLAN full matrix, installed-app E2E, full-flow keyboard/resize/error inspection, minimum terminal sizing, statuses and focus; implement deterministic release verifier/wheelhouse setup; final CI matrix. Keep scope fixed; repair root causes.
**Tests:** full suite/lint/build/twine/comparisons, every release verifier step and no-network mode, visual/PTY checks, bounded-input performance guard.
**Docs:** README supported environments, installation/troubleshooting/privacy/limitations; screenshots; acceptance evidence; BUILD_LOG.
**Complete when:** every acceptance ID has passing evidence or an explicit blocker (a blocker prevents P10 completion).
**Commit boundaries:** "test: verify installed workflows and adversarial cases"; "fix(tui): complete keyboard and responsive polish".

## P10 — Release evidence and handoff
**Depends:** P09, all acceptance gates passed.
**Objective:** a reviewable V1 release candidate, not a merge/publish.
**Work:** final verification on release candidate, clean git audit, documentation consistency, write V1_BUILD_REPORT with full architecture/scope/tests/install/export/UX/limitations/review hotspots. Follow non-self-referential SHA protocol in CODEX_EXECUTION.
**Tests:** final TEST_PLAN commands and both supported CI versions; rerun relevant checks for any fixes, never reuse stale evidence after code changes.
**Docs:** acceptance matrix evidence, final BUILD_LOG and report, README final verified scope.
**Complete when:** code candidate is immutable and verified; final evidence-only commit exists; working tree has no unexplained changes; user receives SHA/branch/report and honest remaining limitations.
**Commit boundary:** "docs: record verified MLForge V1 release candidate".

A phase blocked after three serious repairs follows CODEX_EXECUTION; do not jump to a later phase, reduce scope, weaken tests or report success.
