# MLForge V1 build report

Release candidate on branch `v1/mlforge` (repository noaml21/ml-from-scratch). Not merged into `main`, not published, no release created.

- **Verified implementation commit:** `a2092c04ed1244886cf587a49898f4bcc029fb89`
- **Final repository evidence commit:** the commit that last changed this report, retrieved with `git log -1 --format=%H -- docs/v1/V1_BUILD_REPORT.md` (a file cannot contain its own commit SHA).
- Every later commit before the evidence commit changes documentation only: `git diff a2092c0 <evidence> -- src scripts tests pyproject.toml requirements .github` is empty.
- Planning base `0798b5b7d7ae07b0bd9fe454b3ddf90eba5434d5` is an ancestor; history was never rewritten.

## Architecture and module boundaries
A local, full-screen Textual application over a headless core, with the dependency direction TUI → application → execution/core enforced by `tests/mlforge/test_architecture.py` (AST guard, cycle check, headless imports without Textual/Rich, standalone runtime).

| Layer | Modules | Owns |
|---|---|---|
| Records/contracts | `contracts.py`, `datasets/records.py` | Typed immutable records, safe `DomainError`, codecs |
| Datasets | `datasets/importers.py`, `inference.py`, `validation.py`, `prepare.py` | Bounded CSV/TSV/JSONL import, full-table type inference, atomic overrides, Prepare text |
| ML core | `tasks.py`, `preprocessing.py`, `models.py`, `training.py`, `evaluation.py` | Eligibility, split-before-fit preparation, six estimators, fit-once evaluation, metrics/ranking |
| Prediction/export | `prediction/runtime.py` (zero first-party imports), `prediction/schema.py`, `export/wheel.py` | One inference runtime shared by the app and exported wheels; verified offline wheel builds |
| Execution | `execution/protocol.py`, `coordinator.py`, `worker.py` | Owned child processes, deadlines, cancellation/reaping, integrity-checked results, no-replace publication |
| Application | `application/service.py`, `state.py`, `artifacts.py` | Session state machine, revisions/invalidation, selected accepted bundle, Try/Export commands |
| TUI | `tui/app.py`, `tui/screens/*`, `theme.tcss`, `help.py` | Presentation only: screens, focus, help, resize guard |

Exact object lineage: the pipeline fitted on training rows and evaluated on the holdout is saved once as a bundle; selection, Try and Export all use that bundle's bytes (hash-checked); nothing is refitted.

## Implemented functionality
Welcome → Load (browse, path, five packaged synthetic examples) → Parse → Preview with type review/override/reset and Prepare Copy/Save → Goal (four goals) → Target (supervised only) → Features (reasons, leakage/high-cardinality acknowledgement) → automatic preprocessing summary → Models (both supervised selected; K-Means k, PCA components) → live training with factual phases, cancel and partial results → Results (two primary metrics, cautious recommendation) → Selected model → Inspect (confusion/per-class, residuals, cluster sizes/centers/silhouette, PCA variance/reconstruction) / Try (typed form with Missing, warnings, task outputs) / Export (destination, module, version, privacy/compatibility note, verified wheel, install/use guidance).

Intentional omissions (PRODUCT_SPEC non-goals): no browser, accounts, telemetry, cloud, AI calls, XLSX/general JSON, tuning, cross-validation, time-series/grouped splits, feature importance, probability outputs, automatic full-data refit, saved projects or other export formats.

## Tested environments and versions
- Local: Ubuntu 24.04.5 LTS, Linux 7.0.0-31-generic x86_64, CPython 3.12.3, 12 CPUs.
- CI: GitHub Actions `ubuntu-24.04`, CPython 3.12.14 and 3.13.15.
- Runtime pins (requirements/constraints-runtime.txt): numpy 2.5.3, scipy 1.18.1, scikit-learn 1.9.1, skops 0.15.0, textual 8.2.8, rich 15.0.0, packaging 26.3, threadpoolctl 3.7.0, joblib 1.6.0, build 1.6.1, setuptools 82.0.1, wheel 0.48.0 (full closure in the file). Development: pytest 9.1.1, pytest-asyncio 1.4.0, ruff 0.16.8, twine 6.2.0.

