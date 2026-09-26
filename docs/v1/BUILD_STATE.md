# Current resumable build state

Current pointer only; history: [BUILD_LOG.md](BUILD_LOG.md). Recovery: [RESUME_PROTOCOL.md](RESUME_PROTOCOL.md).

- Updated 2026-09-26 (Claude Code session); repo /home/noam/Projects/ml-from-scratch; branch v1/mlforge only. Planning base 0798b5b7d7ae07b0bd9fe454b3ddf90eba5434d5; ancestry preserved. External CLAUDE.md untracked/untouched.
- Verified candidates: P07 1bb15cf (CI 36262489129); P08 **545d7e9410054967ba6e0dadc3346c6e7179a414** (CI **36266241401 SUCCESS**, 678 passed on 3.12 and 3.13; local package verifier EXIT 0 with 8 TUI-export consumer parity checks).
- **P01-P08 COMPLETE. Progress 24/30.** P09 gate pending.
- Active phase **P09 IN PROGRESS**: P09.1 VERIFIED, P09.2 VERIFIED, P09.3 local VERIFIED; phase gate RUNNING on candidate **a2092c04ed1244886cf587a49898f4bcc029fb89** (commits 37b3034 inference fix, 840e52c rehearsal/resize tests, f4c4f27 export polish, a2092c0 release verifier + README/CI). Evidence and acceptance matrix: BUILD_LOG P09 entry.
- RUNNING (owned, local): full pytest `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q` started 23:26 IDT → .mlforge-build/p09-full-pytest.log (UNKNOWN until EXIT line). RUNNING (remote): CI https://github.com/noaml21/ml-from-scratch/actions/runs/36269528709 on a2092c0, consumer_installs=true (now runs verify_release.py).
- Next: when both succeed, run gate tools (scratch gate_tools.sh equivalent: offline isolated build, twine, pip check, demos, diff check), record P09 COMPLETE 27/30 (docs commit), then P10.1 freeze: final verification on the frozen candidate (verify_release, full suite, CI), P10.2 V1_BUILD_REPORT + doc consistency (A25), P10.3 evidence commit per CODEX_EXECUTION SHA protocol. If CI fails, inspect logs first; the workflow YAML changed in a2092c0.
- Uncommitted: docs/v1/BUILD_LOG.md P09 entry and this file (docs only).
- Invariants: UI presentation only; application state; execution processes; exact evaluated pipeline/no refit/train-only preprocessing; standalone export/no raw rows/no overwrite; no main merge/publish/destructive cleanup.
