# Verification strategy

Tests must exercise production services without Textual and the TUI through those same services. Preserve all 15 legacy tests unmodified unless a separately justified defect fix truly requires extension. Never replace real integration/export tests with mocks.

## Test organization and baseline
Keep `tests/test_{kmeans,logistic_regression,pca}.py`.
Add `tests/mlforge/{datasets,pipeline,execution,prediction,export,tui}/`, common deterministic fixture factories and `tests/mlforge/test_acceptance.py`.
Use pytest + pytest-asyncio for core/async/Pilot tests. Keep property-like boundary matrices parametrized; no need for a new property-test dependency. Real subprocess fixtures use event handshakes and deadlines, not arbitrary long sleeps.

P01 captures original `python -m pytest -v`, three comparison scripts and pip check. Work-unit commits use the relevant targeted/subsystem tests and Ruff/check-format; full suite, packaging/build, planning/docs and other expensive project-wide checks run primarily at phase gates. Isolated exported-wheel consumer installations run when a change can affect export/runtime behavior or an explicit phase/release gate requires them. Broaden verification when focused checks reveal cross-cutting risk. P09/P10 and final release verification still run every required check. No critical skipped/xfail tests count as a pass. Slow installation/PTY gates may have markers but are mandatory in final verification; the release script must explicitly invoke them.

## Required coverage matrix
| Area / suggested test module | Required cases and assertions |
|---|---|
| test_architecture.py | AST dependency table/cycle guard; reject forbidden edges even in lazy/type-only imports; headless core/application imports with Textual/Rich blocked; runtime has no MLForge import; positive/negative checker fixtures |
| datasets/test_importers.py | CSV/TSV quoting, multiline, BOM, Unicode, CRLF, exact field widths, duplicate/blank/control headers, header-only/empty, JSONL key-order differences/duplicate keys/nesting/nonfinite/missing keys, unsupported extension/encoding, huge cell/rows/bytes, growth after stat, unreadable file, URL/device/FIFO rejection |
| datasets/test_canonical.py | Preserve leading zeros/whitespace/literals; raw table never mutates; exact counts; first-50 preview label; column order stable; source controls escaped only at display; equal tables across formats give equivalent semantic views |
| datasets/test_inference.py | Boolean not 0/1, dates vs invalid dates, zip category/override, ID-name heuristic, real-valued uniqueness, mixed JSON kinds, all-missing/constant, huge integers, full dataset tail contradicting preview, invalid override atomicity/reset |
| datasets/test_prepare.py | Works after failed and successful parse; every semantic-preservation instruction present; no source values/paths/headers by default; save collision/failure; no network calls |
| pipeline/test_eligibility.py | Target class/row/missing limits, integral numeric classification, regression finite/constant, all-column view cannot bypass rules, no target as feature, unsupervised numeric-only, PCA/k bounds, high-cardinality and leakage acknowledgements |
| pipeline/test_no_leakage.py | Test-only extreme numbers do not change training medians/scales; test-only categories absent from encoder vocabulary; TRAIN-all-missing number fallback ignores test; split indices same across models; pipeline fit receives only train IDs; target never reaches X |
| pipeline/test_models.py | All six models fit suitable deterministic data; constant/degenerate/bad inputs; repeatability; captured parameters; unsupervised gates; finite outputs; convergence-warning failure; matrix bounds before large allocation |
| pipeline/test_metrics.py | Independent hand-computed confusion/accuracy/macro F1, absent predicted class, zero division, stable class order; MAE/RMSE/R² negative/undefined; training-only baseline; ranking/tie/one-success cases; silhouette sampled/N/A; PCA projection/reconstruction variance |
| execution/test_protocol.py | Version/revision/sequence checks, duplicate/stale events, bad JSON/truncated/oversized lines, output hash/type/size/path validation, nonzero exit after apparent success, bounded stderr, no pipe deadlock |
| execution/test_lifecycle.py | Real slow child responsive cancel, SIGTERM-ignoring child killed/reaped, queued models never start, cancel-before-start, start/finish race, repeated cancel/quit, timeout, child crash, partial successful results, all fail, parent signal cleanup; unrelated sentinel process survives; exporter backend descendants disappear even if build leader exits first |
| prediction/test_runtime.py | Exact names in arbitrary order, missing/extra keys, wrong types, bool-as-number, huge integers, null/missing, unseen categories, sentinel collisions, out-of-range warning, whole-batch validation, empty/oversize batch, PCA API errors, no output logging |
| export/test_wheel.py | Every model roundtrip; no refit; schema + estimator hash; offline build; clean valid METADATA/WHEEL/RECORD; runtime source parity; package/version injections and collisions; no user data/probes/absolute paths in ZIP |
| export/test_security.py | Unknown serialized type refused; forest malformed child/feature indices, cycles and array shapes rejected before inference; altered hash; mismatched Python/dependencies; traversal/duplicate/bomb archive, independent outer/nested member and expanded-size budgets, valid 100-tree forest accepted; corrupt/truncated resource; no pickle fallback; module-name collision; build error/disk full/permission/no-overwrite and atomic cancellation |
| export/test_install.py | Fresh venv outside source import path for all six model artifacts; pip check; Predictor/transform reproduce app values/warnings; mlforge/Textual absent from consumer env; import works from unrelated cwd; exact dependency resolution |
| tui/test_navigation.py | Enter welcome; picker/manual/example flows; keyboard only; ?/F1 context/focus restore; q/b/? typed into paths; Tab/Shift+Tab order; safe Back/invalidation/discard; hidden/disabled controls; no stale run result |
| tui/test_states.py | Invalid preview, schema override/failed override, Show all, no features, warnings, no models, busy/cancel/timeout, one/all failures, retry export, Try errors, privacy copy, failed clipboard fallback |
| tui/test_resize.py | Full journey at 100x30 and 80x24; resize during parse/train/help/export; 79x23 resize view still allows cancel/quit; return preserves focus and selections |
| test_acceptance.py | Real subprocess flow for each goal and format coverage; classification and PCA full Pilot→wheel→fresh-install journeys; examples use same importer; no network runtime; source bytes unchanged |

