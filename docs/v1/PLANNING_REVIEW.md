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
| Full-screen spacing/hierarchy/keys/mouse optional/help/resize/errors | DESIGN_SYSTEM visual contract; UX_FLOW focus/navigation rules | A22/A23 |
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

## Historical continuation refinement — 455553b, 2026-09-18
- Added RESUME_PROTOCOL as sole owner of checkpoint/recovery mechanics; CODEX_EXECUTION retains overall execution authority and links it.
- Added CODEX_PROMPT as one start-or-resume entry, based on the complete planning branch, replacing the original first-commit-only prompt.
- Added one Current checkpoint to BUILD_LOG and 30 ordered unit IDs inside the existing ten phases. Phase gates are unchanged; a completed unit cannot pretend to pass a phase.
- Added explicit hard-stop/dirty-checkout/unknown-check/stale-log recovery, verified-commit push cadence and honest limits of fresh-clone recovery. No promise of automatic restart when usage returns.
- Expanded UX_FLOW with palette roles, clear next actions, humane copy and a nine-item screen review. Added early UX gates, color/monochrome/contrast evidence and acceptance A27/A28 (28 total).
- No product functionality was added; all changes remain planning/documentation. The original 16-file/26-ID verification above records the first planning commit, not the refined document count.
- Refinement verification: 18 Markdown files and local links/fences checked; 10 phase contracts, 30 unique work units and 28 acceptance IDs checked; git diff --check passed; original pytest suite rerun, 15 passed. Recovery rehearsal and real TUI visual gates are specified for implementation, not claimed completed now.

## Recovery and final planning review — 2026-09-18
- Inspected actual branch/status, commits after 046621f, staged/unstaged diffs and untracked inventory before editing. Local 455553b preserved; no partial uncommitted repository work existed. Remote planning still pointed to 046621f at recovery. No reset, stash, discard or history rewrite.
- BUILD_STATE now solely owns the current resumable snapshot; BUILD_LOG retains historical evidence. RESUME_PROTOCOL alone owns checkpoint mechanics. Initial onboarding reads all specs; continuation reads active-phase owners and cross-cutting invariants, expanding with actual diff scope.
- DESIGN_SYSTEM now owns visual tokens/components/layout/gates; UX_FLOW retains screens, navigation and focus restoration. The design has an independent mint/charcoal identity and concrete 100x30/80x24/below-minimum rules. These are required implementation checks, not claims of an already built TUI.
- P01–P10 have relevant reading maps, checkpoint updates, test gates and commit boundaries. No new runtime feature, model, format, exporter or theme selector was added.
- Fixed one feasibility contradiction: <=200 nested model members would reject a valid 100-tree forest. In-memory sklearn/skops probe returned 502 members. EXPORT_SPEC retains <=200 outer wheel members and a separate <=2,000 nested model cap, with the existing size/trust/structural checks and added boundary tests.
- Immutable launch SHA is recorded once in BUILD_STATE; later sessions do not silently reset/rebase to a new planning tip. The final chat provides the actual verified delivery SHA; the reusable prompt deliberately uses a placeholder to avoid a self-referential commit.
- Checked every canonical document against its owner and the coverage below. Historical verification counts remain dated history, not current claims. Implementation phases remain NOT STARTED; release report remains absent.

## Acceptance → implementation → verification traceability
All listed test modules are planned under TEST_PLAN; no implementation test is claimed to exist yet. P09/P10 repeat release gates and assemble evidence for every ID.

| Acceptance | Owning implementation phases | Verification in TEST_PLAN |
|---|---|---|
| A01 | P01/P10 | Git ancestry/status and phase evidence |
| A02 | P01/P09 | Original 15 tests and three comparisons |
| A03 | P01/P09 | Two-Python CI, isolated installed wheel/sdist/entrypoint |
| A04 | P03/P05/P08 | test_acceptance network guards + source hash + export tests |
| A05 | P06 | tui/test_navigation and installed PTY |
| A06 | P03 | datasets/test_importers |
| A07 | P03/P06 | datasets/test_canonical, test_inference, tui/test_states |
| A08 | P03/P06 | datasets/test_prepare + tui/test_states |
| A09 | P04/P07 | pipeline/test_eligibility + tui/test_navigation + test_acceptance |
| A10 | P04/P07 | pipeline/test_eligibility + tui/test_states |
| A11 | P04/P07 | pipeline/test_eligibility + test_no_leakage + tui/test_states |
| A12 | P04 | pipeline/test_no_leakage + test_models |
| A13 | P02/P04/P07 | pipeline/test_models + test_eligibility + tui/test_states |
| A14 | P05/P07 | training/test_protocol, test_lifecycle + responsiveness Pilot |
| A15 | P05/P07 | training/test_lifecycle + real-child ownership assertions |
| A16 | P04/P07 | pipeline/test_metrics + tui/test_states |
| A17 | P07 | four-task test_acceptance and inspection captures |
| A18 | P08 | prediction/test_runtime + Try Pilot |
| A19 | P02/P08 | export/test_wheel + test_security |
| A20 | P02/P08 | export/test_install, all six real wheels |
| A21 | P02/P08 | export/test_security + ZIP/privacy inspection |
| A22 | P06–P09 | tui/test_navigation, test_resize + PTY |
| A23 | P05–P09 | state/protocol tests + tui/test_states |
| A24 | P09/P10 | Full release commands and CI matrix |
| A25 | Every phase/P10 | Documentation/link/coverage review and report |
| A26 | P10 | Final status/history/report provenance review |
| A27 | P01/P09 | Documented dirty/stale/unknown-result recovery rehearsal |
| A28 | P06–P09 | DESIGN_SYSTEM nine-item review, color/monochrome captures, contrast and Pilot |

Final planning verification: `python3 docs/v1/verify_planning.py` passed for 20 Markdown files, local links/fences, 10 phases, 30 units, 28 mapped acceptance IDs and 21 default-palette contrast pairs. Baseline pytest: 15 passed. `git diff --check` passed; production/test/demo/asset/requirements scoped diff empty. These are planning/baseline checks, not completed V1 acceptance.
