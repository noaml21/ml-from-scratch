# Autonomous V1 execution protocol

## Mission and reading
Build MLForge V1 in this repository from the complete planning branch. No chat context is required. Work autonomously until every acceptance gate passes, or an actual stop condition below is reached.

On initial onboarding, before production coding read root AGENTS.md, docs/v1/README.md, REPOSITORY_AUDIT.md, docs/HOW_IT_WORKS.md, docs/EXTENDING_MLFORGE.md, every normative specification, IMPLEMENTATION_PLAN.md, TEST_PLAN.md, ACCEPTANCE_CRITERIA.md, BUILD_STATE.md, BUILD_LOG.md and RESUME_PROTOCOL.md. On continuation use RESUME_PROTOCOL's focused reading sequence. Re-read the owning contract before each phase. Inspect actual code and git status; specifications describe planned as well as existing files.

## Authority and conflicts
1. Explicit current user instructions and applicable higher-priority execution safety rules.
2. PRODUCT_SPEC.md owns V1 scope/platforms/non-goals.
3. Topic owners in docs/v1/README.md own detailed behavior in their area (DATASET, ML_PIPELINE, EXPORT, ARCHITECTURE, UX_FLOW, DESIGN_SYSTEM).
4. ACCEPTANCE_CRITERIA and TEST_PLAN verify that behavior; they may not silently redefine it.
5. IMPLEMENTATION_PLAN controls order; CODEX_EXECUTION controls workflow; AGENTS/README summarize.
6. BUILD_STATE records the current snapshot; BUILD_LOG records historical observations/decisions; neither overrides specifications.

For an apparent conflict, first locate the topic owner and apply it, repair contradictory derivative wording/tests, and log the resolution. For an uncovered internal detail choose the smallest correct solution that preserves invariants and public UX/API; record rationale and tests in the owner document + BUILD_LOG, then proceed. Never use ambiguity as justification for scope growth. A genuine unresolvable conflict affecting product scope, privacy or public compatibility is a stop condition.

## Git
Repository: noaml21/ml-from-scratch. Planning: planning/mlforge-v1. Stable baseline: main at audit SHA; implementation: v1/mlforge.

Fetch/inspect refs normally; no forced update. If implementation branch is absent, create it from the exact verified planning commit supplied in the launch instruction, not from main; verify that SHA belongs to planning/mlforge-v1 and record it as the immutable planning base in BUILD_STATE. If no SHA was supplied, resolve the current complete planning tip once and record it. If already present, verify its recorded planning ancestry and read BUILD_STATE plus relevant BUILD_LOG evidence before continuing. Preserve dirty work and inspect it; don't reset/stash/discard without understanding ownership. Never restart an existing implementation branch or silently move its base to a newer planning tip. Work only on v1/mlforge after setup. No main changes/merge, history rewrite, destructive cleanup or unrelated repository edits.

Small logical phase commits contain code + tests + affected docs + BUILD_STATE/BUILD_LOG updates after checks pass. Multiple commits per phase are fine; don't advance the gate until all phase checks pass. Record commit subject in its own log entry, and fill its hash in the next log update (avoids self-reference). Push this dedicated branch normally when repository access is configured; no force. Do not publish packages, create releases or merge. A PR is optional only if later explicitly requested.

## Continuous work and checkpoints
For each phase:
1. Mark IN PROGRESS with baseline SHA and scope; inspect relevant current code.
2. Implement the smallest complete change, add non-trivial logic tests and preserve existing tests.
3. Run targeted checks, full suite, relevant lint/build and inspect diff for unrelated changes.
4. Update canonical docs/help/README only where affected; keep advertised behavior honest.
5. Record actual commands, environments, results, failures/repairs, known limits and gate status.
6. Commit and normally push a verified boundary, reconcile BUILD_STATE, and proceed directly to the next work unit or phase.

Do not stop after writing a plan, creating a skeleton, finishing one phase, hitting ordinary test failures or choosing a normal implementation detail. No requests to the user to select internal variable names, module decomposition, styling minutiae or compatible package patch versions. Do not ask permission again for ordinary authorized code/test/docs/commit work. Required permissions imposed by the execution environment are handled honestly, not bypassed.