Use tiny deterministic synthetic datasets for tests, no private files and no downloaded data. Bundled examples must carry generation seed/formula/provenance. Performance fixtures bounded and generated in tests, not large committed blobs.

## Small architecture guard (P02 onward)
Implement `tests/mlforge/test_architecture.py` using stdlib `ast` plus pytest; no new dependency/framework. Recursively inspect first-party modules under src/mlforge, resolve absolute and relative Import/ImportFrom (including `from . import sibling` and package initializers), and enforce ARCHITECTURE's module dependency table. Inspect function-local imports and TYPE_CHECKING blocks too. Report offending file, line and source→target edge. Reject first-party module-level import cycles (do not collapse distinct dataset modules into a false package-level cycle); do not analyze third-party library internals.

Reject direct Textual/Rich imports outside tui; reject UI→core/worker bypass and core/execution→application/tui dependencies. Enforce prediction/runtime.py's zero first-party-import contract, including relative imports. Disallow dynamic first-party imports and star imports in first-party product code as an evasion of these explicit seams; runtime/type-check-only imports obey the same direction. Standard-library/resource APIs and numerical-library internal dynamic loading are outside this first-party scan.

Prove the checker with tiny in-memory/disposable source fixtures: allowed edge, absolute and relative reversal, nested import, type-only reversal, initializer re-export, simple cycle, runtime-relative import and a UI direct-worker bypass. Do not corrupt real source files to test the guard. In a fresh subprocess, import existing non-TUI core/application/execution modules with a test import blocker for Textual/Rich; importing a worker module must not start work. Combine with isolated consumer-wheel tests so a copied runtime cannot secretly depend on the source checkout.

P02 gates the modules implemented so far and the checker fixtures; subsequent phases cover newly created modules automatically. Missing planned modules are not evidence of completed phases. Run this test in the ordinary suite/CI and explicitly at final review: `python -m pytest -q tests/mlforge/test_architecture.py`. It is a simple regression guard, not a security sandbox or proof of all dynamic behavior. Manual review still verifies logic belongs in the correct layer.

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

The complete CI workflow runs on pull requests or explicit workflow dispatch. Dispatch it at phase gates and when export/runtime changes require the complete matrix; ordinary focused work-unit pushes do not automatically repeat consumer installations. Record each dispatched run and exact SHA in BUILD_LOG. Local targeted verification remains required before each work-unit commit. For a dataset-only phase gate, dispatch with consumer_installs=false to run the complete non-consumer suite plus app packaging; keep its true default for export/runtime and P09/P10 gates. Report deselected consumer tests explicitly, never as a complete consumer pass.

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

