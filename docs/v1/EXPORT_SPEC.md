# Python package export

One high-quality exporter: a local installable wheel, for every V1 task. No raw-model import/export UI, Full Project exporter, remote registry or automatic publishing. This document owns artifact compatibility and Predictor behavior.

## Exact object and workflow
Export only an accepted successful CandidateResult's ModelBundle. Preserve its fitted preprocessing, model and normalization/label semantics; never refit or evaluate on new rows. Supervised bundle remains fitted on the training partition, with honest evaluation counts in metadata.

Inputs: explicit writable output directory, package module name and version. Module name defaults to `my_model`, user must confirm; regex `[a-z][a-z0-9_]{2,49}`, reject Python keywords, leading underscore, and collisions with mlforge, numpy, scipy, sklearn, skops, packaging and stdlib top-level modules. Do not derive module names/code from raw column names. Version default `1.0.0`; V1 accepts three nonnegative decimal integers without leading zeros (except 0). Validate with packaging as well. Preserve the exact Python module name. For distribution metadata, replace underscore runs with a single hyphen and remove terminal hyphens (distribution names must end in a letter/digit); wheel filenames and dist-info directories use that normalized distribution name with hyphens changed to underscores. Thus `foo__bar` imports unchanged and ships as `foo_bar-1.0.0-py3-none-any.whl`; `foo_` imports unchanged and ships as `foo-1.0.0-py3-none-any.whl`. Check normalized distribution names against inference dependency names too, so a name such as `numpy_` cannot shadow the required numpy distribution. Distinct module names that normalize to the same wheel filename follow the existing no-overwrite policy.

Default destination cwd/exports displayed before creation. User chooses/creates directory inside TUI. Refuse existing final wheel name with Change name/version/destination; no overwrite option in V1. No prompt should suggest uploading. Building a wheel must never call pip or use network.

Generate fixed source templates and JSON resources in an owned staging directory; run `sys.executable -m build --wheel --no-isolation` via argument array. Dependencies for build are already runtime-installed. Untrusted schema/labels go in JSON, never Python string interpolation. Preserve build errors as short safe messages, not arbitrary source-data logs.

Validate resulting wheel contents/metadata/RECORD, load its bundled model safely in a separate verification child and compare predictions with the selected model on in-memory probe inputs. Probes are user data and may be temporary, never bundled. Require exact labels/cluster IDs, numerical agreement rtol=1e-8/atol=1e-10, identical warnings. Include at least one observed row and constructed valid missing/unknown cases when applicable. Before success, ensure schema/model hashes and expected task match.

Stage final file on destination filesystem, flush/fsync, publish without overwrite using exclusive/no-replace semantics (e.g. hard-link completed owned temporary file to new final name, then unlink staging file), fsync parent. No existing user file may be replaced. Handle unsupported atomic publish as an explicit error, not unsafe overwrite. Cancel/disk/permission failures leave no final incomplete wheel; preserve current model for retry. Private staging cleanup cannot target arbitrary user paths.

## Contents
```text
customer_churn_model/
  __init__.py             exports Predictor and public errors
  _runtime.py             same maintained inference runtime source as app
  schema.json             ordered names, semantic types, normalization version
  model.skops             standard sklearn fitted pipeline only
  metadata.json           task, versions, counts, params, metrics, seed, hashes
  MODEL_CARD.md           supported use, limitations, installation and API
customer_churn_model-1.0.0.dist-info/
  METADATA WHEEL RECORD
```
Use importlib.resources; installed package may run from any cwd. Runtime does not import mlforge or Textual. It may import pinned numpy/scipy/sklearn/skops/packaging and their transitive dependencies. No original CSV/TSV/JSONL, rows, holdout values, probe data, full source path, temporary absolute path, row-index list or UI screenshots in artifact. Store schema, learned categories, class labels and numerical learned state because inference needs them. A model is not a privacy/anonymization guarantee.

MODEL_CARD includes task, chosen model, training/evaluation counts (not identities), preprocessing description, primary metrics/definitions, partial-run status if relevant, arbitrary cluster-label warning, PCA component semantics, exact environment, creation tool/version and safe usage examples. No invented licensing information. Application repository has no license at planning baseline: do not publish app or generated packages to public registries without separate authorization. Local private use/install is in scope.

