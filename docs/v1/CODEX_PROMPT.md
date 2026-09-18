# One prompt for start or resume

Use the following prompt in the MLForge repository. It supersedes the earlier prompt pinned to the first planning commit. Reuse it after an interruption; do not recreate the implementation branch or discard local edits.

```text
Build or continue MLForge V1 in noaml21/ml-from-scratch.

Read AGENTS.md, docs/v1/README.md and all authoritative specifications, including CODEX_EXECUTION.md and RESUME_PROTOCOL.md. Inspect Git and BUILD_LOG.md before editing. If v1/mlforge does not exist, create it from the latest complete planning/mlforge-v1 branch; otherwise continue its existing work and preserve uncommitted changes. Never modify or merge into main.

Work autonomously through IMPLEMENTATION_PLAN.md, one small work unit at a time. Maintain the Current checkpoint in BUILD_LOG before edits, around long checks and after verified commits. On resume reconcile it with actual files and test results; don't restart completed phases or assume interrupted checks passed. Commit and push small verified increments; pass each phase's full gate before advancing.

Deliver the complete scoped V1 with the visual and usability requirements in UX_FLOW.md. Preserve the educational algorithms, continuously test, update canonical docs, and don't expand scope or await approval for ordinary implementation decisions.

Finish only when ACCEPTANCE_CRITERIA.md and final release verification pass. Create V1_BUILD_REPORT.md with evidence and commit provenance. Follow the documented blocker policy; never weaken tests, claim unverified success, merge or publish packages.
```
