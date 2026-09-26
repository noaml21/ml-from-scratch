# Current resumable build state

Current pointer only; history: [BUILD_LOG.md](BUILD_LOG.md). Recovery: [RESUME_PROTOCOL.md](RESUME_PROTOCOL.md).

- Updated 2026-09-26 (Claude Code session); repo /home/noam/Projects/ml-from-scratch; branch v1/mlforge only. Planning base 0798b5b7d7ae07b0bd9fe454b3ddf90eba5434d5; ancestry preserved. External CLAUDE.md untracked/untouched.
- P07 verifier-repair candidate **1bb15cff5928fe66728861a65be882175f5c1e09** pushed (origin verified). Product code identical to 799ef21/84376c0 lineage; change is scripts/installed_dataset_smoke.py visible-screen synchronization + tests/mlforge/tui/test_terminal_screen.py.
- **P01-P07 COMPLETE. Progress 21/30.** P07 closed on 1bb15cf: local package verifier EXIT 0 (.mlforge-build/p07-package-1bb15cf.log), CI **36262489129 SUCCESS** (3.12: 659 passed/1525.73s; 3.13: 659 passed/912.08s; package verifier, build, twine, demos, lint, planning). Details in BUILD_LOG.
- Active phase **P08 IN PROGRESS** (baseline 1bb15cf). Unit **P08.1 NEEDS CHECK** and **P08.2 EDITING**, both uncommitted/local-only in this checkout (not in the P07 docs commit).
  - application: state.InputField; artifacts.input_fields (hash-verified fitted schema.json); Service.prediction_fields(). worker _predict maps runtime "Record N: CODE: field" to field-scoped PREDICT_INPUT (row/column, friendly message, no value echo).
  - tui: screens/trial.py Trial form (Input/Select/Toggle Missing per fitted field, known categories hint + suggester, Predict via Service.predict, field errors in place, warnings, task outputs); SelectedModel "Try the model"; help "try"; theme rules. shell.Toggle promoted from dataset HiddenFiles ([x]/[ ] monochrome) and reused for Show all + Missing.
  - tests: application/test_try_inputs.py (12 passed), tui/test_try.py (4 passed before Toggle/monochrome assertion edit).
- Running: P08.1 subsystem batch → .mlforge-build/p08.1-subsystem.log (try, sources, configuration, results, application, worker, architecture, terminal screen).
- Next: on subsystem pass commit P08.1 `feat(prediction): add typed in-terminal model trials`, push. Then P08.2 Export screen (draft in session scratch only; re-create from EXPORT_SPEC/UX_FLOW if lost): destination/module/version form, privacy/compat note, Service.export, field-mapped errors (PACKAGE_NAME/VERSION, EXPORT_EXISTS/IO), success screen with path/pip/task example, Back to results/Quit.
- Invariants: UI presentation only; application state; execution processes; exact evaluated pipeline/no refit/train-only preprocessing; standalone export/no raw rows/no overwrite; no main merge/publish/destructive cleanup.
