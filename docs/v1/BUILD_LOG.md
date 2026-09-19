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
