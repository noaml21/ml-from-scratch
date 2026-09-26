# Current resumable build state

Current pointer only; history: [BUILD_LOG.md](BUILD_LOG.md). Recovery: [RESUME_PROTOCOL.md](RESUME_PROTOCOL.md).

- Updated 2026-09-26 (Claude Code session); repo /home/noam/Projects/ml-from-scratch; branch v1/mlforge only. Planning base 0798b5b7d7ae07b0bd9fe454b3ddf90eba5434d5; ancestry preserved. External CLAUDE.md untracked/untouched.
- Verified candidates: P07 1bb15cf (CI 36262489129); P08 545d7e9 (CI 36266241401); P09 **a2092c04ed1244886cf587a49898f4bcc029fb89** (CI **36269528709 SUCCESS**: 707 passed on 3.12 and 3.13 with verify_release; local 707 passed/2061s, gate tools, release verifier, peak guard).
- **P01-P09 COMPLETE. Progress 27/30.** Active phase **P10 NOT STARTED → next**. Frozen code candidate for P10: a2092c0 unless a verified defect requires a new candidate.
- Next action (P10.1): with a clean tree whose non-doc files equal a2092c0 (`git diff a2092c0 HEAD -- src scripts tests pyproject.toml requirements .github` empty), run `.venv/bin/python scripts/verify_release.py` and `.venv/bin/python scripts/measure_peak_input.py`; then P10.2 doc consistency (AGENTS 'Planned' layout, ARCHITECTURE module tree: add application/artifacts.py, no tui/widgets/, dated-slice note; docs/v1/README status; README 'under construction'/'not yet release verified'; HOW_IT_WORKS 'P07 gate has not passed'; EXTENDING intro) and docs/v1/V1_BUILD_REPORT.md per CODEX_EXECUTION; P10.3 evidence-only commit, push, clean status, handoff.
- Running: none. Uncommitted: none after this docs commit.
- Invariants: UI presentation only; application state; execution processes; exact evaluated pipeline/no refit/train-only preprocessing; standalone export/no raw rows/no overwrite; no main merge/publish/release without explicit user request.
