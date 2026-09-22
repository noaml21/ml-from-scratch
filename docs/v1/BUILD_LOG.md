# MLForge V1 build log

Current pointer: [BUILD_STATE.md](BUILD_STATE.md). This file records historical events and phase evidence; it is not a second mutable resume pointer.

## Planning baseline — COMPLETE (not a V1 implementation)
- Date: 2026-09-18.
- Source: ml-from-scratch main 93272b473b6079960e903b45bd3a625c0d19be59.
- Reference: linux-concurrency-ipc v3/reliable-ipc-lab 4711931ec1eca8238cc3aa2e4838263182f08fec.
- Branch: planning/mlforge-v1.
- Scope: audit and documentation only; original production/test/demo/dependency files unchanged.
- Initial system/bundled Python test attempts: pytest unavailable.
- Created ignored repository-local .venv and installed unchanged requirements.txt for baseline verification.
- Baseline: CPython 3.12.3; NumPy 2.5.3; sklearn 1.9.1; SciPy 1.18.1; pytest 9.1.1; Matplotlib 3.11.2.
- Commands: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -v -p no:cacheprovider → 15 passed; .venv/bin/python -m pip check → no broken requirements.
- Three comparison scripts completed successfully; research-only six-pipeline skops roundtrip passed after narrowly reviewing numpy.dtype and sklearn.tree._tree.Tree (forest-specific); initial empty trust was correctly refused. Details: PLANNING_REVIEW.md.
- Planning commit: resolve with git log --oneline planning/mlforge-v1; exact planning tip is the base for implementation.
- Planning verification: all 16 Markdown files/link/fence checks passed; 10 complete phase records and 26 unique acceptance IDs; git diff --check passed; production/test/demo/asset/requirements diff empty.
- No V1 feature has been implemented or release-verified.

## Phase ledger — planning snapshot, no implementation completed
| Phase | Status | Commit | Next action |
|---|---|---|---|
| P01 | NOT STARTED | — | Read all specs; branch from planning tip; baseline/package foundation |
| P02 | NOT STARTED | — | Await P01 |
| P03 | NOT STARTED | — | Await P02 |
| P04 | NOT STARTED | — | Await P03 |
| P05 | NOT STARTED | — | Await P04 |
| P06 | NOT STARTED | — | Await P05 |
| P07 | NOT STARTED | — | Await P06 |
| P08 | NOT STARTED | — | Await P07 |
| P09 | NOT STARTED | — | Await P08 |
| P10 | NOT STARTED | — | Await P09 |

## Phase entry template
### Pxx — title
- Status:
- Started-from SHA:
- Objective / files changed:
- Decisions and canonical documentation updated:
- Tests / exact commands / environment / results:
- Acceptance IDs and evidence:
- Repair attempts (hypothesis, change, outcome):
- Commit subject / SHA once available:
- Remaining risks:
- Next exact action:
- Completed work-unit IDs and corresponding BUILD_STATE update:

## Planning refinement — verified documentation change
- Scope: continuation protocol, one reusable start/resume prompt, one Current checkpoint, 30 work units inside the same 10 phases, and explicit intuitive/color/contrast/focus UX gates.
- Files: AGENTS.md; docs/v1/{README,RESUME_PROTOCOL,CODEX_PROMPT,CODEX_EXECUTION,BUILD_LOG,IMPLEMENTATION_PLAN,UX_FLOW,TEST_PLAN,ACCEPTANCE_CRITERIA,PLANNING_REVIEW}.md.
- Validation: inline Python checker passed for 18 Markdown files, local links/fences, 10 complete phases, 30 unique work units, 28 ordered acceptance IDs and one Current checkpoint/prompt.
- Commands: git diff --check passed; PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider completed, exit 0, 15 passed on the existing Python 3.12 project environment.
- Commit subject: docs: add interruption recovery and explicit UX quality gates (resolve SHA from Git history).
- All implementation phases remain NOT STARTED. Current next unit is P01.1.

## Planning recovery — 2026-09-18
- Recovered local commit 455553b3a5fe803fc8a032d4970b1d8e04eb3236 after approved 046621f19aa583e797246d7552c3ecf0e0ef9fa5. Branch planning/mlforge-v1; status/staged/unstaged/untracked inventories empty before edits. Remote remained at 046621f; earlier refinement had not been pushed.
- Preserved the completed refinement. Its former current checkpoint (observed HEAD 046621f, P01.1 NOT STARTED, no implementation commit) is superseded by BUILD_STATE; this history and Git retain the original observation.
- Added BUILD_STATE and DESIGN_SYSTEM; updated resume/authority/handoff/phase/test/acceptance/index pointers and planning coverage. Original production, tests, dependencies, demos and assets remain untouched.
- Resolved export nested-member limit conflict using an in-memory 100-tree forest archive probe: 502 members; canonical limits and related tests updated without adding features.
- Implementation remains NOT STARTED. Current action belongs only in BUILD_STATE. Planning commit subject: docs: separate resumable state and define terminal design system.
- Final pre-commit verification: `python3 docs/v1/verify_planning.py` passed: 20 Markdown files/local links/fences, index ownership, 10 phase contracts, 30 units, 28 mapped acceptance IDs, 21 default palette pairs. Initial contrast failure for error/selected was repaired by darkening selected background and rerunning the checker.
- Baseline command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` → exit 0, 15 passed. `git diff --check` passed. Scoped diff against 93272b for src/tests/demos/assets/requirements.txt was empty. Inspected final planning diff and new state/design/checker files.
- Delivery commit is identified by the subject above; its exact SHA and remote equality must be verified after commit/push, not invented inside its own contents. No actual TUI, recovery-fixture or installed-export acceptance is claimed by planning checks.

## Pre-implementation architecture review — 2026-09-18
- Started from clean planning/mlforge-v1 at approved 87a7d83d660ecb3f0267719667403859ced8b53c; inspected tracked tree, original source/tests, all planning documents, status and diff before edits.
- Findings: shared-contract placement, fitting versus process ownership, and practical extension/change guidance needed clarification. Canonical decisions and tradeoffs are recorded in PLANNING_REVIEW's final architecture review.
- Added docs/HOW_IT_WORKS.md with control/data diagrams and Train/Try/export walkthrough; docs/EXTENDING_MLFORGE.md covers seven extension types with change locations and required tests.
- Clarified contracts.py, tasks.py, training.py and execution/ in ARCHITECTURE, allowed import directions, immutable parent handles and descriptor ownership. Added a planned stdlib-AST pytest guard in P02 and its tests/acceptance mapping; the guard itself is not implemented on this planning branch.
- Updated AGENTS, root/index navigation, execution/handoff instructions, phase plan, acceptance/test plan and current state. Planning checker now covers both new guides as well as docs/v1. All product scope, model/importer/export choices and ten phases remain unchanged.
- Commit subject: docs: clarify architecture boundaries and extension workflows.
- Verification: `python3 docs/v1/verify_planning.py` → PASS, 22 Markdown files including both guides, local links/fences, 10 phases, 30 units, 28 acceptance mappings, 21 palette pairs; `git diff --check` → pass.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` → exit 0, 15 passed. Scoped Git diff of src/tests/demos/assets/requirements.txt against both approved 87a7d83 and baseline 93272b was empty. Reviewed new guides, final architecture and all affected documentation for consistency. No product code or new architecture test was implemented.

