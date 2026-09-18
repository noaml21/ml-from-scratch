# Reliable implementation continuation

Canonical owner of implementation checkpoints and restart reconciliation. This is a developer workflow, not an MLForge end-user project-history feature. Scope, phase gates and UX remain owned by their existing specifications.

## Durable state, not a final goodbye message
A usage-limit interruption can arrive without time to write a handoff. Maintain checkpoints throughout work; never wait for a warning or assume the agent knows its remaining tokens. This protocol does not replenish usage, schedule future execution, or guarantee automatic restart. Once execution is available, the same launch prompt works in the existing session or a new session with this checkout.

Progress sources have distinct roles:
- IMPLEMENTATION_PLAN.md: ordered phases and small work-unit IDs; what to do.
- BUILD_STATE.md: the sole current pointer; where to continue.
- BUILD_LOG.md: append-only historical phase evidence, decisions and repair attempts.
- Git, working files and actual test evidence: what really exists and what passed. They override a stale progress claim, but do not override product specifications.

No separate TODO database, parallel handoff file, auto-resume daemon or token-counting service. CODEX_PROMPT.md is a reusable entry instruction, not another specification.

## Small work units
Use the Pxx.n units in IMPLEMENTATION_PLAN. Work on one unit at a time. A unit is one reviewable outcome with a targeted check, not an entire subsystem rewrite. If too large, split into Pxx.n.a/Pxx.n.b in that phase's log before editing. Finish only the current unit before moving to the next; finishing a unit does not imply that its phase passed. Complete all phase checks before a phase is VERIFIED.

Update BUILD_STATE (not after every line of code):

1. At phase start and before a broad or risky edit: record the intended scope, affected paths, recovery boundary and check. A checkpoint does not authorize a destructive operation.
2. Before the first edit in a unit: record scope, paths, baseline and next check.
3. After a coherent edit batch, before moving to another concern: mark code present but tests pending if appropriate.
4. Before a long test/build/install: record exact command and RUNNING/UNKNOWN, never PASS in advance.
5. After receiving its exit result: record outcome, environment, evidence location and next action.
6. Before commit: record the reviewed paths, passing checks and intended commit subject. After commit: reconcile the observed SHA; after push: record the observed remote SHA.
7. Before any voluntary stop, genuine blocker or known approaching context/session limit, if execution remains available: record incomplete work and one exact next action.

At most one small edit batch should normally be ahead of the written checkpoint. No wall-clock or token-count promises; a crash in the middle of an edit is recovered by inspecting files. A known near-limit condition means complete a safe checkpoint, not rush a large unverified commit.

## Current checkpoint schema
Keep BUILD_STATE normally <=40 lines. Replace its current snapshot; append meaningful historical evidence to BUILD_LOG. State-only updates need not create a commit per edit batch.
- Updated UTC timestamp; observed repository path and branch.
- Planning-base SHA; observed HEAD SHA (before this log-only edit is fine).
- Active phase and work-unit ID; phase status; unit status NOT STARTED / EDITING / NEEDS CHECK / VERIFIED / BLOCKED.
- Last verified phase and code commit; last completed unit.
- Completed work in current phase: concrete files/functions/screens, at most three bullets.
- Incomplete work: exact remaining unit scope, including partially edited functions.
- Relevant canonical specs to reread; checks that must be rerun.
- Uncommitted work: paths, purpose, whether checked; explicitly record none when clean.
- Last check: exact command, cwd, interpreter/environment, completed exit status or UNKNOWN/RUNNING, report path if any.
- Known failure and serious repair count; unresolved assumptions with owner-document links.
- Next action: one precise operation and its next verification command; no vague 'continue implementation'.
- Owned running operations: identifier/start time/command/output path if known, or none/unknown.
- Last remote verified commit; local-only work or a push error if any.

