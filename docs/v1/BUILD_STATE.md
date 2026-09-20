# Current resumable build state

Current pointer only; history: [BUILD_LOG.md](BUILD_LOG.md). Recovery: [RESUME_PROTOCOL.md](RESUME_PROTOCOL.md).

- Updated: 2026-09-20T08:36:15.200817+00:00.
- Repository: noaml21/ml-from-scratch; /home/noam/Projects/ml-from-scratch; branch v1/mlforge.
- Immutable planning base: 0798b5b7d7ae07b0bd9fe454b3ddf90eba5434d5; ancestry checked.
- Observed HEAD/last pushed: 6375e645d874f04afa3c11766ff42002172bc8ec.
- Active phase/unit: P04 / P04.3.a; phase IN PROGRESS; unit VERIFIED.
- Last verified phase: P03 at c2e395a; both supported CI jobs passed in 35465790338.
- Completed locally: P01-P03 verified; typed contracts, standalone export/runtime, bounded import/schema/Prepare and packaged examples.
- Incomplete: P04.3 evaluation/evaluated bundles/export integration and phase gate; P05-P10 not started.
- Uncommitted: evaluation.py, pipeline/test_metrics.py and owner/guide/checkpoint docs, verified; external CLAUDE.md preserved.
- Last verification: .venv/bin/python -m pytest -q tests/mlforge/pipeline tests/mlforge/test_architecture.py; 72 passed in 9.13s, session 50421 exit 0; scoped Ruff/check-format and git diff --check passed.
- Known failures: none in evaluated metric unit; schema-cap reachability review remains pending.
- Next exact action: commit/push P04.3.a metrics, then P04.3.b train/evaluate/save integration and actual large-vocabulary schema-cap reproduction.
- Relevant owners: ML_PIPELINE, DATASET_SPEC, EXPORT_SPEC runtime, ARCHITECTURE task/preprocessing boundaries, TEST_PLAN pipeline.
- Owned operation: none; P03 CI completed successfully.
- Verification cadence: focused tests + Ruff per unit; full/build/docs at phase gates; consumer installs only export/runtime impact or explicit gate. CI now dispatched at gates rather than every push.
- P04.3 review item: runtime schema read cap is 2 MiB despite larger allowed dataset/archive budgets; investigate a valid large vocabulary before phase completion (code-review risk, not yet reproduced).
- Completed top-level work units: 11/30 (P01-P03 and P04.1-P04.2); P04.3 in progress.
