# Current resumable build state

Current pointer only; history: [BUILD_LOG.md](BUILD_LOG.md). Recovery: [RESUME_PROTOCOL.md](RESUME_PROTOCOL.md).

- Updated 2026-09-26 (Claude Code session); repo /home/noam/Projects/ml-from-scratch; branch v1/mlforge only. Planning base 0798b5b7d7ae07b0bd9fe454b3ddf90eba5434d5; ancestry preserved. External CLAUDE.md untracked/untouched.
- Verified candidates: P07 1bb15cf (CI 36262489129); P08 **545d7e9410054967ba6e0dadc3346c6e7179a414** (CI **36266241401 SUCCESS**, 678 passed on 3.12 and 3.13; local package verifier EXIT 0 with 8 TUI-export consumer parity checks).
- **P01-P08 COMPLETE. Progress 24/30.** Active phase **P09 IN PROGRESS** (baseline 545d7e9).
- P09 local work (uncommitted in this checkout, not in this docs commit): scripts/rehearse_recovery.py (A27 rehearsal, passed → .mlforge-build/recovery-p09.json); Try/Export A28 resize transitions in tests/mlforge/tui/test_try.py + test_export_flow.py (6 passed); peak-input guard scripts/measure_peak_input.py found a real defect (20,000×100 load timed out at the 30s parse deadline) → datasets/inference.py Number fast path + reuse of detection values (identical schemas on 7 tables, 29-case Decimal oracle test, 109 dataset tests passed; peak load child 20.5s, guard passed: load 30.6s wall, train 83.5s, predict 3.8s, export 7.7s, child RSS 779 MiB); scripts/verify_release.py (composes verify_package + six-model consumer installs, report .mlforge-build/release-3.12.json) not yet run; README environments/privacy/limits/troubleshooting.
- Next action: run focused checks for the inference change (datasets + pipeline + application), commit `fix(data): infer peak-size tables within the parse deadline` and `test: rehearse recovery and verify release`, then P09.2 full-flow review and P09.3 `python scripts/verify_release.py`, full local pytest, acceptance matrix, exact-SHA CI.
- Running: none.
- Invariants: UI presentation only; application state; execution processes; exact evaluated pipeline/no refit/train-only preprocessing; standalone export/no raw rows/no overwrite; no main merge/publish/destructive cleanup.