For each TUI phase record the nine DESIGN_SYSTEM screen-review checklist items against the screens built in that phase. Add Pilot assertions for next-action visibility, focus versus selection, disabled reasons and input retention. Inspect actual normal-color and monochrome captures, including selected/error states, at 100x30 and 80x24. Verify default-palette text contrast against the actual rendered background pairing. Mockups cannot substitute for Textual evidence. Remaining blocking usability defects prevent that phase from passing.

For A28, include table and modal overflow, focused-and-checked versus checked-only, disabled labels/reasons, pending/running/cancelling, partial success, wide Unicode cells, and repeated transitions 100x30 → 80x24 → 79x23 → 100x30. Assert contents/focus survive and Cancel/Ctrl+Q remain usable. Verify the actual token pairings in DESIGN_SYSTEM, not just the base theme.
For A27, the recovery fixture must include both staged and unstaged partial edits plus a relevant untracked file, stale BUILD_STATE, and BUILD_LOG history. Check that the reconstructed next action matches IMPLEMENTATION_PLAN, the history is retained, and immutable planning ancestry is preserved.

Planning documentation sanity check: `python3 docs/v1/verify_planning.py` plus `git diff --check`. This checks structural invariants and local links, not semantic truth or V1 acceptance; retain the manual cross-document review.

## P02.3 installation prerequisites
The ordinary suite includes `tests/mlforge/export/test_install.py` for every model. Before running it on a fresh checkout, run `python scripts/verify_package.py --prepare-wheelhouse` once to obtain the committed runtime wheels. Tests then install with --no-index into independent venvs outside the checkout, with MLForge/Textual/Rich absent and a uniquely named .pth-loaded audit hook that exits on any network attempt (including in pip); a denied control connection proves the hook is active. No install test silently skips missing wheels. CI prepares the wheelhouse before pytest. Per-model synthetic evidence is saved under ignored `.mlforge-build/consumer-*.json`; these installation checks do not replace the later installed-TUI or release verifier gates.

Network test guards must prove that the specific audit hook is active, including in `-I` export verification children. Use a uniquely named module loaded by a test-environment `.pth` file and a denied local-connection positive control; checking only that `sitecustomize` is imported is insufficient because a system module can shadow the test file. Installation tests still use fresh consumer environments and never rely on MLForge/Textual being present.

P06 extends `scripts/verify_package.py` with `installed_dataset_smoke.py`: both clean application installations run from temporary directories outside the checkout, with a uniquely named `.pth` network guard inherited by workers and a denied control connection. Installed Pilot covers all five examples, manual/browse navigation, type override/reset/confirmation, Prepare privacy/save/collision/recovery, repeated resize and session cleanup. Real installed CLI PTYs verify explicit OSC52 Copy (not terminal receipt), no automatic clipboard request, Ctrl+Q/Ctrl+C and alternate-screen restoration. Synthetic SVG/PTY/JSON evidence is retained under `.mlforge-build/installed-*` and in CI artifacts. These dataset checks do not replace P07/P08 or final supervised/unsupervised export journeys.

P07 extends the same installed verifier with a separate `--training` smoke mode in both wheel and sdist-derived installations. It exercises all four keyboard-only configure → train → Results → Select → Inspect journeys, exact retained bundle hashes, result re-entry, source immutability, help/focus and resize restoration. Real installed CLI PTYs cover classification and PCA through inspection, unexported-result quit confirmation, `q`/Ctrl+C and alternate-screen restoration. The inherited network guard covers training workers; session temporary resources must be empty after quit. Evidence adds `training-journey.json` and task-specific SVG/PTY captures under the same installed directories. These checks stop at inspection; P08 extends the journeys through Try/export.

P05 export publication coverage includes real child missing/corrupt receipts, wrong names/hashes/sizes, malformed terminal events, crash after apparent completion, timeout, pre-acceptance cancellation, existing destinations and parent fsync rollback. Real evaluated exporters additionally exercise backend descendant termination, staged-byte termination and successful retry across all six models. Transport fault fixtures do not substitute for wheel-content/parity or consumer installation checks.
