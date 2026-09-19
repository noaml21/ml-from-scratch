# ML pipeline contract

Canonical owner of target/feature eligibility, preprocessing, model defaults, evaluation and task semantics. All numeric limits below are design choices, not claims of statistical sufficiency.

## Eligibility and target selection
Classification: effective Category/Boolean, or Number whose present values are integral; 2..20 distinct labels, no missing target, minimum 5 rows per class and at least 20 rows total. Nonintegral numeric outcomes require deliberate Category override. Regression: Number target with >=2 distinct finite values, no missing target, >=20 rows. No target imputation or silent target-row dropping. Errors return to Target/Preview with a concrete remedy.

Suggested targets put Boolean/Category first for classification, Number first for regression, excluding ID-like, constant, all-missing, date or long-text columns. "Show all columns" displays every column with eligibility reason; it does not bypass safety rules. No target preselected and no automatic training.

Clustering/PCA skip Target. Clustering requires >=10 rows and >=1 selected Number feature. PCA requires >=3 rows and >=2 selected Number features. These goals are disabled with an explanation if no eligible selection is possible.

## Feature policy
Exclude target structurally. Preselect eligible Number/Boolean and low-cardinality Category columns for supervised tasks; Number only for unsupervised. Use full-data schema statistics for user-visible suggestions only, never learned imputation/scaling/encoding. Identifiers, Date, high-cardinality/long-text columns default unselected with reasons. All-missing and constant features are disabled as unusable. Category >50 unique or >80% unique (n>=20) and long text use DATASET_SPEC warnings.

User may select a high-cardinality Category after warning; encoder caps representation. Identifier/Date can only become features after an explicit valid type override in Preview. No silent semantic feature engineering. At least one eligible feature required.

Leakage review before Train:
- Exact equality with target (compare missingness and effective values), and names such as target_copy, prediction, predicted, outcome, result, label, post_outcome are warnings; matching is case-insensitive and documented, not certainty of leakage.
- Flag exact duplicate selected-feature rows, and caution that repeated entities/time ordering can make a random split optimistic. No deduplication/group inference.
- Warnings show specific columns/reasons and require "Keep selected features and continue" or return to edit; only deterministic target exclusion is automatic.
- Do not compute correlation/mutual-information selection on the holdout, and do not claim all leakage can be detected. No high-correlation feature pruning.

## Split and fitted transforms
Seed 42, private RNG/random_state everywhere; record the seed and exact split row IDs in session metadata.
Supervised: one 80/20 shuffled holdout split, test count ceil(0.2*n). Classification uses stratification; verify all classes in both partitions and fail actionably if constraints cannot be satisfied. Regression uses the same deterministic random split rule without stratification. All models for a run share the exact indices. No per-model resplitting or model-dependent dropped rows.

Fit the entire preprocessing+estimator pipeline independently on training rows only. Category vocabularies, rare grouping, medians, means, scales and coefficients must not inspect holdout values. UI's descriptive whole-table schema inspection is separate and does not fit transforms. Target class labels map to stable strings (Category exact lexical text; Boolean "false"/"true"; integral Number canonical decimal integer strings); report these display/API types. Regression y is finite float64. No target scaling. Any input-range diagnostics stored for prediction use training-only minima/maxima for supervised tasks, and all fitted rows for unsupervised tasks; holdout extremes never affect these ranges.

| Feature kind | Learned transformation |
|---|---|
| Number | SimpleImputer median, keep_empty_features=True; StandardScaler for Logistic/Linear/K-Means/PCA; no scaler for forests |
| Category | Constant missing sentinel + OneHotEncoder(handle_unknown="ignore", max_categories=32, sparse_output=False, drop=None) |
| Boolean | Same categorical branch with canonical "false"/"true" values and explicit missing sentinel |

Use a fixed, schema-recorded missing sentinel never equal to user category text: deterministic input normalization prefixes every present categorical value with a present-value marker and reserves a distinct missing marker. Normalization is stateless and shared with exported prediction. Pipeline category imputer/encoder sees uniform strings; unknown categories encode all zero and produce a user/API warning, never a crash. No data-dependent choice of sentinel.

If a numeric feature is entirely missing in TRAIN, retain it using zero fallback as provided by the configured imputer, surface the fallback warning and record it. Never use its test median. If every transformed training feature is constant/empty, stop as not trainable. Do not silently remove selected inputs from the exported schema.

Hard transformed-matrix limit: <=512 output features and <=128 MiB estimated dense float64 matrix bytes for the largest batch involved; preflight using selected kinds with worst-case category expansion (32 each), then enforce after fit before allocation where possible. Refuse with "Choose fewer features or simplify categories"; do not silently lower limits, hash or truncate. Input row/cell limits remain in DATASET_SPEC.

Unsupervised: fit preprocess+estimator on all selected data, clearly labeled "Exploration on this dataset; no test split". Numeric median and scale fit on all these rows. No categorical one-hot distance geometry in V1 unsupervised tasks.