## P01.1 — baseline and branch verified (2026-09-19)
- Started from clean planning/mlforge-v1 at 0798b5b7d7ae07b0bd9fe454b3ddf90eba5434d5. All canonical specifications and both practical guides read before coding.
- Remote ls-remote confirms that exact planning SHA and no existing implementation branch. Created v1/mlforge at the supplied base; main untouched.
- Ubuntu 24.04.5 x86_64, CPython 3.12.3: `.venv/bin/python -m pytest -v` → 15 passed; `.venv/bin/python -m pip check` → no broken requirements.
- `.venv/bin/python demos/kmeans_comparison.py`, `demos/logistic_regression_comparison.py`, `demos/pca_comparison.py` → all exit 0; cost 47.699582, test accuracy 0.9200, reconstruction MSE 0.00407484 match sklearn.
- Sandbox DNS/.git writes required approved escalation; both succeeded. No production changes in this unit. A01 ancestry and A02 baseline evidence only; P01 phase remains in progress.
- Next unit P01.2: package metadata/bootstrap, constrained dependencies and installed namespace checks.

## P01.2 — packaging foundation locally verified (2026-09-19)
- Started from planning base 0798b5b7d7ae07b0bd9fe454b3ddf90eba5434d5 on v1/mlforge; no prior implementation.
- Added pyproject.toml, MANIFEST.in, src/mlforge/{__init__,__main__}.py, tests/mlforge/test_bootstrap.py, runtime/dev constraints, scripts/verify_package.py and .github/workflows/verify.yml. Updated .gitignore, README, canonical architecture/audit/index and both practical guides with honest implementation status. No TUI/services claimed.
- Resolved 24 runtime and 60 development/demo dependency pins from installed distribution metadata and transitive requirements (including extras and both Python markers); core versions: NumPy 2.5.3, SciPy 1.18.1, sklearn 1.9.1, skops 0.15.0, Textual 8.2.8, setuptools 82.0.1. No license grant or publication.
- `.venv/bin/python -m pip install --no-cache-dir -e '.[dev,demos]'` → exit 0 after approved project-local dependency installation. Reinstalled with constraints, --no-index, prepared wheelhouse and --no-build-isolation → exit 0.
- `.venv/bin/python -m pytest -q` → 18 passed; Ruff check/format, pip check, planning checker and git diff --check → pass. Bootstrap is exercised in fresh subprocesses with Textual/Rich explicitly blocked.
- `.venv/bin/python scripts/verify_package.py --prepare-wheelhouse` → exit 0 (setup network); ordinary verifier → exit 0 with indexes disabled: wheel and sdist-derived isolated installs, entrypoints, package namespace location, pip check. Local-only report `.mlforge-build/package-3.12.json`; no Python 3.13 claim yet.
- Build and twine metadata checks passed. Manifest review found baseline tests in sdist without their educational source; added explicit manifest inclusions and repeated both isolated installs successfully. Scoped legacy source/test/demo/asset/requirements diff is empty.
- Formatting issues on first generated batch repaired using scoped Ruff formatting; subsequent checks pass. An overlapping repeat of isolated verification used separate owned temporary environments; both completed successfully. No operations remain from those checks.
- Commit subject: build: establish MLForge package and preserve educational baseline (SHA recorded next checkpoint). P01 remains IN PROGRESS pending CI and continuation rehearsal; A03/A24 release acceptance is not complete.

## P01.3 — CI baseline and recovery rehearsal in progress
- GitHub Actions permissions API reports enabled/all actions allowed. Workflow targets Ubuntu 24.04 x86_64 and Python 3.12/3.13, full suite/lint/build/metadata/comparisons plus isolated app installations. Remote job results remain pending.
- Reconstructed P01.3 and completed P01.2 from BUILD_STATE, IMPLEMENTATION_PLAN and Git alone; confirmed immutable planning ancestry. SHA-256 before/after checks preserve dirty checkpoint/log/bootstrap/manifest/package files. Next action correctly remains commit/push then two-Python CI, not P02. Local-only evidence: `.mlforge-build/recovery-p01.json`. P09 must still test the richer synthetic recovery cases.
- Final local foundation verification: `PIP_NO_INDEX=1 PIP_FIND_LINKS="$PWD/.mlforge-build/wheelhouse" .venv/bin/python -m build` → exit 0 (isolated backend resolved offline); twine both artifacts passed; full pytest 18 passed; Ruff check/format passed. Local-only build output `.mlforge-build/build.log`.
- P01.1/P01.2 local gates and P01 continuation rehearsal pass. P01.3 awaits both CI results and cannot yet advance.

