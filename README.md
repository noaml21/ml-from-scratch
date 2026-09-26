# ML From Scratch

NumPy implementations of core machine learning algorithms, with tests, visual experiments, and comparisons against scikit-learn.

## MLForge V1 implementation

The next product is MLForge, a local-first full-screen terminal ML workbench.
Its authoritative plan starts at [docs/v1/README.md](docs/v1/README.md).
Read [How it works](docs/HOW_IT_WORKS.md) for the system flow and
[Extending MLForge](docs/EXTENDING_MLFORGE.md) for practical change locations.
The `v1/mlforge` branch holds the verified V1 release candidate (not merged or published;
see [V1_BUILD_REPORT](docs/v1/V1_BUILD_REPORT.md)). Packaging and noninteractive
`mlforge --help` / `mlforge --version`, headless dataset/schema services, synthetic
examples, six-model fitting/evaluation and standalone model export are implemented;
the Textual shell supports local browsing, manual paths, packaged examples and a
first-50-row preview with schema statistics and complete cell details.
Schema correction, reset, explicit confirmation and local Prepare Copy/Save have
passed the dataset phase gate. Goal, target, feature and model selection now lead
through preprocessing review to real training, live status and cancellation.
Results, selected-model provenance and task-specific terminal inspection have
passed their phase gate. Try the model and Export package screens are implemented;
their installed-package verification is recorded in BUILD_STATE. Current progress and verification are in
[BUILD_STATE](docs/v1/BUILD_STATE.md). The educational algorithms below remain supported.

