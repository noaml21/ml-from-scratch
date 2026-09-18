# MLForge agent guide

MLForge V1 is a local, full-screen Textual machine-learning workbench. Dataset files never leave the machine. This repository also preserves the original NumPy learning implementations.

## Read first
Start with [docs/v1/README.md](docs/v1/README.md), then read all normative specifications and [CODEX_EXECUTION.md](docs/v1/CODEX_EXECUTION.md) before coding. The specifications are the source of truth; this guide is an index, not a competing specification. The audit distinguishes current code from planned code.

## Invariants
- UI is presentation only; core modules must import without Textual.
- Split before fitting supervised preprocessing. Export the exact evaluated pipeline; never silently refit.
- No network, telemetry, browser flow, remote AI calls, or user-data logging in the application.
- No shell interpolation of paths, arbitrary model loading, or automatic trust of serialized types.
- Keep existing NumPy APIs, tests, demos and assets working. Do not turn educational algorithms into the default product engine.
- No destructive Git operations, stable-branch changes, secret access, or unrelated cleanup.

## Layout
Existing: `src/{kmeans,logistic_regression,pca}.py`, `tests/test_*.py`, `demos/`, `assets/`.
Planned: `src/mlforge/` with application, datasets, preprocessing, models, training, evaluation, prediction, export and tui modules. See ARCHITECTURE.md for ownership. Specifications and evidence live in `docs/v1/`.

## Implementation
Work on `v1/mlforge`, based on the complete `planning/mlforge-v1` branch; never merge into main. Follow phase gates in IMPLEMENTATION_PLAN.md. Commit small verified changes and their tests/documentation together. Do not stop for ordinary internal implementation choices. Do stop for the concrete blockers in CODEX_EXECUTION.md.

Use typed core contracts, small cohesive modules, explicit error states, deterministic tests, and the existing Python conventions. Add tests for every non-trivial behavior. No speculative frameworks or additional V1 features.

## Commands
Current baseline: `python -m pytest -v`.
After foundation: `python -m pip install -e '.[dev,demos]' -c requirements/constraints-dev.txt`; `python -m pytest -q`; `python -m ruff check .`; `python -m ruff format --check .`; `python -m build`; `python -m pip check`.
Release: use every command and manual check in TEST_PLAN.md, including clean-wheel installs and exported-wheel verification. Do not claim future commands already exist.

## Resume and documentation
Read BUILD_LOG.md, inspect status/history/diff, confirm the branch and latest verified gate, and rerun its relevant checks before continuing incomplete work. Never discard uncommitted work or infer success from a checkbox. Update canonical documents when an authorized detail changes; log rationale and evidence. Finish with ACCEPTANCE_CRITERIA.md evidence and V1_BUILD_REPORT.md.