- Foundation commit: 536fb0de964e294372f555e6a849e9aba7f35a07; normal push to origin/v1/mlforge succeeded. CI [35410007123](https://github.com/noaml21/ml-from-scratch/actions/runs/35410007123) queued for that exact SHA. No phase gate inferred from queue status.

## P01 — VERIFIED / P02.1 started
- CI run [35410007123](https://github.com/noaml21/ml-from-scratch/actions/runs/35410007123) completed successfully for both Python 3.12 and 3.13 on Ubuntu 24.04 at 536fb0de964e294372f555e6a849e9aba7f35a07. Both jobs passed suite, lint/format, dependency check, build/twine, original comparisons, isolated wheel/sdist installations and planning checker. P01 phase gate passes.
- P02.1 first batch: immutable dataset/core records, concrete six-model registry and stdlib AST dependency/cycle guard with positive/negative fixtures. P02.2/P02.3 will implement shared runtime/persistence and independently installed six-model wheels; no such evidence exists yet.

## P02.1 — typed records, factories and architecture guard VERIFIED
- Started from 536fb0de964e294372f555e6a849e9aba7f35a07 after both P01 CI jobs passed. Added contracts.py, datasets/records.py, models.py and tests/mlforge/test_{architecture,contracts}.py; updated canonical architecture and practical guides.
- Dataset nested input sequences are copied into tuples; experiment structural checks reject target inclusion, duplicate/empty features/models and task/target mismatch. Parent bundle records contain immutable metadata strings/hashes, not estimators. Six model factories import sklearn lazily and use ML_PIPELINE defaults.
- Stdlib AST guard tests absolute/relative/nested/type-only edges, initializer reexports, cycles, standalone runtime direction, UI bypass, direct presentation imports and dynamic/star imports (including aliases). Fresh subprocess headless imports include all present non-TUI modules.
- `.venv/bin/python -m pytest -q` → 43 passed; Ruff check/format → pass; `.venv/bin/python -m build --no-isolation` and twine → pass; planning checker and git diff --check → pass. Build evidence local-only `.mlforge-build/build-p02.1.log`.
- Initial default test incorrectly required PCA.random_state=42 despite specified deterministic full SVD; corrected the test to the canonical PCA configuration. No estimator default changed. Formatting repaired before commit.
- Commit subject: feat(core): define task and prediction contracts. Unit passes; P02 phase remains in progress. Next: P02.2 shared standalone runtime, schema/persistence and wheel exporter; P02.3 must prove all six installed roundtrips before P03.

- P02.1 commit 23fcd0800cb6334719c211a7529858884c40e88d pushed normally. P02.2 source review of installed skops 0.15.0 confirms DTypeNode reconstructs dtype through an array and TreeNode deliberately requires explicit trust because native inference indices are unchecked. Retain the specified numpy.dtype plus forest-only sklearn.tree._tree.Tree allowlist; validate tree structure before inference. No new trusted types approved.

## P02 recovery and checkpoint reconciliation (2026-09-19)
- User continuation request confirmed existing checkout and implementation HEAD 23fcd0800cb6334719c211a7529858884c40e88d. Git branch/status/history/unstaged/staged/untracked inventories inspected; planning ancestry verified. No staged files, no reset/stash/discard/restart.
- Preserved substantial uncommitted prediction/runtime/schema, preprocessing builder, exporter/template and tests, pyproject resources and architecture-test edits. Earlier BUILD_STATE was stale and incorrectly described P02.2 as unwritten; corrected against actual files.
- Collected previous session 3953: tests/mlforge/export/test_wheel.py → exit 0, 28 passed. Earlier runtime/security subset: 53 passed. User independent review reports full 124 passed and checks passed; rerun after repairs rather than treat it as future evidence.
- Reproducible review defect to repair: repeated/trailing underscore modules pass validation but wheel/distribution paths disagree with setuptools. P02.3 fresh consumer installs remain absent and mandatory; ZIP-path parity is not installation evidence.
- Next unit work remains P02.2 normalization/security completion, then P02.3 six installed model wheels; no phase advance yet.

- Export normalization regression reproduced: both classification.logistic/foo__bar and foo_ failed before repair. Added separate canonical distribution/wheel stem handling, retained import modules, and guarded normalized dependency collisions; canonical EXPORT_SPEC records trailing separator handling.
- Continued P02 security review tightened archive path canonicalization, CPython identity, schema/model feature-count checks, forest leaf sentinels and dtype/branch bounds. Runtime/security subset after these changes: 53 passed. A normalization run overlapped these runtime edits and is invalid as final evidence; collect it then rerun against stable source.

## P02.2 — shared inference and verified wheel generation VERIFIED
- Preserved and completed the uncommitted slice from 23fcd08: prediction/runtime.py + schema.py, preprocessing.py, export/wheel.py + fixed init template, package resource metadata, synthetic fixture/runtime/security/export tests and the headless architecture fixture.
- Input normalization, missing/category sentinel, strict numeric/boolean checks, whole-batch validation and task-aware Predictor/transform APIs share one standalone source. Exact fitted bundles retain only learned state and allowed metadata.
- Fixed type allowlist remains numpy.dtype plus forest-only sklearn.tree._tree.Tree. Tree array shape, finite values, indices, leaf markers, depth/count, reachability and acyclicity are checked before inference. Both outer and nested archives have independent limits/path checks. Environment/hash failures precede deserialization.
- Corrected repeated/trailing underscore module exports with separate distribution/wheel naming. Both failures reproduced before fix; 18 real wheel cases now cover six models × three module names. Module imports are preserved; normalized reserved distributions and no-overwrite policy are enforced. EXPORT_SPEC records the uncovered trailing-separator detail.
- Added METADATA/WHEEL/RECORD checks. setuptools reorders Requires-Python constraints; comparison uses SpecifierSet equality, preserving exact compatibility policy. Bundle resource hashes/metadata are rechecked at copying.
- Source-reviewed sklearn’s optional Rich import fallback: headless blocker now raises ModuleNotFoundError and asserts no UI modules loaded; AST still rejects direct presentation dependencies. Verified inference closure: cloudpickle, joblib, narwhals, numpy, packaging, prettytable, scikit-learn, scipy, skops, threadpoolctl, wcwidth.
- Final stable run session 87032: `.venv/bin/python -m pytest -q` → 141 passed in 192.24s; Ruff check/format, build --no-isolation, twine wheel/sdist, verify_planning.py and git diff --check → all exit 0. Local-only reports .mlforge-build/pytest-p02.2.log and build-p02.2.log. No critical skip/xfail. Duplicate-name warning is explicitly expected inside its adversarial fixture.
- Earlier overlapping source-edit/test run correctly failed parity/source-equality checks and was discarded as verification evidence; stable full rerun passed. No weakened assertion.
- P02.1 remote CI [35410459118](https://github.com/noaml21/ml-from-scratch/actions/runs/35410459118) also passed at 23fcd08.
- Commit subject: feat(export): preserve shared inference and validate model wheels. P02 phase remains IN PROGRESS; P02.3 must install and infer with all six wheels in fresh consumer environments outside the checkout.

- P02.2 committed and pushed normally as 294307401805071fc216a7a7375667724b1775d9. P02.3 begins with real consumer installs; verification must run outside checkout with complete dependency resolution, no app/UI packages, and a network-attempt guard.

## P02.3 — clean consumer installation matrix IN PROGRESS
- Added tests/mlforge/export/test_install.py: six actual independent venvs under pytest-owned temporary paths outside checkout, no source import path or system-site packages, pip --no-index with prepared wheels, pip check, real task API and numerical/warning parity. Uses both repeated/trailing underscore import modules.
- Consumer asserts MLForge/Textual/Rich absent, exact inference dependency versions, no refit, input/batch/task errors, metadata copies, Python mismatch and resource hash rejection. A venv-local sitecustomize audit hook exits 93 on attempted network operations during pip or inference; no exceptions can hide attempts.
- Updated CI preparation before full pytest and consumer evidence artifact paths. Documentation explains missing wheelhouse is a failure, not a skip.
- Long verification: `.venv/bin/python -m pytest -q tests/mlforge/export/test_install.py` running as session 65608; output .mlforge-build/install-p02.3.log; result UNKNOWN until collected. No P02 phase completion claimed.

## P02.3 continuation reconciliation
- Re-read AGENTS/RESUME_PROTOCOL and inspected Git/checkpoint/log on user continuation. HEAD remains 294307401805071fc216a7a7375667724b1775d9 on v1/mlforge; no staged changes. Preserve install test, CI/docs/checkpoint edits and newly observed unrelated untracked CLAUDE.md.
- Prior session 65608 is unavailable after tool-runtime reset; saved log ends `6 passed in 119.63s`, and all six consumer evidence JSON files exist. This is positive test evidence but no recoverable process return code. Full required suite will rerun with durable recorded return codes; no inference of phase completion from the missing process.

## P02.3 — local consumer gate VERIFIED; CI pending
- Collected session 27826 exit 0 and durable per-command return codes in .mlforge-build/checks-p02.3.json. Full pytest: 147 passed in 367.06s; Ruff check/format, build --no-isolation, twine check, pip check, verify_planning.py and git diff --check all passed. Six consumer-12-*.json reports confirm isolated installation and task inference with no app/UI dependencies or network attempts.
- P02.2 CI [35436143083](https://github.com/noaml21/ml-from-scratch/actions/runs/35436143083) passed for both supported Python versions. New P02.3 tests still require their own CI evidence.
- Reviewed test, workflow, prerequisite docs and diff. Replaced stale checkpoint with actual current pointer; historical pre-implementation evidence remains solely in BUILD_LOG. Preserved external untracked CLAUDE.md unchanged.
- Next: commit test/export installation matrix and documentation, push normally, verify both CI jobs before P03. No full V1 acceptance claim.

- P02.3 committed/pushed as 67c36cd31cd3166528f344b2c55067280cf1f6d1. CI [35450096351](https://github.com/noaml21/ml-from-scratch/actions/runs/35450096351) running at that SHA; local-only checkpoint records pending gate.

## P02 VERIFIED / P03.1 started
- CI [35450096351](https://github.com/noaml21/ml-from-scratch/actions/runs/35450096351) completed successfully for Python 3.12 and 3.13 at 67c36cd31cd3166528f344b2c55067280cf1f6d1. Both run all six real isolated consumer installations, full suite, lint/build, original comparisons and app installation checks. P02 phase gate passes.
- P03.1 scope: bounded regular-file reads with identity checking, strict CSV/TSV/JSONL, immutable lexical cells, provenance and safe structural errors. Use existing records and no new dependencies. Targeted check: datasets importer matrix plus architecture guard. P03.2 inference/overrides/Prepare and P03.3 examples remain unwritten.

## P03.1 — bounded importers present, full verification pending
- Added datasets/importers.py and tests/mlforge/datasets/test_importers.py. Frozen format descriptors and explicit dispatch; regular-file/symlink identity checks with nonblocking/no-follow open; stat plus streaming byte bounds; strict quoting and column/cell/row/header bounds; safe UTF-8/JSON errors; immutable lexical cells and content/parser fingerprint.
- Explicit quote grammar supplements csv.reader(strict=True), which accepts quotes inside unquoted fields. JSON numeric parse hooks retain lexical tokens and reject nonfinite float64 values. No file paths are retained by dataset records or exported provenance.
- Targeted importer/architecture checks: 58 passed (session 46729 exit 0); Ruff check passed. Actual 20,000-row boundary, growth after stat, open identity races, permissions, FIFOs/devices, multiline locations and unchanged source bytes covered. Initial long fixture strings needed formatting repair; no runtime test failed.
- Starting full pytest/lint/format/build/pip/docs/diff checks; durable statuses .mlforge-build/checks-p03.1.json. P03.2/P03.3 remain incomplete.

- P03.1 full verification session 57006 completed exit 0: 188 passed in 408.06s; Ruff check/format, build/twine, pip check, planning checker and diff check all passed. Durable per-command evidence .mlforge-build/checks-p03.1.json. Reviewed importer/test/doc paths; commit subject: feat(data): add bounded canonical importers. Phase remains in progress; next unit P03.2.

- P03.1 committed/pushed as 437bc6d. P03.2 starts: datasets/inference.py interprets all bounded cells and creates schema statistics; validation.py owns atomic override/reset and preview/provenance helpers; prepare.py provides safe local text and exclusive save. Existing immutable records remain the seam. No model fitting or UI work.

## P03.2 — schema review and Prepare present, full checks pending
- Added full-table inference/profile services, pure scalar interpretation, atomic type override/reset, effective provenance, bounded preview and control escaping. Unknown/all-missing stays unusable; large integer and leading-zero warnings preserve raw values; compatible JSON number/text and boolean/text pairs retain semantic types, incompatible mixtures require acknowledgement or explicit override.
- Added stable structural Prepare prompt with format/diagnostic allowlists, no source-content arguments, local privacy note and private atomic no-overwrite .txt save. Failure leaves no partial final file. Null-byte path review found a safe-error gap in P03.1; importer now maps invalid paths without swallowing DomainError.
- Dataset/architecture checks: 88 passed, session 58882 exit 0; Ruff passed. Initial fixture import ordering corrected; no failing runtime assertion. Full suite/build/docs checks begin with durable .mlforge-build/checks-p03.2.json evidence; P03.3 remains incomplete.

## P03.2 VERIFIED / user-authorized verification cadence
- Reconciled branch/status/staged/unstaged/untracked/history and planning ancestry after continuation. P03.2 source already exists; preserved it and external CLAUDE.md. Collected existing session 71949 exit 0: 218 passed in 370.43s, all eight full verification commands passed; no duplicate full run launched.
- P03.1 CI [35450994927](https://github.com/noaml21/ml-from-scratch/actions/runs/35450994927) passed at 437bc6dce8611e6947fc71c7c598c16ab3940a57.
- User explicitly changed cadence: focused/subsystem tests and Ruff at work-unit boundaries; full/build/docs checks primarily at phase gates; installed-consumer repeats only for export/runtime impact or explicit gate. Updated CODEX_EXECUTION/TEST_PLAN and removed automatic push trigger from complete CI; explicit phase-gate dispatch and PR runs preserve the entire matrix. P09/P10 and acceptance remain unchanged.
- Reviewed production/tests/guides/cadence changes. Intended commit: feat(data): add schema review and preparation guidance. P03.3 examples/adversarial phase gate remains next; P04-P10 not started.

- P03.2 committed/pushed as f8bf94da2ccf20ffca26b818acf009c9932e2424. P03.3 starts with five deterministic synthetic package resources, formula provenance/reproduction checks, remaining adversarial data cases, and installed app resource proof. Use the same importer/schema path. Dataset phase gate excludes isolated model consumers because this unit has no export/runtime impact; complete non-consumer suite and app packaging run on both Pythons. P09/P10 retain all consumers.
- Initial P03.3 checkpoint script raised NameError before writing; immediately reconciled actual edits. Example files/generator, static descriptors, package-data and explicit CI consumer toggle are present but not yet tested. No tests or commits were claimed by the failed checkpoint.

## P03.3 — examples and adversarial dataset tests present
- Five packaged resources cover four tasks and mixed types across CSV/TSV/JSONL. scripts/generate_examples.py uses fixed row-index formulas; package README records provenance. Reproduction tests enforce exact bytes, schemas and source immutability. Static descriptors live beside importer format descriptors; no architecture edge added.
- Extended app wheel/sdist installation verifier to parse and infer all five installed resources. Added actual max column/header/escaped-quote boundaries and mid-read source mutation rejection. Targeted datasets/architecture: 96 passed in 6.30s, session 67254 exit 0; Ruff passed.
- P03 gate begins: full non-consumer suite (-m 'not install'), lint/format/build/twine/pip/docs/diff and isolated app wheel/sdist resource checks. Durable .mlforge-build/checks-p03-gate.json. Six exported-consumer installations are intentionally excluded under user cadence: dataset/resources do not change runtime/export; mandatory P09/P10 remains complete. CI dispatch has explicit consumer_installs boolean default true, false only for this applicable gate.

- P03.3 local phase gate session 85301 exit 0: 220 tests passed, six isolated model-consumer tests intentionally deselected under the user cadence; Ruff check/format, build/twine, pip check, planning checker, diff check and isolated app wheel/sdist installs passed. Both installed app variants parsed/inferred all five packaged resources. Evidence .mlforge-build/checks-p03-gate.json, p03-gate-*.log, package-3.12.json.
- Reviewed descriptors, generation formulas/resources, tests, packaging/verifier and cadence docs. Commit subject: feat(data): ship verified synthetic example datasets. P03 remains in progress until both supported CI jobs pass at this candidate; next action explicit workflow dispatch with consumer_installs=false.

- P03.3 committed/pushed as c2e395a6dc24d0248cd76c7816eddfeca4221f9b. Explicit CI [35465790338](https://github.com/noaml21/ml-from-scratch/actions/runs/35465790338) running with consumer_installs=false; no phase completion inferred from dispatch. External CLAUDE.md preserved untracked.

## P03 VERIFIED / P04.1.a starts
- CI [35465790338](https://github.com/noaml21/ml-from-scratch/actions/runs/35465790338) completed successfully on Python 3.12 and 3.13 at c2e395a6dc24d0248cd76c7816eddfeca4221f9b. Both run complete non-consumer tests, lint/build/metadata/comparisons, installed app wheel/sdist examples and docs checks. Model-consumer exclusions are intentional per cadence; prior P02 proof remains intact. P03 phase gate passes.
- Split P04.1 into P04.1.a task/target/feature eligibility and leakage warnings, then P04.1.b shared split and preparation plan. P04.2 fits transforms/model gates; P04.3 evaluates/persists candidates. First scope: tasks.py and tests/mlforge/pipeline/test_eligibility.py, using existing schema statistics and contracts; no dependency-edge change. Focused tests/Ruff before commit, broad gate later.

## P04.1.a VERIFIED — eligibility and review policy
- Added tasks.py with immutable task/choice/warning descriptors, target eligibility and stable labels, suggested/all-column views, feature defaults/exclusions, unsupervised option bounds, duplicate/equality/name warnings and explicit acknowledgement validation. Uses only permitted contracts/dataset records. Numeric classification label conversion refuses nonintegral input rather than silently truncating.
- Added pipeline/test_eligibility.py: row/class/type/missing boundaries, no all-column bypass, Category override and label semantics, disabled/default features, k/PCA bounds, target exclusion, warning acknowledgement, mixed target correction and high-cardinality/long-text behavior.
- Focused eligibility + datasets + architecture run session 22158: 115 passed; scoped Ruff check/format passed. Repaired only initial long-string/import formatting; no failing runtime test. Under user cadence no consumer/full-build rerun.
- Review complete; commit subject: feat(ml): validate task targets and feature selections. Next P04.1.b shared deterministic split and preparation plan; fitting/evaluation remain incomplete.

- P04.1.a committed/pushed as 66c6b0c. P04.1.b starts: prepare one deterministic split/policy in preprocessing.py, use shared runtime normalization for canonical records, enforce matrix bounds before allocation, and add focused split/no-fit tests. No learned preprocessing during preparation.

## P04.1.b VERIFIED — shared split and unfitted preparation
- Extended preprocessing.py with prepare_run, ordered raw-record/field/matrix helpers and pre-allocation feature/byte guards. Canonical inputs pass through the existing shared runtime normalizer. Preparation never fits; all candidates retain the same immutable train/test indices, effective schema, environment and policy.
- Classification uses one stratified shuffled holdout; regression the same shuffled size/seed policy; integer arithmetic computes ceil(n/5). Checks preserve every row exactly once and require every class in both partitions. Unsupervised preparation retains all rows and labels scope explicitly. Dataset fingerprint/schema column mismatch is rejected.
- Added pipeline/test_split.py: deterministic candidate-order-independent splits, no transform fitting, holdout-only perturbations cannot enter policy/ranges/vocabulary, target exclusion, stateless missing/category parity, all-row exploration, memory/feature limits before allocation, corrupt/impossible splits and stale inputs.
- Focused pipeline + architecture + prediction-runtime run session 29360 exit 0: 79 passed; scoped Ruff/check-format and diff check passed. Existing build_pipeline/export/runtime implementation unchanged, so no isolated consumer repeat under cadence.
- Intended commit: feat(ml): prepare shared deterministic row splits. Next P04.2 fits each candidate's transforms/models only on permitted rows; P04.3 evaluation/persistence still incomplete.

- P04.1.b committed/pushed as 13461ad7116cc352f42e5166fadb1813caf06da6. P04.2 starts: training.fit_pipeline fits standard preprocessing once on train rows, checks transformed bounds/variance/distinct rows before estimator fitting, and retains those exact fitted steps in the standard sklearn Pipeline. This ordering enables pre-estimator degeneracy gates without a duplicate fit. No custom serialized types, alternate runtime or process logic. Focused real-model/no-leakage tests before commit; evaluated bundle/export integration remains P04.3.

## P04.2 VERIFIED — per-candidate fitted pipelines
- Added training.fit_pipeline: shared confirmed inputs, fresh six-model factory/pipeline, training-only standard preprocessing fit once, transformed matrix bounds/finite/constant checks, k distinct-row gate, estimator fit once, safe warning capture and convergence rejection, actual cluster-count check, PCA rank-deficient output note. Thread pools are bounded without process lifecycle logic.
- Exact fitted standard steps remain in the Pipeline; no custom serialized class or refit. Fitting preprocessing before the estimator allows required degeneracy rejection before native fitting. Each candidate uses only PreparedRun.train_rows; holdout is untouched by learned transforms.
- Added real six-model reproducibility + skops restore tests, holdout median/scale/vocabulary sentinels, unknown category inference, train-all-missing zero fallback, constant/distinct rejection, convergence/stale environment/task errors and rank-deficient PCA explanation.
- Focused pipeline + architecture + prediction runtime session 86836 exit 0: 91 passed in 12.75s; Ruff/check-format and diff check passed. Installed model consumers deferred to the P04 evaluated-bundle phase gate.
- Code review noted runtime's 2 MiB schema resource cap is narrower than dataset/archive budgets; not yet reproduced with a real large vocabulary. Investigate in P04.3 integration instead of silently advertising universal export coverage.
- Intended commit: feat(ml): fit isolated training-only candidate pipelines. Split next oversized unit into P04.3.a evaluation/diagnostic/ranking functions, P04.3.b evaluated bundle integration/resource review, then P04.3.c full phase gate. No later phase started.

- P04.2 committed/pushed as 6375e64. P04.3.a starts: pure evaluation/diagnostics/ranking in evaluation.py and independent metric fixtures. No widgets, estimator fitting or process ownership in evaluation.

## P04.3 continuation reconciliation
- Read AGENTS, RESUME_PROTOCOL, BUILD_STATE, plan/execution protocol and active owners; actual branch v1/mlforge and HEAD 6375e645d874f04afa3c11766ff42002172bc8ec confirmed, planning ancestry retained. P04.2 is committed/pushed; checkpoint's uncommitted description was stale.
- Preserved untracked partial evaluation.py and external CLAUDE.md, with existing state/log edits; no staged files and no reset/stash/discard. Partial evaluation has no tests yet and one known Ruff long-line defect; no active local check to duplicate.
- Correct next action remains P04.3.a evaluation verification, then evaluated-bundle integration and evidence-based schema-cap investigation. 11 of 30 top-level work units completed; P05-P10 not started.

## P04.3.a VERIFIED — metrics, diagnostics and ranking
- Completed preserved evaluation.py and added pipeline/test_metrics.py with hand-calculated classification/confusion/baseline, regression negative/undefined R² and train-mean baseline, silhouette degeneracy/sampling, PCA reconstruction and deterministic ranking cases. Nonfinite/overflow values fail safely. No dependency edge changed.
- Updated ML_PIPELINE and practical guides to distinguish implemented metric services from pending evaluated-bundle orchestration. Resume confirmed remote HEAD 6375e645d874f04afa3c11766ff42002172bc8ec and preserved external CLAUDE.md.
- Focused pipeline + architecture: 72 passed in 11.22s (session 78135), rerun after resume 72 passed in 9.13s (session 50421, exit 0). Scoped Ruff/check-format and git diff --check passed. No full build/consumer repeat for pure metric unit.
- Reviewed paths; intended commit: feat(ml): evaluate task metrics and rank candidates. Next P04.3.b exact evaluated bundles and real schema-cap reproduction; phase gate remains incomplete.

- P04.3.a committed/pushed as 14719ee. P04.3.b starts with real large-vocabulary reproduction, then training/evaluation/persistence integration. Preserve archive security budgets and exact fitted objects. Test all six models through immutable handles and real clean consumers before P04 gate.

- P04.3.b reproduced schema-cap defect before repair: legal CSV 3,024,021 bytes, 1,000 rows, acknowledged HIGH_CARDINALITY/LONG_TEXT; 800 training rows yielded 2,413,789-byte schema and 3,060,721-byte model, but runtime rejected RESOURCE_LIMIT. Local evidence .mlforge-build/schema-cap-probe/evidence.json. Small repair reuses MAX_EXPANDED for schema reads; archive checks unchanged.
- Integrated training.train_candidate with evaluation, train-only fitted schema, existing save/load validation and immutable CandidateResult. Added retained metric reasons and review acknowledgement metadata. New real canonical six-model consumer fixture replaces provisional fitting only for consumer installation tests; original persistence fixtures remain.
- First focused bundle + architecture tests: 37 passed in 29.04s (session 34970, exit 0), including valid large-vocabulary export, single fitting, repeatable metrics/metadata, holdout-only category/range exclusion, fallback and safe failure. One test-fixture long line repaired; no functional test failures. Subsystem + six consumer installs are the next verification.

- P04.3.b local verification and P04.3.c local phase gate combined to avoid duplicate expensive installs: full pytest (includes six real evaluated clean consumers), all Ruff/format, build/twine/pip, three educational demos, planning/diff and app wheel/sdist verification. RUNNING evidence .mlforge-build/checks-p04-gate.json; CI dispatch follows a verified pushed candidate. No P05 work until both CI jobs pass.

## P04.3.b VERIFIED / P04 local phase gate VERIFIED
- Full local gate wrapper session 23193 exit 0: 301 tests passed in 430.89s, including all six real evaluated model consumer installations outside the checkout with MLForge/Textual/Rich absent, exact dependency checks, network guard and parity. No skipped tests. Python 3.12.3, committed constraints.
- Ruff check and format, app wheel/sdist build, twine check, pip check, all three original educational comparison scripts, verify_planning.py, git diff --check and isolated app wheel/sdist installations passed. Both installed app variants loaded the five packaged examples. Evidence .mlforge-build/checks-p04-gate.json, p04-gate-*.log, package-3.12.json and consumer-12-*.json.
- Reviewed production diff, test coverage, archive budgets/privacy and architecture boundaries. No new dependency edges, no change to educational code/assets or main. External CLAUDE.md remains preserved/untracked.
- Intended commit: feat(ml): retain exact evaluated candidate pipelines. P04 remains IN PROGRESS until both supported CI jobs pass on the pushed candidate; no P05 implementation started.

- P04.3.b committed/pushed as a1e0888172b923c6274d1f9950f45c21ace78c1f. Required CI [35500751982](https://github.com/noaml21/ml-from-scratch/actions/runs/35500751982) dispatched with consumer_installs=true; both supported jobs pending. Phase completion is not inferred from dispatch.

## P04 VERIFIED — complete supported-environment phase gate
- CI [35500751982](https://github.com/noaml21/ml-from-scratch/actions/runs/35500751982) succeeded at exact production SHA a1e0888172b923c6274d1f9950f45c21ace78c1f. Python 3.12.14: 301 tests passed in 151.05s; Python 3.13.15: 301 passed in 175.36s. Each job also passed Ruff/format/build/twine, pip check, all three educational comparisons, isolated wheel/sdist app installs/examples and planning verification. No required test omitted; consumer_installs=true.
- Downloaded two package reports and twelve consumer reports under local-only .mlforge-build/p04-ci-artifacts; all consumers report passed parity, clean dependencies and active network guard with zero attempts. CI JSON/log retained as p04-ci.json/p04-ci.log. CI watch session 37421 exit 0.
- All four task types/six models now fit, evaluate and retain exact pipelines; headless invalid-configuration, leakage, degeneracy, unknown-category, immutable-handle, ranking and reproducibility evidence passes. Core evidence contributes to A11-A13, A16-A17 and A19-A21; their later UI/process/release obligations are not claimed complete.
- CI has a nonblocking Node 20 deprecation annotation for the existing v4 actions; runner executes them on Node 24 and both jobs pass. No P04 blocker remains. No architecture/dependency-boundary relaxation, no scope expansion, no main modification or package publication.
- Updated README implementation status and current pointer. Intended evidence-only commit: docs: checkpoint verified P04 pipeline phase. Progress 12/30 units; P05-P10 remain. Exact next action P05.1: reconcile Git, read lifecycle/protocol owners, checkpoint scope and implement headless validated operation records/codecs and worker ownership before UI. External CLAUDE.md remains preserved/untracked.

## P05 resume reconciliation — implementation NOT STARTED
- Actual branch v1/mlforge, local HEAD and remote both 8c6c6d4026d72dcc07a1dbfedb899a2464fd0097; immutable planning ancestry confirmed. No staged/unstaged changes on entry; external untracked CLAUDE.md preserved unchanged and excluded from commits.
- Read AGENTS, BUILD_STATE, RESUME_PROTOCOL, CODEX_EXECUTION, IMPLEMENTATION_PLAN and P05 owners ARCHITECTURE/UX_FLOW/TEST_PLAN. Confirmed execution/application modules do not yet exist; P05.1 is the correct next unit. No new implementation unit started.
- Rechecked saved P04 evidence: all 12 local gate commands exited successfully; both CI jobs passed at a1e0888. Resume architecture boundary check: .venv/bin/python -m pytest -q tests/mlforge/test_architecture.py, 17 passed in 5.10s, session 64259 exit 0. No reason to repeat full tests/build/consumer installs or CI for this documentation-only reconciliation.
- Updated the current pointer without altering scope or claiming implementation progress. Progress remains 12/30; P05-P10 pending. Next action: checkpoint P05.1 implementation scope, then validated protocol records/codecs and headless worker ownership, with focused protocol/ownership/architecture tests. Intended commit: docs: reconcile P05 resume checkpoint.

## P05.1.a starts — protocol and owned-file boundary
- Baseline 2176395075e97e1ee2a78bbd83d1d8d4030a1e05; user directs immediate implementation. Split P05.1 into .a bounded request/event/result codecs and owned-file validation, then .b headless service dispatch/worker integration. This preserves the approved coordinator/worker boundary without a generic RPC framework.
- Scope .a execution/protocol.py and tests/mlforge/execution/test_protocol.py; only contracts/stdlib dependencies. Parent chooses paths and identities; child output is provisional until successful exit and integrity validation. Targeted protocol/ownership + architecture tests before commit.

## P05.1.a VERIFIED — bounded wire and owned artifacts
- Added execution/protocol.py and minimal package initializer. Frozen request/result/event/identity/artifact records, strict versioned JSON and bounded JSONL, safe phase/error event fields, identity/sequence/terminal rejection, immutable nested payload representation and exact parent-assigned artifact acceptance. No domain services, UI, network or process launch in the module.
- Added owner-only dir-fd-based resource reads/writes with O_NOFOLLOW/nonblocking regular-file checks, hardlink refusal, byte/hash/change checks, atomic no-replace publication and cleanup of only the created temporary file. Acceptance requires successful exit, complete event stream, expected identity/output set and no cancellation. Coordinator lifetime/cleanup is not claimed implemented.
- Tests cover six operation envelopes, immutable copies, duplicate keys/deep/nonfinite/invalid Unicode JSON, byte/newline limits, malformed fields, wrong phases, stale/gapped/duplicate/terminal events, traversal/reserved paths, symlinks/hardlinks/FIFOs/private permissions, corruption, disk failure, unrelated sentinel preservation and completion/cancel/exit barriers.
- Focused execution + architecture checks: first 65 passed in 5.12s; after adding operation-phase/request-limit cases, 66 passed in 5.66s (session 69544 exit 0). Scoped Ruff check passed. Owner/guide updates document exact wire limits and distinguish implemented protocol from pending worker/coordinator/application. No dependency-edge change or export/runtime change; no expensive consumer/full/CI repeat.
- Reviewed code/test/doc paths; intended commit: feat(execution): validate wire records and owned artifacts. Next P05.1.b is headless worker dispatch/service codecs and ownership integration tests. P05.1 remains incomplete; 12/30 top-level units complete. No later phase started, no unverified partial edit, external CLAUDE.md preserved.

## P05.1.b starts — headless operation worker
- Reconciled local/remote f92583c5544a2d4b3acee6813aff16baff4e1cc3; only external CLAUDE.md untracked. P05.1.a verified commit is intact. Read continuation and P05 owners; no restart of completed phases.
- Implement concrete canonical data/contract codecs, explicit parse/inspect/prepare/train/predict/export dispatch and bounded event/result emission. Worker writes only parent-assigned private output resources; coordinator retains process/acceptance ownership. Tests use real operation children and adversarial malformed input/ownership cases.


## P05.1.b VERIFIED — concrete headless dispatch
- Preserved recovered partial worker/contracts/data-record edits. Recovered prior interrupted worker+architecture check: 28 passed, session 41579 exit 0. Local/remote base f92583c verified; external CLAUDE.md untouched.
- Worker explicitly dispatches all six operation kinds, preserves shared prepared splits and exact evaluated pipelines, validates parent-assigned private output sets and hashes, pins/revalidates its private root, and emits safe bounded events. Exit 0/1/2 distinguishes completed/service/protocol outcomes; process acceptance remains provisional.
- Concrete record codecs reject malformed structures, duplicate/nonfinite/deep metadata, corrupted fingerprints and invalid splits. Fixed a discovered revision coupling: dataset revision must not be equated with configuration/event revision. Real tests now deliberately use distinct revisions.
- Real worker tests cover all six models through preparation/train/prediction and logistic export; malformed/unsupported/oversized input, resource links/overwrite, service exceptions, invalid event/result serialization, private diagnostics and inherited worker network guard. Export descendant network/lifecycle verification remains part of P05's process gate, not claimed by a PYTHONPATH guard removed by the exporter.
- Focused adversarial/codec pass: 27 passed, 6 deselected. Subsystem completion: 186 passed in 139.99s (session 22282 exit 0), .mlforge-build/p05-worker-tests.log; Python 3.12.3 repository .venv. Scoped Ruff/check-format, planning verifier and diff checks passed. Full phase/CI and unrelated isolated consumers not repeated.
- Updated ARCHITECTURE and both practical guides without new dependency edges. Intended commit: feat(execution): dispatch validated headless operations. P05.1 complete, 13/30; immediately continue P05.2. No coordinator/application/UX completion claimed.


## P05.2.a starts — owned process supervision
- P05.1 worker committed as 4e2ebc4. Split P05.2 into .a generic process lifetime/transport/deadlines with real child tests, then .b serial orchestration/failure policy and export cancellation resource ownership. No new architecture edges.
- Coordinator owns one active process group and a private session directory. Linux subreaper ownership will allow exact owned-group descendant reaping after leader exit; unrelated children/resources must remain untouched. Focused real subprocess tests precede commit.


## P05.2.a VERIFIED — single-operation process ownership
- Added Coordinator and immutable Outcome; private session directory; one active operation; argument-array/start_new_session spawn; concurrent bounded stdout parsing and stderr counting; concrete operation deadlines; post-exit hash validation off the event loop; cancellation wins until acceptance after cleanup.
- Linux child-subreaper ownership collects orphaned descendants only with waitpid on the operation group. SIGTERM then two-second SIGKILL escalation; direct child/pipes/descendants reaped before return. A disappeared group is permanently released. Repeated task cancellation cannot abandon a pending spawn, validation or cleanup; cancelled close still removes owned session resources.
- Actual process tests cover responsive/ignoring workers, leader-exit-before-descendant, unrelated sentinel process/file, malformed/truncated/oversized output, crash after provisional completion, multi-megabyte stderr flood, timeout, cancel-before-start, completion/cleanup races, repeated cancellation/close, and disk failure before spawn.
- Initial 30 tests passed. Expanded check stalled due restricted sandbox denying asyncio background-thread wakeup, diagnosed with completed validation thread + sleeping event loop; stopped owned diagnostic runs. Authorized unsandboxed same check passed 34 tests in 18.87s. Final protocol/lifecycle/architecture subsystem: 85 passed in 24.41s, session 69157 exit 0; .mlforge-build/p05-supervision-tests.log. One approval-review timeout retried successfully. No product workaround or weakened test added.
- Scoped Ruff/check-format passed, docs/planning/diff checked for commit. No runtime/export change; no consumer reinstall. Updated owner and guides. Intended commit: feat(execution): supervise owned process groups. P05.2 remains incomplete (serial policy/export staging ownership next); 13/30 top-level units.
