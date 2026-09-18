# Planning review and requirement coverage

Planning only. Reviewed 2026-09-18 against the requested product flow and inspected repositories. This is not V1 acceptance evidence.

## Canonical decisions checked
- PRODUCT_SPEC fixes four tasks, six sklearn estimators, three formats and one wheel exporter.
- DATASET_SPEC owns parsing/type/override semantics; ML_PIPELINE owns eligibility and learned transforms.
- ARCHITECTURE owns operation process groups, event revisions and cancellation; UX uses those same states.
- EXPORT_SPEC owns Predictor API and compatibility; Try delegates to that same runtime.
- IMPLEMENTATION_PLAN gates ten ordered phases; acceptance has 28 measurable requirements; TEST_PLAN names concrete adversarial fixtures and release commands.
- CODEX_EXECUTION distinguishes implementation interruption from user-session persistence and final implementation SHA from the evidence commit.
- No production V1 claim or feature implementation is hidden in the planning branch.

## Requirement coverage
| Requested concern | Canonical home / disposition | Gate |
|---|---|---|
| Latest source research beyond README; algorithms/tests/demos/deps/packaging/CI/debt | REPOSITORY_AUDIT; exact remote/local SHAs, all ML source/tests/demos read | P01 / A02 |
| IPC v3 reference without copying engine | Audit + ARCHITECTURE: separation, workers, reaping, focus, literal text, tests, documentation | P05–P07 |
| Local-first full-screen mlforge, no browser/cloud/upload | PRODUCT_SPEC + UX_FLOW shell/privacy | A03–A05 |
| Minimal Enter welcome, no Start New Project | UX_FLOW Welcome | A05 |
| Picker/manual path/local examples | UX_FLOW loading | A05 |
| CSV/TSV/XLSX/JSON/JSONL candidates | DATASET_SPEC: CSV/TSV/JSONL included; PRODUCT_SPEC: XLSX/general JSON deferred | A06 |
| Preview counts/types/samples/table and zip-code override | DATASET_SPEC verification | A07 |
| Misunderstood data; Prepare with AI after invalid or valid parse | DATASET_SPEC prompt; UX_FLOW error actions | A08 |
| AI preparation preserves information, no invented data/preprocessing/target/encoding/semantics | DATASET_SPEC exact prompt constraints | A08 |
| Four clean goal labels, contextual ? | PRODUCT_SPEC + UX_FLOW | A09 |
| Suggested targets, all columns and suitability help | ML_PIPELINE eligibility + UX_FLOW | A10 |
| Feature defaults, identifier exclusions, warnings, no silent removal | ML_PIPELINE feature policy | A11 |
| Automatic preprocessing, original immutable, split before fit, reusable inference | ML_PIPELINE; EXPORT_SPEC runtime | A12 |
| Candidate model reduction, NumPy identity, meaningful adapter decision | PRODUCT_SPEC model table; audit: preserve educational track, concrete single-backend registry | A02/A13 |
| Model toggles/help, no tuning dashboard | UX_FLOW Models; ML_PIPELINE fixed params | A13 |
| Nonblocking training, truthful progress, failures/cancel/quit | ARCHITECTURE lifecycle + UX_FLOW | A14/A15 |
| Clean comparison, metrics/help, cautious recommendation | ML_PIPELINE evaluation | A16 |
| Confusion/precision/recall and useful diagnostics | ML_PIPELINE; feature importance explicitly deferred | A17 |
| Optional user Try, typed form, predict/transform | UX_FLOW + EXPORT_SPEC API | A18 |
| Python Package/Saved Model/Full Project candidates | EXPORT_SPEC wheel only; other exporters explicitly deferred | A19 |
| Self-contained fitted preprocessing, clean installation, versions/security/reproducibility | EXPORT_SPEC | A20/A21 |
| Full-screen spacing/hierarchy/keys/mouse optional/help/resize/errors | UX_FLOW visual contract and focus rules | A22/A23 |
| Modular core/importers/models/tasks/export extensibility without framework | ARCHITECTURE boundaries and concrete seams | P02–P05 |
| Agent onboarding, canonical docs and autonomous single handoff | AGENTS, index, CODEX_EXECUTION | A25 |
| Phase commits, build log/resume, final build report/review SHA | CODEX_EXECUTION + IMPLEMENTATION_PLAN + BUILD_LOG | A01/A25/A26 |
| Non-happy-path tests including install/export/Pilot/cancel/resize | TEST_PLAN | A24 |
| Scope control, future extensibility without implementing future scope | PRODUCT_SPEC non-goals; CODEX_EXECUTION | All phases |

