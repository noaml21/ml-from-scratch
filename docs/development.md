# Development and testing

## Setup

CPython 3.12 or 3.13 on Linux x86_64. From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,demos]' -c requirements/constraints-dev.txt
python scripts/verify_package.py --prepare-wheelhouse   # once, needs network
```

`requirements/constraints-runtime.txt` and `constraints-dev.txt` pin the tested dependency set. The prepared wheelhouse (`.mlforge-build/wheelhouse`, git-ignored) lets installation tests and verifiers run with package indexes disabled. They fail with setup instructions if it is missing, never skip.

## Repository layout

```text
src/mlforge/          the application (see How MLForge works for module ownership)
  application/        session state and commands
  datasets/           bounded importers, type inference, overrides, Prepare text
  execution/          worker protocol, coordinator, child entrypoint
  prediction/         shared inference runtime and export schema
  export/             offline wheel builder and templates
  tui/                Textual screens, theme and help catalog
  examples/           packaged synthetic datasets
tests/mlforge/        application, datasets, execution, export, pipeline, prediction, tui
scripts/              package/release verifiers and maintenance tools
src/{kmeans,logistic_regression,pca}.py, demos/, assets/, tests/test_*.py
                      the original NumPy educational track
docs/                 user and developer documentation; docs/v1 holds the V1 record
```

## Checks

```bash
python -m pytest -q                      # full suite, including real child processes,
                                         # Pilot UI journeys and model-consumer installs
python -m pytest -q -m 'not install'     # without the six consumer installations
python -m pytest -q tests/mlforge/test_architecture.py   # module dependency guard
python -m ruff check .
python -m ruff format --check .
python -m build && python -m twine check dist/*
python demos/kmeans_comparison.py        # and the other two comparisons
```

The suite contains 707 tests for the V1 release candidate. Real-process and UI tests use event handshakes and deadlines rather than fixed sleeps.

## Verifier scripts

| Script | Purpose |
|---|---|
| `scripts/verify_package.py` | Builds the wheel and sdist, installs both into fresh environments outside the checkout with indexes disabled, then drives the installed app: dataset, training, Try and Export journeys through Textual Pilot and real terminals, with a network guard in every process. Each exported wheel is installed into its own consumer environment and must match the in-app prediction. |
| `scripts/verify_release.py` | The release command: runs `verify_package.py` and the six-model consumer installations and writes a JSON report with commands, exit codes and versions. |
| `scripts/measure_peak_input.py` | Loads, trains, predicts and exports at the documented input limits and records time and memory. |
| `scripts/rehearse_recovery.py` | Rehearses the development resume protocol on a disposable clone. |
| `scripts/capture_screenshots.py` | Regenerates the documentation screenshots in `docs/assets/` from the real application. |
| `scripts/generate_examples.py` | Regenerates the packaged synthetic example datasets (a test checks they are reproducible). |

Reports and captures go to the git-ignored `.mlforge-build/`.

## Continuous integration

[`.github/workflows/verify.yml`](../.github/workflows/verify.yml) runs on pushes and pull requests to `main` and on manual dispatch, on Ubuntu 24.04 with Python 3.12 and 3.13. Each job installs the constrained dev environment, runs `pip check`, the full test suite, Ruff, build, Twine, the three educational comparisons, the release verifier and the planning-document check, and uploads the verifier evidence. The dispatch input `consumer_installs=false` skips the consumer installations for quicker runs.

## Contributing changes

- Start with [AGENTS.md](../AGENTS.md) (project rules), [How MLForge works](HOW_IT_WORKS.md) and [Extending MLForge](EXTENDING_MLFORGE.md).
- The specifications in [docs/v1](v1/README.md) are the source of truth for behavior; update the owning document when a contract changes.
- Keep widgets presentation-only, keep fitting and process management out of the UI, and add tests for every non-trivial behavior.
- Run the checks above; run `python scripts/verify_release.py` when packaging, prediction or export behavior changes.
