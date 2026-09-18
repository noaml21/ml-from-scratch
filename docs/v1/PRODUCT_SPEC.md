# MLForge V1 product contract

## Purpose and priorities
A local-first, full-screen terminal workbench for small tabular datasets: load, understand, train, compare, try and export. Launch command: `mlforge`. Tagline: "Build useful machine learning models locally." Privacy line: "Your data stays on your machine."

Correctness, reliability, excellent UX, smooth interaction, defaults, clear errors, architecture, tests and documentation take priority over feature count. V1 is a complete narrow workflow, not a scaffold for later implementation.

## Fixed scope
| User goal | Task | Offered models |
|---|---|---|
| Predict an outcome | Binary/multiclass classification | Logistic Regression, Random Forest |
| Predict a number | Single-output regression | Linear Regression, Random Forest Regressor |
| Find groups | Numeric-feature clustering | K-Means |
| Reduce complexity | Numeric-feature dimensionality reduction | PCA |

All four goals are required; disabled goals explain current data incompatibility. Supervised tasks may use Number/Category/Boolean features. Clustering/PCA accept Number features only. Both supervised models are selected initially. All offered models use sklearn; educational NumPy algorithms remain separately documented and tested.

Required formats: CSV, TSV, flat JSONL. XLSX and general JSON are explicitly deferred. The example chooser bundles deterministic synthetic local examples for each goal and a small mixed-type supervised example; no download or browser.

Required flow: Welcome → Load Dataset → Parse → Preview and verify/correct types → Goal → Target (supervised only) → Features → Automatic preprocessing summary → Models → Training → Results → Select model → Inspect / optional Try / Export. "Optional Try" means the feature is built but the user need not use it.

One required exporter: installable Python wheel containing the fitted pipeline and inference runtime. All four goals export with the task-correct API in EXPORT_SPEC.md. No Saved Model or Full Project menu placeholders.

## Product boundaries
- One dataset and one current experiment per session. Back edits are supported with explicit downstream invalidation. No disk project history/resume UI; BUILD_LOG resumes implementation, not a user's experiment.
- Source data is read-only. No automatic row deletion, data repair, target inference, engineering, outlier removal or balance resampling.
- Explicitly warn about random-split suitability for time-ordered/grouped observations; V1 has no grouped/time-series splitter.
- A comparison is a small local holdout experiment, not proof of production validity. Unsupervised diagnostics are descriptive, not predictive accuracy.
- No tuning dashboard. Only K-Means cluster count and PCA component count are exposed because they define the desired output; their defaults/ranges live in ML_PIPELINE.
- No mandatory accounts, telemetry, update checks, AI calls or browser. Package installation may obtain dependencies before use. App execution, examples, training and wheel creation must work with network disabled.
- Preparation help generates text locally. The user decides whether to paste it/data into an external service. No provider integration and no dataset content included by default.
- Export does not include original rows. Fitted model parameters, category vocabularies and labels may still reveal information; explain this once before export.

## Supported release environment
V1 supported: CPython 3.12 and 3.13, Linux x86_64, Ubuntu 24.04 baseline, including Ubuntu 24.04 under WSL2. Primary UI target 100x30; complete keyboard flow must work at 80x24. Below 80x24 show a resize-required view while preserving state/cancellation/quit. Windows-native, macOS, ARM, Python 3.14 and other environments are unverified, not promised; do not add portability abstractions to claim them.

Distribution name in local metadata: `mlforge`, package `mlforge`, initial application version `0.1.0`. This is a repository-local V1 release, not a claim to the PyPI name and not authorization to publish. Existing NumPy tests remain valid in a source checkout; legacy educational files need not ship inside the app wheel.

## Explicit non-goals
Deep learning; NLP/text embeddings; image/audio models; time-series-specific ML; causal inference; group-aware evaluation; multioutput prediction; streaming/giant data; cloud/accounts/remote storage; GPU/distributed computation; AutoML search; tuning dashboard; cross-validation search; dataset editing; arbitrary serialized model import; ML plugin marketplace; multiple runtime backends; advanced experiment management; automatic model refit on all rows; probability calibration; browser plots; XLSX/general JSON; KNN/standalone Decision Trees; Saved Model/Full Project exporters.

Feature importance is deferred to avoid misleading impurity attribution and added explanation/UI. Required diagnostics instead use confusion matrices, per-class precision/recall, regression residual summaries, cluster sizes and PCA variance. New extensions have clear seams in ARCHITECTURE; no future feature is implemented speculatively.