Never record tokens, credentials, private dataset contents or full raw diffs in the log. A process identifier is evidence to inspect, not permission to kill an unrelated or reused PID. State tied to a local machine must be marked local-only.

## Resume algorithm (same or new session)
1. Read AGENTS, BUILD_STATE, this protocol, the active phase in IMPLEMENTATION_PLAN and its relevant reading map. Read the listed canonical owners and cross-cutting PRODUCT_SPEC/ARCHITECTURE/CODEX_EXECUTION invariants before edits. Initial implementation onboarding reads all canonical specifications; a continuation may read only relevant contracts, expanding when affected boundaries or missing evidence require it. Do not ask the user to recount the chat.
2. Inspect cwd, git status --short, current branch, recent git log, staged and unstaged diffs and relevant untracked files. Confirm v1/mlforge and recorded planning ancestry. If implementation does not exist yet, follow CODEX_EXECUTION branch setup. Do not switch a dirty checkout away from its work or reset/stash/delete it.
3. Reconcile the checkpoint against actual files/commits. Preserve useful uncommitted work, including partial edits. A stale 'verified' entry is downgraded to NEEDS CHECK for affected work. If a completed verified commit is ahead of the log, reconstruct its evidence and repair the pointer; don't rebuild the phase from scratch.
4. Inspect any previously running operation and saved results before launching a duplicate. If an exit status cannot be established, mark UNKNOWN and rerun the relevant check safely. Never infer success from missing output or a detached process. Do not blindly kill processes or rerun side effects such as Git pushes/exports.
5. Run the current unit's targeted checks and relevant last-verified boundary checks. Restore a project-local environment using committed constraints when needed. Test failures remain part of the current phase; carry forward the repair history rather than resetting the three-attempt count after every session.
6. Write a reconciled BUILD_STATE with the next unit/action, then continue autonomously through remaining phase gates. Do not restart completed phases merely because conversation context was lost.

## Commit and remote durability
Only commit code after the applicable checks pass, as required by CODEX_EXECUTION. Do not label an untested WIP commit as verified or weaken a check to get a checkpoint into Git. Unverified partial code and checkpoint edits remain in the existing local checkout until repaired. A documentation-only checkpoint commit is allowed when it does not bundle unchecked production changes; it must state that those changes are local-only.

After each small verified implementation commit, update BUILD_STATE with the observed code SHA; include that update in the next coherent commit or an evidence-only checkpoint commit and normally push v1/mlforge if configured. No force, merge to main, or hidden branch switching. Do not recursively create commits merely to store a state file's own commit SHA: observed HEAD and last verified code SHA are explicitly historical observations. Record a push failure; local verification and remote backup are separate facts.

Same-checkout resumption can inspect uncommitted files. A different computer/fresh clone only receives pushed commits: it cannot recover files left solely on another machine or unsaved edits. Report that gap precisely instead of pretending recovery is lossless. Keep the original checkout until local work has been verified and pushed.

## Recovery rehearsal
Before completing P01, rehearse continuation from the populated checkpoint: reconstruct active unit and next check without relying on conversation, then document result. Repeat in P09 against three development scenarios: a stale pointer with actual partial local edits, a check with unknown exit status, and Git ahead of the log. Use a disposable repository fixture for synthetic cases; do not reset/delete working project files. Evidence must show preserved edits, no false verification and the same next planned unit. No need to deliberately exhaust quota or create a new Codex task.

## User action
For continuation, "Continue MLForge V1 from the repository state. Read AGENTS.md and follow the documented resume protocol" is sufficient. Use CODEX_PROMPT.md for the initial launch; open the same repository/checkout when local edits exist. In a retained conversation, a simple request to continue under this protocol suffices. No new product decisions or recap should be needed.

Codex CLI also supports reopening saved chats with `codex resume`; see the [official CLI documentation](https://learn.chatgpt.com/docs/codex/cli). Repository recovery remains necessary even when chat history is available. This plan makes no claim that a usage reset starts work automatically.
