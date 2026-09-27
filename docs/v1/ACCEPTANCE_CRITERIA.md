# V1 release acceptance

Every row is mandatory. Status initially NOT VERIFIED; implementation must replace that status with evidence links/commands/results in BUILD_LOG and the final report. Existing planning or code alone is not proof. No V1-critical TODO, skip/xfail, severe known UX break or undocumented workaround may remain.

| ID | Objective pass condition | Required evidence |
|---|---|---|
| A01 | Dedicated v1/mlforge branch descends from complete planning branch; main untouched; logical verified commits | git branch/log/diff, BUILD_LOG per phase |
| A02 | All 15 original tests and three educational comparison scripts work; original NumPy APIs and assets preserved | pytest/comparison outputs, scoped diff |
| A03 | Clean wheel and sdist-derived install, pip check, --help/--version and mlforge TUI launch work on Python 3.12/3.13 Ubuntu baseline | two CI jobs + isolated verifier logs |
| A04 | Runtime/examples/import/train/export have no attempted network use or browser; source dataset bytes unchanged | child-aware network guard + content hash tests |
| A05 | Enter Welcome → Load; picker/manual/example all usable keyboard only, path spaces/Unicode supported | Pilot tests, installed-app PTY walkthrough |
| A06 | CSV/TSV/JSONL follow exact grammar/limits and canonical ordering; malformed/unreadable/oversized inputs recover without crash or silent rows lost | importer success/error matrix |
| A07 | Preview counts/types/samples/table match full parsed data; explicit confirmation required; valid override persists, invalid override changes nothing | stats fixtures, tail-conflict and zip-code override test |
| A08 | Prepare with AI works for parse failure and user-rejected preview, contains preservation rules, no automatic dataset inclusion/network; copy failure has usable save/text fallback | prompt content/privacy tests + Pilot |
| A09 | All four scoped goals work; contextual help hidden by default and available on focused option; no unsupervised Target screen | goal/flow tests, screenshots |
| A10 | Suggested targets plus Show all; unsafe/missing/ineligible target cannot bypass gates; information help correct | target tests and keyboard navigation |
| A11 | Useful feature defaults; identifiers/date excluded with reasons; user choices respected; target structurally excluded; leakage warnings acknowledged without silent removal | feature/warning/gate tests |
| A12 | Same deterministic split across supervised models; only training data fits preprocessing; all transforms retained; source unchanged | no-leakage sentinel and reproducibility tests |
| A13 | Six offered estimators work with fixed recorded defaults; selection excludes unwanted models; K/PCA bounds and degenerate data handled | model/registry/parameter tests |
| A14 | UI timer/input responsive during real child training; truthful operation/elapsed/counts; one model fault leaves other candidates possible | process + Pilot responsiveness/failure tests |
| A15 | Cancel/quit stops scheduling, kills/reaps stubborn owned child, retains accepted results and rejects incomplete ones; unrelated process survives | lifecycle/race tests, owned-process inspection |
| A16 | Classification/regression primary metrics independently correct, N/A explicit, ranking deterministic and cautious; unsupervised diagnostics correctly labeled | independent expected metrics + result rendering |
| A17 | Terminal inspection covers required task diagnostics; no browser; selected model is exact evaluated bundle with split provenance | four-task inspection/E2E evidence |
| A18 | Optional Try is implemented for all four tasks with typed inputs, validation, missing/unknown handling; no target input, no retraining | runtime tests + Try Pilot cases |
| A19 | One export type only; produces valid wheel from each model without network or refit; safe name/version/destination handling and no overwrite | exporter/atomic/failure tests, wheel inspection |
| A20 | Fresh consumer env installs generated wheel; no mlforge/Textual dependency; inference/transform equals in-app values/warnings within EXPORT_SPEC tolerance | all six real installed-artifact tests |
| A21 | Serialized types/versions/integrity checked; malformed/untrusted inputs refused; no raw rows/probes/paths bundled; model privacy limits stated | security tests + manifest/ZIP content scan |
| A22 | Entire flow keyboard usable at 100x30 and 80x24; resize/help restore focus, below-minimum allows cancel/quit; text keys never trigger navigation | Pilot full flows and visual/PTY evidence |
| A23 | Errors, empty/busy/partial-success states all have clear next actions; back edits invalidate stale state; export retry retains accepted bundle | state transition tests and UX review record |
| A24 | Complete suite including dependency/cycle/headless-import architecture checks, lint, build, metadata, comparisons, isolated release verifier pass; no critical skips or weakened tests | exact TEST_PLAN command results + CI URLs |
| A25 | README commands/environment/scope true; docs canonical and consistent; HOW_IT_WORKS and EXTENDING_MLFORGE match actual code/ownership; BUILD_STATE current and resumable; BUILD_LOG historical; V1_BUILD_REPORT has evidence, limitations and verified SHA | doc link/coverage review + final scoped diff |
| A26 | Final report identifies review hotspots and separates tested implementation SHA from evidence-only commit; worktree clean except declared ignored test artifacts | final git status/log and report |
| A27 | Interruption recovery reconstructs the next small unit from BUILD_STATE + Git + historical evidence, preserves partial local edits, treats unknown checks as unverified and does not restart completed work | P01/P09 recovery rehearsal evidence per RESUME_PROTOCOL |
| A28 | Every implemented screen passes DESIGN_SYSTEM screen-review checklist; visual/focus/state consistency, actual text contrast and clear next actions demonstrated | per-phase checklist + actual color/monochrome captures at supported sizes |

Release is not complete if a supported environment is unverified, network restrictions prevent clean install checks, or real process cancellation/security cases are skipped. Report blocked with completed work preserved; do not silently redefine the release target.