## Serialization and trust
Use skops for built-in sklearn Pipeline/ColumnTransformer/estimators; no pickle/joblib/cloudpickle fallback. Category normalization/record validation is fixed runtime code outside the serialized pipeline, not FunctionTransformer/lambdas. Standard learned parameters remain inside the pipeline.

Inspect untrusted types and require them to be in a code-maintained reviewed allowlist for the fixed supported estimators, with these planning-reviewed entries for the tested sklearn 1.9.1/skops 0.15.0 combination: `numpy.dtype` for standard pipeline dtype state and `sklearn.tree._tree.Tree` only for the two forest models. Other model IDs may trust only `numpy.dtype` beyond skops defaults. Do not populate trusted types from the artifact or automatically trust every `get_untrusted_types` result. An actual additional built-in type can be approved by implementer only after source review and a narrow regression fixture, documented in BUILD_LOG. Never allow arbitrary modules, user code or educational custom classes as a convenience.

The planning source review found that skops deliberately leaves Tree untrusted: malformed child/feature indices can crash sklearn native inference. Therefore forest bundles are restricted to trusted MLForge-generated artifacts, and a fixed validator must check tree array lengths/shapes, finite values, feature indices, leaf sentinels, child indices, reachability/acyclicity and bounded node counts before any inference. Test corrupted tree state without executing unsafe inference. Run artifact validation in the isolated child; the exported runtime repeats structural checks. This does not make an executable wheel from an untrusted publisher safe. A future dependency set must revalidate these exact assumptions.

Check resource sizes (wheel/model <=100 MiB compressed, <=512 MiB expanded, wheel member count <=200; nested model.skops member count <=2,000 checked independently). Apply these checks to both archives before deserialization; reject traversal/absolute/duplicate archive names and decompression bombs before loading/validation. The nested archive must also satisfy the expanded-size bound; limiting only the outer ZIP is insufficient. P02 must prove all six default pipelines fit these bounds. The separate member budget accommodates 100-tree forests (a planning probe produced 502 model members) without changing estimator defaults. SHA-256 detects corruption, not authenticity; the generated wheel is executable Python and must come from a trusted source. V1 Predictor loads only its own bundled artifact, no public `load(path)` API and no URL inputs.

