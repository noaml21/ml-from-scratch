# Verification strategy

Tests must exercise production services without Textual and the TUI through those same services. Preserve all 15 legacy tests unmodified unless a separately justified defect fix truly requires extension. Never replace real integration/export tests with mocks.

## Test organization and baseline
Keep `tests/test_{kmeans,logistic_regression,pca}.py`.
Add `tests/mlforge/{datasets,pipeline,training,prediction,export,tui}/`, common deterministic fixture factories and `tests/mlforge/test_acceptance.py`.
Use pytest + pytest-asyncio for core/async/Pilot tests. Keep property-like boundary matrices parametrized; no need for a new property-test dependency. Real subprocess fixtures use event handshakes and deadlines, not arbitrary long sleeps.

P01 captures original `python -m pytest -v`, three comparison scripts and pip check. Each phase runs targeted tests plus full `python -m pytest -q`, relevant lint/build and diff review before commit. No critical skipped/xfail tests count as a pass. Slow installation/PTY gates may have markers but are mandatory in final verification; the release script must explicitly invoke them.

## Required coverage matrix
| Area / suggested test module | Required cases and assertions |
|---|---|
| datasets/test_importers.py | CSV/TSV quoting, multiline, BOM, Unicode, CRLF, exact field widths, duplicate/blank/control headers, header-only/empty, JSONL key-order differences/duplicate keys/nesting/nonfinite/missing keys, unsupported extension/encoding, huge cell/rows/bytes, growth after stat, unreadable file, URL/device/FIFO rejection |
| datasets/test_canonical.py | Preserve leading zeros/whitespace/literals; raw table never mutates; exact counts; first-50 preview label; column order stable; source controls escaped only at display; equal tables across formats give equivalent semantic views |
| datasets/test_inference.py | Boolean not 0/1, dates vs invalid dates, zip category/override, ID-name heuristic, real-valued uniqueness, mixed JSON kinds, all-missing/constant, huge integers, full dataset tail contradicting preview, invalid override atomicity/reset |
| datasets/test_prepare.py | Works after failed and successful parse; every semantic-preservation instruction present; no source values/paths/headers by default; save collision/failure; no network calls |
| pipeline/test_eligibility.py | Target class/row/missing limits, integral numeric classification, regression finite/constant, all-column view cannot bypass rules, no target as feature, unsupervised numeric-only, PCA/k bounds, high-cardinality and leakage acknowledgements |
| pipeline/test_no_leakage.py | Test-only extreme numbers do not change training medians/scales; test-only categories absent from encoder vocabulary; TRAIN-all-missing number fallback ignores test; split indices same across models; pipeline fit receives only train IDs; target never reaches X |
| pipeline/test_models.py | All six models fit suitable deterministic data; constant/degenerate/bad inputs; repeatability; captured parameters; unsupervised gates; finite outputs; convergence-warning failure; matrix bounds before large allocation |
| pipeline/test_metrics.py | Independent hand-computed confusion/accuracy/macro F1, absent predicted class, zero division, stable class order; MAE/RMSE/R² negative/undefined; training-only baseline; ranking/tie/one-success cases; silhouette sampled/N/A; PCA projection/reconstruction variance |
| training/test_protocol.py | Version/revision/sequence checks, duplicate/stale events, bad JSON/truncated/oversized lines, output hash/type/size/path validation, nonzero exit after apparent success, bounded stderr, no pipe deadlock |
| training/test_lifecycle.py | Real slow child responsive cancel, SIGTERM-ignoring child killed/reaped, queued models never start, cancel-before-start, start/finish race, repeated cancel/quit, timeout, child crash, partial successful results, all fail, parent signal cleanup; unrelated sentinel process survives; exporter backend descendants disappear even if build leader exits first |
| prediction/test_runtime.py | Exact names in arbitrary order, missing/extra keys, wrong types, bool-as-number, huge integers, null/missing, unseen categories, sentinel collisions, out-of-range warning, whole-batch validation, empty/oversize batch, PCA API errors, no output logging |
| export/test_wheel.py | Every model roundtrip; no refit; schema + estimator hash; offline build; clean valid METADATA/WHEEL/RECORD; runtime source parity; package/version injections and collisions; no user data/probes/absolute paths in ZIP |
| export/test_security.py | Unknown serialized type refused; forest malformed child/feature indices, cycles and array shapes rejected before inference; altered hash; mismatched Python/dependencies; traversal/duplicate/bomb archive; corrupt/truncated resource; no pickle fallback; module-name collision; build error/disk full/permission/no-overwrite and atomic cancellation |
| export/test_install.py | Fresh venv outside source import path for all six model artifacts; pip check; Predictor/transform reproduce app values/warnings; mlforge/Textual absent from consumer env; import works from unrelated cwd; exact dependency resolution |
| tui/test_navigation.py | Enter welcome; picker/manual/example flows; keyboard only; ?/F1 context/focus restore; q/b/? typed into paths; Tab/Shift+Tab order; safe Back/invalidation/discard; hidden/disabled controls; no stale run result |
| tui/test_states.py | Invalid preview, schema override/failed override, Show all, no features, warnings, no models, busy/cancel/timeout, one/all failures, retry export, Try errors, privacy copy, failed clipboard fallback |
| tui/test_resize.py | Full journey at 100x30 and 80x24; resize during parse/train/help/export; 79x23 resize view still allows cancel/quit; return preserves focus and selections |
| test_acceptance.py | Real subprocess flow for each goal and format coverage; classification and PCA full Pilot→wheel→fresh-install journeys; examples use same importer; no network runtime; source bytes unchanged |