## Commands and results on the verified candidate
| Check | Result |
|---|---|
| `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q` (local, 3.12.3) | **707 passed in 2061.12s**, exit 0; includes six-model consumer installs; no skips, no xfails, no deselections |
| CI [36269528709](https://github.com/noaml21/ml-from-scratch/actions/runs/36269528709), consumer installs on | **success**: 3.12 707 passed/1749.31s; 3.13 707 passed/1642.70s; each also pip check, Ruff, format, build, twine, three comparisons, `verify_release.py`, planning validation |
| `python -m ruff check .` / `python -m ruff format --check .` | passed (121 files) |
| `python -m build` (isolated, offline from the wheelhouse), `python -m twine check dist/*`, `python -m pip check` | passed |
| `python demos/{kmeans,logistic_regression,pca}_comparison.py` | passed (educational track preserved; original 15 tests pass in the suite) |
| `python scripts/verify_release.py` (local, clean tree) | **exit 0** at aa7f971 (code identical to a2092c0), worktree clean: application wheel/sdist installs and installed journeys 655.8 s, six model consumer installations 104.9 s; release-3.12.json |
| `python scripts/measure_peak_input.py` | **passed**: 20,000 × 100 CSV (12,956,658 bytes) load 25.42 s, training both classification models 65.31 s, 1,000-record prediction 3.13 s, export 6.02 s (25,975-byte wheel), peak child RSS 779.5 MiB; performance-3.12.json |
| `python scripts/rehearse_recovery.py` | passed (.mlforge-build/recovery-p09.json) |
| `python docs/v1/verify_planning.py`, `git diff --check`, `git status --short` | passed; only the user's external untracked `CLAUDE.md` remains |

Earlier phase gates: P07 CI [36262489129](https://github.com/noaml21/ml-from-scratch/actions/runs/36262489129), P08 CI [36266241401](https://github.com/noaml21/ml-from-scratch/actions/runs/36266241401), both successful on both Pythons.

## Clean installation and entrypoint proof
`scripts/verify_package.py` (inside `verify_release.py`) builds the application wheel and sdist, creates fresh virtual environments outside the checkout, installs with index access disabled from the prepared wheelhouse, asserts the package is loaded from the venv, runs `mlforge --version` (0.1.0) and `mlforge --help`, parses all five packaged examples and runs `pip check`. A uniquely named `.pth` audit hook, inherited by every worker, denies network access; a control connection is refused in every environment and the logs show zero attempts. Session temporary directories are empty after quit.

## Offline export, install and prediction equality
- Six models (`tests/mlforge/export/test_install.py`): Logistic Regression, Random Forest Classifier, Linear Regression, Random Forest Regressor, K-Means and PCA wheels, each installed into its own fresh consumer environment without MLForge/Textual/Rich, network guarded, `pip check` clean. Predictions/transforms equal the evaluated in-app pipeline (exact labels/cluster IDs; rtol 1e-8, atol 1e-10), with identical warnings, strict input errors, compatibility/corruption refusal and no refit.
- TUI exports: each installed application (wheel and sdist) completes all four goals keyboard-only through Try and Export; each exported wheel is installed into a fresh consumer and reproduces the in-app Try result (8 consumer checks per verifier run).

## Keyboard, resize, error, cancellation and visual evidence
Pilot suites run the complete flow keyboard-only at 80x24 and 100x30, including help/focus restoration, literal `q`/`b`/`?` in fields, below-minimum guard with cancel/quit, repeated 100x30 → 80x24 → 79x23 → 100x30 transitions (now including Try and a running export), real-child training cancellation and partial results, field-level Try errors and export collisions/permission failures with retry. Real PTYs of the installed application cover the dataset journey (explicit OSC52 Copy, Ctrl+Q/Ctrl+C) and classification (`q`) and PCA (Ctrl+C) through Help, resize, re-entry, inspection, quit confirmation and alternate-screen restoration. The PTY verifier judges modal and resize transitions on the currently visible terminal cells. Color and monochrome SVG captures are kept under `.mlforge-build/` (p07-*, p08-try, p08-export, installed-*) and in CI artifacts. Evidence limit: no human-operated physical terminal session was recorded; visual review used the actual Textual SVG captures and automated PTY transcripts.

## Documentation and acceptance status
README, HOW_IT_WORKS, EXTENDING_MLFORGE, AGENTS and ARCHITECTURE describe the implemented modules; BUILD_STATE is the current pointer and BUILD_LOG the history. Acceptance: A01–A24, A27 and A28 have passing evidence mapped in BUILD_LOG (P09 acceptance matrix); A25 is satisfied by the P10 documentation review and A26 by this report and the non-self-referential SHA protocol. No V1-critical TODO, skip, xfail or known blocker remains.

## Known limitations
- Supported only on Linux x86_64 with CPython 3.12/3.13; exported wheels require the exporting Python minor version and exact pinned dependencies.
- One holdout split; model choice on it can be optimistic. No grouped/time-aware splitting.
- At the maximum input size, loading took 25–31 s and training both classification models 65–84 s across two runs on the reference machine (the parse child used about two thirds of its 30 s deadline; the parent then decodes the table in a thread). Slower machines approach the deadlines.
- An exported wheel is executable Python and must come from a trusted source; learned categories and labels can reveal information.
- Parent SIGKILL or power loss can leave temporary files (documented in ARCHITECTURE).

## Review hotspots
- Leakage: `preprocessing.prepare_run` split-before-fit, per-candidate fitting in `training.fit_pipeline`, no-leakage sentinels in `pipeline/test_split.py`.
- Serialization: skops trust allowlist and forest tree validation in `prediction/runtime.py`; archive bounds; no pickle fallback.
- Worker races: `execution/coordinator.py` cancellation vs completion acceptance, publication barrier, subreaper cleanup; `application/service.py` revision checks.
- Package installation: `scripts/verify_package.py`, `verify_release.py`, network guard coverage of children, exact dependency pins.
- Schema semantics: `datasets/inference.py` (Number fast path must stay identical to exact Decimal interpretation; oracle test), overrides in `validation.py`, leading zeros/precision warnings.
- UX: focus restoration and modal/resize ordering in `tui/app.py`; Try field-error mapping (worker parses the runtime's `Record N: CODE: field` message); export success guidance.
