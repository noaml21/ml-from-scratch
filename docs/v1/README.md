# MLForge V1 specification index

Status: implementation-ready planning; production V1 has not been built.
Planning date: 2026-09-18. All prose below this directory is in English so subsequent implementers and reviewers need no chat context.

Start with REPOSITORY_AUDIT.md for what actually exists. Then read PRODUCT_SPEC.md and every canonical document in the table. CODEX_EXECUTION.md controls autonomous execution, not product behavior.

| Subject / canonical owner | File |
|---|---|
| Baseline evidence, technical debt, reference lessons | [REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md) |
| Scope, tasks, supported platforms, explicit exclusions | [PRODUCT_SPEC.md](PRODUCT_SPEC.md) |
| Screens, navigation, keyboard semantics, focus restoration | [UX_FLOW.md](UX_FLOW.md) |
| Visual tokens, component states, layouts and screen quality gates | [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) |
| Boundaries, contracts, process lifecycle, dependencies | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Formats, cells, types, overrides, resource limits, preparation prompt | [DATASET_SPEC.md](DATASET_SPEC.md) |
| Eligibility, features, split, transforms, model defaults, metrics | [ML_PIPELINE.md](ML_PIPELINE.md) |
| Artifact, Predictor API, serialization, versioning, export security | [EXPORT_SPEC.md](EXPORT_SPEC.md) |
| Test fixtures, verification commands, adversarial and UX checks | [TEST_PLAN.md](TEST_PLAN.md) |
| Ordered phases and commit gates | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) |
| Objective release requirements and evidence IDs | [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) |
| Branching, autonomy, decisions and finish protocol | [CODEX_EXECUTION.md](CODEX_EXECUTION.md) |
| Checkpoint cadence, interrupted-work recovery and durable continuation | [RESUME_PROTOCOL.md](RESUME_PROTOCOL.md) |
| One reusable entry prompt for start or resume | [CODEX_PROMPT.md](CODEX_PROMPT.md) |
| Sole current resumable snapshot; initially not started | [BUILD_STATE.md](BUILD_STATE.md) |
| Historical implementation evidence; initially not started | [BUILD_LOG.md](BUILD_LOG.md) |
| Planning consistency/coverage audit | [PLANNING_REVIEW.md](PLANNING_REVIEW.md) |

Practical guides: [HOW_IT_WORKS](../HOW_IT_WORKS.md) explains control/data flow and ownership; [EXTENDING_MLFORGE](../EXTENDING_MLFORGE.md) maps seven extension types to planned files and tests. Both are guides, not competing normative contracts.

The implementer creates `V1_BUILD_REPORT.md` at release. Do not create a report that implies unperformed verification. README and audit are indexes/evidence; they do not override normative behavior. There are no hidden requirements from the planning chat.

Extra documents beyond the requested set: this index prevents duplicate ownership; the repository audit anchors design in code; PLANNING_REVIEW records cross-document coverage; RESUME_PROTOCOL owns interruption recovery; CODEX_PROMPT provides one reusable start/resume instruction. A separate generic ADR system, project database or research backlog is unnecessary for V1.

Continuation starts at BUILD_STATE.md and follows RESUME_PROTOCOL.md; BUILD_LOG.md preserves history. DESIGN_SYSTEM.md separates reusable visual rules from screen behavior. These separate files prevent a long history from hiding the next action and prevent per-screen styles from drifting. CODEX_PROMPT.md uses the verified planning SHA supplied in the launch instruction; an existing implementation retains its recorded base.

Planning checks: `python3 docs/v1/verify_planning.py` validates local links, ownership pointers, phase/acceptance coverage and default palette contrast. It does not replace semantic review or actual TUI verification.