Install project-local dependencies and use local temporary artifacts; no sudo/system changes. Network for dependency setup and normal Git/CI is distinct from the application's offline contract. Do not access secrets/.env or include private data in artifacts/logs.

## BUILD_LOG historical evidence
The checkpoint cadence, field schema and restart algorithm are owned by [RESUME_PROTOCOL.md](RESUME_PROTOCOL.md). Maintain BUILD_STATE as the sole current checkpoint and BUILD_LOG as historical evidence.
Update docs/v1/BUILD_LOG.md at meaningful boundaries, not only the end. Each phase entry contains:
- status NOT STARTED / IN PROGRESS / VERIFIED / BLOCKED;
- objective, started-from SHA, files changed;
- implementation decisions and canonical doc changed;
- commands/results/environment and acceptance IDs covered;
- failures + serious repair attempts (hypothesis, change, observed result);
- commit subject/hash once known;
- next exact action and remaining risks.

Keep it concise; link detailed generated local/CI reports rather than paste unlimited logs. Never include secrets or user data. Follow RESUME_PROTOCOL for any interruption, including a hard stop with a stale checkpoint. An unchecked partial change is not a passed gate.

## Failure and stop policy
Fix failures at root cause. Investigate up to three serious distinct repair attempts for the same blocking failure; repeated command execution alone is not an attempt. Never weaken acceptance, delete tests, skip a supported task/environment, switch to unsafe serialization, fake metrics or claim tests passed to get unstuck.

Stop only for:
- required repository/installation/CI/environment capability unavailable with no authorized path;
- a genuine scope/privacy/API conflict that owner documents cannot resolve;
- destructive/irreversible action beyond authorization;
- the same blocking failure persisting after three serious evidence-based repairs;
- inability to meet a mandatory acceptance criterion.
First finish independent work within the current phase that is safe and useful. Record blocker, evidence, attempts and the minimal user/external action needed. Do not start later phases around the failed gate or call V1 complete. Lack of time/context is a checkpoint, not invented completion; continue in available sessions from BUILD_STATE and actual Git state.

## Scope control
No extra tasks/models/importers/export formats/tuning/cloud/history engine. A bug fix that enforces existing contract is in scope. A newly appealing feature goes into a brief deferred note, not production code. The original NumPy track remains educational; don't use it as an untested shortcut around sklearn/skops contracts.

## Final verification and report
Complete every TEST_PLAN release command, both supported CI environments, installed app PTY/Pilot and six exported-wheel tests. Attach each acceptance ID to actual evidence. Verify no source-data mutation/network path, no stale pipelines, no critical TODOs or severe UX gaps. Review diff/history/docs; repeat applicable checks after repairs.

Produce docs/v1/V1_BUILD_REPORT.md with:
- final architecture and module boundaries;
- implemented functionality and intentional omissions;
- exact tested Python/Linux/dependency versions;
- commands/test results, CI URLs, skipped tests with reasons (no critical skip accepted);
- clean installation and entrypoint proof;
- offline export/install/prediction equality proof across all six models;
- keyboard/resize/error/cancellation visual and PTY evidence;
- documentation/acceptance status;
- known limitations and review hotspots for Astra (leakage, serialization, worker races, package installation, schema semantics, UX);
- final verified implementation commit SHA.

SHA protocol: commit final production code first; run final verification against that immutable SHA. Put that literal SHA in the report. Then make one evidence-only docs commit containing report/log/acceptance results. A file cannot contain its own commit's SHA. Include a "Final repository evidence commit" field with the deterministic retrieval command `git log -1 --format=%H -- docs/v1/V1_BUILD_REPORT.md`; return that resulting literal SHA in final handoff. Distinguish it from the verified implementation SHA; do not amend repeatedly to chase self-reference. If any production change occurs after verification, create a new candidate and repeat affected verification.

Final response should name branch, final repository SHA, verified implementation SHA, report path, test/acceptance result and any actual blocker. Do not merge/publish. Ordinary implementation decisions must not await human confirmation.