[sklearn persistence guidance](https://scikit-learn.org/stable/model_persistence.html) documents version constraints; [skops guidance](https://skops.readthedocs.io/en/stable/persistence.html) requires deliberate trust decisions. These tools reduce specific deserialization risks; they do not make malicious wheels safe.

## Versions and reproducibility
Generated wheel is pure Python `py3-none-any`, but its supported environment is narrower: same CPython minor used for export on supported Linux x86_64. Set Requires-Python >=major.minor,<nextminor and a runtime check of platform/architecture/minor. The tag does not promise cross-platform validated models.

Freeze exact versions of the inference dependency closure from the verified training environment in generated Requires-Dist and metadata, including numpy, scipy, sklearn, skops, packaging, threadpoolctl and transitive dependencies needed to load. Compare actual versions before deserialization; mismatch raises CompatibilityError with fresh-venv install guidance. App/build-only dependencies are not installed by the exported wheel.

Record app version, normalization/schema format versions, estimator get_params, seed, split policy/counts, Python version, platform and dependencies. Exact reproduction of training requires the user's original data and same environment; artifacts don't contain training data. Predictions round-trip within tolerance; no claim of bitwise identical floating-point results on all hardware. Build deterministic file ordering and timestamp policy where practical; no requirement for identical wheel bytes because creation metadata can differ.

## Public API
```python
from customer_churn_model import Predictor

model = Predictor()
result = model.predict({"age": 32, "salary": 14500, "city": "Tel Aviv"})
# supervised classification:
# {"prediction": "retained", "warnings": []}

results = model.predict_many([{"age": None, "salary": 14500, "city": "New city"}])
```
Predictor() validates bundled schema/version/integrity, then loads lazily or eagerly consistently (document choice). Public errors: InputValidationError(ValueError), CompatibilityError(RuntimeError), ArtifactError(RuntimeError), UnsupportedOperationError(ValueError). They contain field names/error codes, not raw values or tracebacks as user text.

One record must be a Mapping[str, scalar-or-None] with exactly the selected feature names. Missing keys and unexpected keys (including target) are errors; key order is ignored and reconstructed from schema. None is the only API missing marker. Numbers accept finite int/float or strict numeric text (bool rejected); reject precision-losing large integers. Boolean accepts bool or true/false text. Category accepts string only; original numeric/boolean categories are entered as their preserved text. Empty category string is a present literal in the API and may be unknown; the Try form uses explicit Missing. No arbitrary object coercion. Validation happens before partial prediction.

`predict(record)` / `predict_many(records)`:
- Classification: {"prediction": str_label, "warnings": [safe warning objects]}.
- Regression: {"prediction": float, "warnings": [...]}.
- K-Means: {"cluster": int, "warnings": [...]}.
- PCA: raise UnsupportedOperationError directing caller to transform.
`transform(record)` / `transform_many(records)`:
- PCA: {"components": [float, ...], "warnings": [...]}.
- Other tasks: raise UnsupportedOperationError.
`metadata`: read-only/deep-copied JSON-compatible summary; no mutable access to fitted model.

Warning object: {"code": str, "field": str|null, "message": str}; codes include UNKNOWN_CATEGORY and OUTSIDE_TRAINING_RANGE. Missing values use trained defaults and can include MISSING_IMPUTED. No unsolicited print/log output. Batch max 1,000 records; empty input returns []; validate whole batch first and report indexed errors without returning partial results. No predict_proba API in V1.

The TUI Try flow calls this same runtime source and uses identical result/error/warning contracts. Tests enforce source/template parity and installed-wheel behavior rather than two independently maintained prediction implementations.

## Implementation evidence at P02.2
The shared runtime eagerly validates its bundled resources. App and exported code use identical normalization/prediction source; all six synthetic standard pipelines pass serialization and separate-process wheel parity with fixed trust. Full inference dependency closure is explicitly checked (11 distributions in the current environment); build/TUI packages are excluded from model requirements. P02.2 tests cover safe names including repeated/trailing underscores, archive/forest/hash/version failures, no-overwrite publication and runtime parity. This is not yet clean consumer-install evidence; that is the P02.3 gate recorded separately in BUILD_LOG.

## Implementation evidence at P02.3
The six-model consumer matrix installs each wheel with its complete declared dependency closure into a fresh virtual environment outside the checkout. MLForge, Textual and Rich are absent. Installed inference checks task APIs, strict input validation, metadata isolation, compatibility/hash rejection and exact categorical/warning or tolerance-based numerical parity. Network audit hooks cover installation and inference. Local Python 3.12 evidence passed; supported-version CI results are recorded in BUILD_LOG. Later application/Try integration remains a separate gate.

## P04 evaluated-pipeline integration
The canonical dataset training service supplies the exact evaluated pipeline and its metrics/diagnostics to the existing bundle writer. Review acknowledgements and safe fitting warnings are retained; split row IDs, source paths and records remain excluded. All six clean-consumer fixtures now originate from canonical import, schema, preparation and evaluation.

A legal 1,000-row, 3,024,021-byte CSV with long unique categories produces a 2,413,789-byte schema from 800 training rows. The earlier 2 MiB schema read cap incorrectly rejected it. Schema resource reads now use the existing 512 MiB expanded-resource ceiling; compressed/expanded ZIP bounds, member limits, fixed trust and hashes are unchanged. Regression coverage loads and exports this artifact and verifies the resource ceiling still rejects oversized input before parsing/deserialization.

Internal execution integration: an export worker receives only a parent-owned private publication directory on the selected destination filesystem. It builds/verifies the wheel using the existing exporter inside that directory and returns a receipt (expected filename, size, SHA-256) for a fixed private leaf. The parent validates the completed transport and staged bytes after successful exit/reaping, then checks cancellation/deadline before atomic no-replace publication. Cancelled, crashed, malformed or incomplete completion cannot publish. The coordinator retains cleanup ownership across forced termination. Direct headless exporter calls retain their self-cleaning publication behavior; the execution adapter supplies private staging as their destination. This does not alter wheel contents, inference APIs or evaluated pipeline identity.
