# MLForge V1 specification index

This directory is the V1 engineering record. To use MLForge, start with [Getting started](../getting-started.md); for an overview of all documentation see [docs/README.md](../README.md).

Status: V1 is implemented and verified; see [V1_BUILD_REPORT.md](V1_BUILD_REPORT.md). Specifications were written on 2026-09-18, before implementation.

Start with REPOSITORY_AUDIT.md for the baseline the design grew from, then PRODUCT_SPEC.md and the canonical document for the subject you are changing. Each subject has exactly one owner:

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
| Phases V1 was delivered in, with their tests and completion gates | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) |
| Objective release requirements and evidence IDs | [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) |
| Verified release candidate, evidence, limitations and review hotspots | [V1_BUILD_REPORT.md](V1_BUILD_REPORT.md) |

Practical guides: [HOW_IT_WORKS](../HOW_IT_WORKS.md) explains control/data flow and ownership; [EXTENDING_MLFORGE](../EXTENDING_MLFORGE.md) states the project rules and maps seven extension types to the files and tests they touch. Both are guides, not competing normative contracts.

The README and audit are indexes/evidence; they do not override normative behavior. DESIGN_SYSTEM.md separates reusable visual rules from screen behavior so per-screen styles do not drift.

Documentation check: `python docs/v1/verify_planning.py` validates local links and fences, this index, the phase/acceptance structure and default palette contrast. CI runs it on every change. It does not replace semantic review or actual TUI verification.