Development setup (CPython 3.12 or 3.13 on Ubuntu 24.04 x86_64):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,demos]' -c requirements/constraints-dev.txt
mlforge --help
python scripts/verify_package.py --prepare-wheelhouse
python -m pytest -q
```

Exact runtime and development/demo constraints live in `requirements/`.
Clean installation verification prepares dependencies explicitly, then checks
wheel and sdist-derived installations with package-index access disabled:

```bash
python scripts/verify_package.py --prepare-wheelhouse
python scripts/verify_package.py
```

The package verifier checks app packaging, dataset review and all four training/inspection
journeys through Pilot and real PTYs, with network attempts blocked in parent and worker processes.
The ordinary test suite also includes
six real exported-model consumer installations and requires the prepared local
wheelhouse; missing prerequisites fail explicitly. `python scripts/verify_release.py` runs the
complete installed-application and exported-model verification. Run `mlforge` to start.

### Try and export a model

After training, press Enter on a completed result to open **Selected model**.
**Try the model** shows one input per selected feature; mark an input Missing to
use the default learned from training rows. Numbers outside the training range
are used as entered with a warning, and new category text uses the fitted
unknown-category encoding. Nothing is retrained.

**Export package** asks for a destination folder (default `./exports`), a Python
module name (default `my_model`) and a version (default `1.0.0`), then builds one
wheel locally without network access. Existing files are never replaced. The
wheel holds the exact evaluated pipeline, its input schema and learned
categories/labels, never your original rows. Install it into a fresh virtual
environment with the same Python minor version on Linux x86_64:

```bash
python3.12 -m venv model-env
. model-env/bin/activate
python -m pip install exports/my_model-1.0.0-py3-none-any.whl
python -c 'from my_model import Predictor; print(Predictor().metadata["task"])'
```

`Predictor().predict(record)` returns `{"prediction": ...}` for classification and
regression or `{"cluster": ...}` for K-Means; PCA uses `transform(record)` and
returns `{"components": [...]}`. Use `None` for a missing value. The package does
not require MLForge, Textual or Rich. See
[EXPORT_SPEC](docs/v1/EXPORT_SPEC.md) for the full API and compatibility rules.

### Supported environments, privacy and limits

- Supported: CPython 3.12 and 3.13 on Linux x86_64 (Ubuntu 24.04 baseline,
  including WSL2). Other platforms are unverified. Use a terminal of at least
  80 × 24; 100 × 30 is the primary layout. Smaller terminals show a resize notice
  while work, cancellation and Ctrl+Q stay available.
- Inputs: UTF-8 CSV, TSV or flat JSONL up to 20 MiB, 20,000 rows and 100
  columns. The source file is only read, never modified.
- Privacy: MLForge makes no network requests and has no telemetry or browser
  flow. Temporary session files are removed on normal exit. Exported wheels
  contain no original rows, but learned categories, labels and parameters can
  still reveal information about the data.
- Limits: comparisons use one 80/20 holdout (or all rows for clustering/PCA)
  and are not proof of future performance. There is no cross-validation, tuning,
  time-series or grouped splitting, and no automatic refit on all rows. Exported
  models support the same Python minor version on Linux x86_64 with the exact
  pinned dependencies.
- At the maximum input size on the reference machine, loading took 25–31 s
  and training both classification models 65–84 s; exact timings and memory
  are recorded by `python scripts/measure_peak_input.py`.

### Troubleshooting

- *Resize to at least 80 × 24*: enlarge the terminal; your work is kept.
- *Clipboard unavailable*: the terminal refused the clipboard request. Select the
  prompt text or use Save.
- *That wheel already exists*: change the module name, version or destination.
  Existing files are never replaced.
- *VERSION_MISMATCH* when using an exported model: create a fresh virtual
  environment with the Python minor version shown on the export screen and
  install the wheel there so pip installs its pinned dependencies.
- *Missing prepared wheelhouse* from a verifier: run
  `python scripts/verify_release.py --prepare-wheelhouse` once with network access.

## Overview

This project focuses on understanding and implementing the mathematical core of common machine learning algorithms instead of relying on library implementations. The algorithms themselves use NumPy; scikit-learn is used only for reference comparisons and datasets.

The project currently includes K-Means clustering, binary Logistic Regression trained with stochastic gradient descent, and Principal Component Analysis using covariance eigendecomposition.

## Algorithms

### K-Means

The K-Means implementation alternates between assigning each sample to its nearest centroid and updating each centroid to the mean of its assigned samples. Training stops when the centroids converge or the maximum number of iterations is reached. The recorded objective is the sum of squared distances from samples to their nearest centroids. A comparison script validates the implementation against scikit-learn.

![K-Means clusters and convergence](assets/kmeans_demo.png)

### Logistic Regression

The binary Logistic Regression implementation uses the sigmoid function to estimate positive-class probabilities, binary cross-entropy as its loss, and stochastic gradient descent for training. Predictions use a linear decision boundary with a probability threshold of 0.5. A comparison script evaluates its learned decision rule against unregularized scikit-learn Logistic Regression.

![Logistic Regression decision boundary and loss](assets/logistic_regression_demo.png)

### Principal Component Analysis

The PCA implementation centers the data, computes its covariance matrix, obtains eigenvalues and eigenvectors, and selects the leading eigenvectors for dimensionality reduction. Reduced observations can be projected back into the original feature space for reconstruction. A comparison script checks the results against scikit-learn PCA.

![PCA digit reconstruction](assets/pca_reconstruction.png)

## Validation

The educational track retains 15 automated pytest tests covering core behavior, reproducibility, learned values, error handling, and reconstruction. Each implementation is also compared against scikit-learn on the same data:

- K-Means reached the same centroids and objective on the comparison dataset.
- Logistic Regression achieved the same training and test accuracy with very similar learned parameters.
- PCA matched scikit-learn's explained variance and reconstruction error.

These implementations are educational and are not intended as production replacements for scikit-learn.

## Project structure

```text
src/      NumPy algorithm implementations
demos/    Visual examples and scikit-learn comparisons
tests/    Automated pytest tests
assets/   Images used in this README
```

## Installation

The educational baseline has been verified locally on CPython 3.12.3.
MLForge targets CPython 3.12 and 3.13; both are required CI gates.

Create a virtual environment:

```bash
python -m venv .venv
```

On Windows, install the dependencies directly with the virtual environment's Python:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Activating the virtual environment is optional when using its Python executable directly.

## Running the demos

```bash
python demos/kmeans_demo.py
python demos/logistic_regression_demo.py
python demos/pca_demo.py
```

Each demo displays its visualization and saves the corresponding portfolio image under `assets/`.

## Running comparisons

```bash
python demos/kmeans_comparison.py
python demos/logistic_regression_comparison.py
python demos/pca_comparison.py
```

These scripts compare the NumPy implementations against scikit-learn reference implementations.

## Running tests

```bash
python -m pytest -v
```

## Technologies

- Python
- NumPy
- Matplotlib
- scikit-learn (validation and datasets only)
- pytest
