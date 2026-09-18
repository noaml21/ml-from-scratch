# Single implementation handoff

The final delivery message supplies the exact verified planning SHA. Substitute it below; a template cannot embed the SHA of the commit containing itself. Never substitute the original first planning commit. If resuming an existing build, preserve its recorded planning base and inspect local work first.

```text
Build MLForge V1 in noaml21/ml-from-scratch from planning/mlforge-v1 at <VERIFIED_PLANNING_SHA>, on v1/mlforge. Read AGENTS.md and all canonical specifications in docs/v1/, especially CODEX_EXECUTION.md. Inspect Git before editing; preserve existing partial work and follow RESUME_PROTOCOL.md when continuing.

Execute all phases of IMPLEMENTATION_PLAN.md autonomously. Maintain BUILD_STATE.md checkpoints and BUILD_LOG.md history, commit and push small verified increments, test continuously, and keep canonical docs current. Follow UX_FLOW.md and DESIGN_SYSTEM.md. Preserve the educational baseline; do not expand scope or ask for confirmation for ordinary implementation decisions. Stop only for genuine blockers under CODEX_EXECUTION.md.

Finish only after every ACCEPTANCE_CRITERIA.md gate and final verification pass. Create V1_BUILD_REPORT.md with evidence and verified commit provenance, push v1/mlforge, and report the final SHA. Do not merge into main or publish packages.
```

After interruption, in the same checkout, this is sufficient: "Continue MLForge V1 from the repository state. Read AGENTS.md and follow the documented resume protocol." A fresh clone only contains pushed work; see RESUME_PROTOCOL for local-only recovery limits.