## Contradictions resolved before handoff
- Educational README claims refer to the existing baseline; root README marks MLForge as planning. Future runtime use of sklearn is explicit.
- Four user goals retained, model/importer/exporter candidates narrowed explicitly instead of silently omitted.
- Export for PCA uses transform, not misleading predict; Try renders components and package examples follow task.
- PCA default clamps to legal component count for two-feature datasets.
- Privacy distinguishes no outbound data, local temporary files and learned category/model information inside exports.
- Whole-table descriptive inference is allowed; all fitted supervised values and prediction ranges are train-only.
- Export never performs an unannounced full-data refit.
- Letter shortcuts do not consume editable path/category text.
- Export build backends can spawn descendants; operation-owned process groups and corresponding cancellation tests cover them. ML estimators themselves do not spawn child processes.
- Final implementation SHA and report's own evidence commit use a non-self-referential protocol.

## Planning verification
- GitHub branch heads matched clean local audit checkouts.
- Baseline tests: 15 passed on CPython 3.12.3.
- Baseline pip check: no broken requirements.
- K-Means comparison: both cost 47.699582.
- Logistic comparison: both test accuracy 0.9200.
- PCA comparison: both reconstruction MSE 0.00407484; sign-equivalent components.
- Research-only skops probe: six standard fitted pipelines (mixed numeric/categorical for supervised; numeric for unsupervised), skops 0.15.0 + sklearn 1.9.1, initial empty-trust probe refused numpy.dtype; a second probe exposed the forest Tree type; final roundtrip passed with exactly numpy.dtype and (forests only in product policy) sklearn.tree._tree.Tree and equal predictions/transforms. Inspected skops _numpy.py DTypeNode/ArrayNode and _sklearn.py TreeNode/ReduceNode; the Tree index warning is reflected in EXPORT_SPEC structural validation requirements. No application or wheel exporter was implemented by this probe.
- Passed: validation of 16 Markdown files, all local links and code fences, required-document presence, 10 phases each with objective/dependencies/work/tests/docs/completion criteria, 26 unique acceptance IDs, and absence of a premature V1_BUILD_REPORT. git diff --check passed; scoped source/test/demo/asset/requirements diff was empty.
- Production source, tests, demos, assets and requirements are not changed. A local ignored .venv was created for audit; it is not the authoritative V1 dependency lock.

## Remaining implementation risks
1. Parser inference can misread domain meaning: explicit preview/type override and conservative eligibility mitigate it; semantic correctness still needs user confirmation.
2. Holdout model selection is optimistic for some datasets; no causal/group/time-series guarantees and no hidden refit.
3. Packaging/skops portability depends on exact tested versions; P02 proves fresh installs early and release gates cover all six models; trusted forest state still requires structural checks before native inference.
4. Process cancellation races and exporter descendants need real subprocess tests; a UI worker flag alone is insufficient.
5. Four tasks still require careful polish; no scope expansion, and a failed milestone blocks progression.
6. Both supported Python environments and live/PTY TUI need implementation-time evidence; baseline audit is not release verification.
7. Repository has no license; no licensing grant or public distribution is invented.

No unresolved product choice requires the user to mediate ordinary implementation. Library version resolution and internal decomposition remain evidence-based implementation tasks under explicit contracts.

## Continuation and visual refinement — 2026-09-18
- Added RESUME_PROTOCOL as sole owner of checkpoint/recovery mechanics; CODEX_EXECUTION retains overall execution authority and links it.
- Added CODEX_PROMPT as one start-or-resume entry, based on the complete planning branch, replacing the original first-commit-only prompt.
- Added one Current checkpoint to BUILD_LOG and 30 ordered unit IDs inside the existing ten phases. Phase gates are unchanged; a completed unit cannot pretend to pass a phase.
- Added explicit hard-stop/dirty-checkout/unknown-check/stale-log recovery, verified-commit push cadence and honest limits of fresh-clone recovery. No promise of automatic restart when usage returns.
- Expanded UX_FLOW with palette roles, clear next actions, humane copy and a nine-item screen review. Added early UX gates, color/monochrome/contrast evidence and acceptance A27/A28 (28 total).
- No product functionality was added; all changes remain planning/documentation. The original 16-file/26-ID verification above records the first planning commit, not the refined document count.
- Refinement verification: 18 Markdown files and local links/fences checked; 10 phase contracts, 30 unique work units and 28 acceptance IDs checked; git diff --check passed; original pytest suite rerun, 15 passed. Recovery rehearsal and real TUI visual gates are specified for implementation, not claimed completed now.