## Model registry and fixed defaults
Only the following factories; explicit parameters with actual resolved library version recorded. Standard remaining library defaults must be captured via get_params in run metadata. No tuning screen.
| Stable ID | Estimator / explicit configuration |
|---|---|
| classification.logistic | LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000, random_state=42) |
| classification.forest | RandomForestClassifier(n_estimators=100, max_depth=12, min_samples_leaf=2, random_state=42, n_jobs=1) |
| regression.linear | LinearRegression() |
| regression.forest | RandomForestRegressor(n_estimators=100, max_depth=12, min_samples_leaf=2, random_state=42, n_jobs=1) |
| clustering.kmeans | KMeans(init="k-means++", n_init=10, max_iter=300, random_state=42); k default 3, range 2..min(10,n_rows-1) |
| reduction.pca | PCA(svd_solver="full"); components default min(2, allowed maximum), range 1..min(10,n_features-1,n_rows-1) |

K-Means additionally requires >=k distinct rows in transformed space. PCA requires nonzero total variance; degenerate/rank-deficient output is explained, not assigned fake variance. ConvergenceWarning makes that candidate failed with actionable text; do not rank/export a model that failed convergence. Other warnings are captured explicitly with safe categories; unexpected exceptions are model-local except corrupt shared state/resource/protocol failures, which abort the run.

Limit numerical thread pools to one in child environment before importing numpy/sklearn; n_jobs=1 avoids hidden worker children. ML training lifecycle/timeout belongs to ARCHITECTURE.

## Evaluation and recommendation
Classification table: Accuracy, Macro F1 (arithmetic mean over all known classes, zero_division=0). Sort descending Macro F1, then descending Accuracy, then stable model ID. Highlight "Recommended based on test performance" only among successful candidates with valid metrics; with one valid candidate say "Only completed model" rather than implying a comparative victory. Help states model selection on this holdout can be optimistic; independent future validation is required.

Diagnostics: confusion matrix with true rows/predicted columns and stable label order, per-class precision/recall/F1/support, train/test class counts, majority-class baseline on the same test rows using most frequent TRAIN label (stable lexical tie break). Probability confidence/calibration claims are not offered.

Regression table: MAE and R²; rank lowest MAE then stable ID. RMSE and residual count/mean/min/max in details. R² is N/A for constant test targets, even if sklearn force_finite would replace it. Negative R² is valid. Baseline predicts TRAIN-target mean, scored with same metrics. Predictions/metrics must be finite where defined; invalid metrics fail candidate evaluation.

K-Means: cluster sizes and silhouette; details show inertia, standardized-space centers, iterations, and actual cluster count. Silhouette computed on all transformed observations up to 2,000, otherwise deterministic sample of 2,000 using seed 42, explicitly labeled sampled. If fewer than 2 labels or sample labels equal sample size, show N/A with reason, never zero. Warn if actual clusters < requested; treat that candidate as failed under the distinct-row gate. IDs are arbitrary, not meaningful categories. No "best" recommendation.

PCA: retained variance ratio sum and retained/original feature counts; details per-component variance and reconstruction MSE in standardized feature space. Zero-variance denominator blocks training. No predictive quality claim, no recommendation, no mandatory scatter plot.

All calculations use original precision; formatting/rounding is presentation only. Comparisons belong to one immutable run/split; stale results cannot be mixed.

## Selection, Try and export identity
Selected model is the exact successfully evaluated pipeline. V1 never refits it on full data during selection/export. Header/export card explicitly states "Trained on 80%; evaluated on 20%" for supervised, with counts. Completed candidates in a cancelled/partially failed run remain inspectable/exportable with the partial-run label; interrupted candidates never do.

Try requires one input per selected feature (scrollable form), number/category/boolean controls plus an explicit Missing toggle. A blank numeric input is an error unless Missing selected. Category has known choices plus new text input. Reuse the exact prediction runtime defined in EXPORT_SPEC. Classification returns label, regression number, K-Means cluster ID, PCA component vector. No target field. Inference warnings show unknown categories, missing handling and unreasonable/nonfinite values as appropriate; numeric out-of-range relative to training min/max is a warning, not clipping.

## P04.1.a implemented policy
`tasks.py` exposes task labels, target/feature choices with reasons, option bounds, validated target display labels and explicit review warnings. It consumes confirmed schema statistics; it does not fit transforms, split rows or manage processes. High-cardinality/long-text inputs remain selectable only with review; incompatible mixed target kinds also require acknowledgement or explicit Category correction. Name-based leakage matching uses the exact case-insensitive names listed above, with no substring or correlation heuristic. `validate_selection` enforces the same rules headlessly; Show all changes visibility only.

## P04.1.b implemented preparation
`preprocessing.prepare_run` freezes one shared row split and policy; it validates raw inputs statelessly through `prediction.runtime.normalize_record` and does not fit anything. Numeric/categorical matrix bounds are checked before allocating the normalized matrix. Supervised test size uses exact integer ceil(n/5); classification stratifies, both supervised goals shuffle with seed 42, and unsupervised goals keep all rows. Candidate fitting/evaluation is the next unit. `raw_records` preserves selected-field order and translates only canonical missing markers to None for the shared runtime.