Use tiny deterministic synthetic datasets for tests, no private files and no downloaded data. Bundled examples must carry generation seed/formula/provenance. Performance fixtures bounded and generated in tests, not large committed blobs.

## Responsiveness evidence
A deliberately blocked/slow worker allows a UI timer heartbeat and help/cancel interaction to be observed. Pilot must see acknowledgement within 1s on CI fixture; child is reaped within 5s of cancellation under normal scheduled test conditions, including a SIGTERM-ignoring child. These are test budgets, not hard real-time kernel promises. Don't skip the test to mask a race. Retest peak supported input guards separately from tiny fixtures; document environment/time/RSS, not a universal speed claim.

## Build/CI contract
Add GitHub Actions jobs for Ubuntu 24.04 x86_64, Python 3.12 and 3.13:
1. Install `.[dev,demos]` using the committed compatible constraints; `pip check`.
2. Run legacy and new tests, Ruff, app wheel/sdist build, `twine check dist/*`.
3. Run three original comparison scripts; verify they complete and retain intended educational behavior.
4. Real process tests and Pilot at both supported sizes.
5. Isolated wheel/install/export smoke through release script, including all six model artifacts. Setup may download dependencies; the runtime phase cannot.
No job needs credentials/data uploads. Synthetic test reports/screenshots may be CI artifacts; no private datasets.

## Final commands (must exist by release)
From activated project venv, repository root:
```bash
python -m pip install -e '.[dev,demos]' -c requirements/constraints-dev.txt
python -m pip check
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m build
python -m twine check dist/*
python demos/kmeans_comparison.py
python demos/logistic_regression_comparison.py
python demos/pca_comparison.py
python scripts/verify_release.py
git diff --check
git status --short
```
If Python-specific pins differ, constraints-dev.txt may include documented environment markers; CI must prove both resolve. Do not claim a single local interpreter verified the other.

Implement `scripts/verify_release.py` as a deterministic verifier, not a new product CLI: creates fresh repo-owned temporary environments, builds/installs app wheel and sdist-derived wheel, invokes --help/--version, executes real TUI/child smoke using installed app, generates six model wheels and installs each into isolated consumer environments, runs inference equality/error cases and pip check. Make dependency preparation explicit (`--prepare-wheelhouse` can download declared packages before verification); ordinary verifier uses a prepared ignored local wheelhouse with `--no-index --find-links`. Missing prerequisites fail with exact setup instructions, never silently skip. No globally installed/editable source package may satisfy clean-install tests. Record commands, versions and exit statuses in a local report.

Enforce app no-network tests in children too (an inherited test harness guard or OS sandbox where available); assert no attempted outbound connections. Dependency installation is outside this phase. Export subprocess environment disables index access/build isolation. Inspect generated package for source data leakage separately.

## Manual/PTY finish
Run installed `mlforge` in a real terminal, keyboard only, one complete supervised and one unsupervised journey using local examples. Check resize, cancellation, help, all error wording, export command copy and terminal restoration (normal quit, handled failure, Ctrl+C). Save synthetic SVG evidence and the tester/environment/results in the build report. Pilot is required but cannot alone establish visual polish. If no real terminal is available, use an automated PTY capture/inspection and explicitly state the evidence limit; don't declare an unperformed visual check passed.

Before release verify docs links, command accuracy, package resources, source-data immutability, no critical TODO placeholders, and no untracked production files. A failing check must be fixed or reported as a blocker, never described as completed.

## Continuation and visual quality verification
The implementation workflow must pass the recovery rehearsals in RESUME_PROTOCOL.md at P01 and P09. Check reconstruction of the next unit from repository evidence, preservation of local partial work, unknown test-result handling and reconciliation when Git is ahead of the log. Keep this a documented development rehearsal (or a small disposable Git fixture), not a runtime MLForge feature or an autonomous-agent test framework.

For each TUI phase record the nine UX_FLOW screen-review checklist items against the screens built in that phase. Add Pilot assertions for next-action visibility, focus versus selection, disabled reasons and input retention. Inspect actual normal-color and monochrome captures, including selected/error states, at 100x30 and 80x24. Verify default-palette text contrast against the actual rendered background pairing. Mockups cannot substitute for Textual evidence. Remaining blocking usability defects prevent that phase from passing.
