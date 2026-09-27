# MLForge terminal design system

Canonical owner of visual tokens, component states, responsive layout and visual quality gates. [UX_FLOW.md](UX_FLOW.md) owns screen order, keyboard behavior and navigation; [ARCHITECTURE.md](ARCHITECTURE.md) owns actual operation state. This is an implementation contract for Textual, not a web mockup or additional feature set.

## Identity and tokens
Calm dark blue-charcoal surfaces, mint accents, readable information and deliberate spacing. One default dark theme; no theme editor, decorative animations, gradients, emoji dependence or ASCII logo wall. Use named TCSS tokens shared across screens, never ad hoc screen palettes. Terminal fonts are user-controlled.

| Token | Default | Use |
|---|---|---|
| background | #101820 | App canvas |
| surface | #182630 | Content panels and table body |
| elevated | #223642 | Help/modal surface, distinct from underlying content |
| text | #E6EEF3 | Titles, labels, values, body |
| muted | #AEC0CC | Secondary explanation and disabled labels, still readable |
| accent | #66D9C3 | Primary action and focused border/marker |
| selected | #244247 | Chosen row/control background; use text foreground |
| on-accent | #101820 | Text on mint primary button |
| border | #526975 | Unfocused separators/borders; never body text |
| success | #66D9C3 | Completed/ready status, paired with words |
| warning | #F3C477 | Warning label and reason |
| error | #FF8A91 | Error label and recovery instruction |
| pending | #AEC0CC | Pending label; active work adds activity indicator |

Normal text/background pairs must meet >=4.5:1 contrast, including selection, disabled, error and modal states. Do not dim labels by arbitrary opacity. Borders are not a substitute for readable labels. Quantized or monochrome terminals must retain meaning through labels, markers and structure. If an actual terminal requires palette adjustment, update these canonical tokens and rerun the visual gates; keep the mint/charcoal identity.

## Hierarchy, spacing and structure
- One bold screen title/question, normal-weight control labels/values, muted secondary text. Reserve bold for title, focused action and short status labels; avoid all-caps paragraphs.
- Body padding: two columns horizontally, one row vertically where available. Use one blank row between groups, no blank rows between every table row. At 80x24 reduce panel decoration before reducing usable content; never shrink text or hide critical warnings.
- One thin border per meaningful region (table, group or modal); avoid nested boxes and borders around each label. Focused interactive region gains accent border plus a visible focus marker. Keep the same control shape across screens.
- After Welcome, compact header shows MLForge and named stage from UX_FLOW. Footer is one or two rows of active shortcuts; status is a separate short line. Status/footer never scroll away with the body.
- One visually primary action per decision screen. Back is consistently secondary on the action row. Welcome has only its Enter instruction. A recommended/default choice is visibly selected but never automatically confirmed.

## Interaction states
| State | Required presentation |
|---|---|
| Idle | Normal text/surface and quiet border; no focus marker |
| Focused | Accent border or leading `>` plus bold label; keep checked/selected marker independent |
| Selected/checked | Selected background and `[x]` (or equivalent stable check marker); unchecked `[ ]`. A selected row can lose focus without losing its marker |
| Disabled | Readable muted label plus `Unavailable`/reason; cannot activate. Reason is visible nearby or accessible by the containing list's help; do not require focusing an unfocusable control to discover it |
| Success | `Completed`/`Ready` plus check marker and success token; actionable result remains reachable |
| Warning | `Warning:` plus concrete consequence and next action, near affected control; essential warnings never live only in help |
| Error | `Error:` plus short cause and recovery action; preserve input, focus invalid field when appropriate; no raw traceback |
| Pending | `Pending` label, no spinner for a model not yet running |
| Loading/running | Actual operation name, activity indicator and elapsed time; disable only conflicting controls, keep help/cancel/quit available |
| Cancelling | `Stopping…` until ownership cleanup completes; do not show stopped/success prematurely |

Focus and selection must be distinguishable in monochrome. Hover may reinforce a control but reveals no essential information and is never required. Input errors use both a field message and an error marker; valid previous entries remain intact.

## Components
**Tables:** bold header, aligned columns, right-aligned numeric metrics, left-aligned names/categories. Units belong in headers or values consistently. Use a visible selected-row marker. Truncate with an ellipsis and expose complete literal values through details/help. Horizontal/vertical scrolling stays in the table; selection/help does not silently change data. Keep model status visible; failed metrics display an explanatory dash, never a fabricated zero. No dense decorative striping or color heatmaps required.

**Help:** one catalog and consistent title/topic/content/close structure. At wide sizes a panel is allowed only if minimum widths below fit; otherwise use a modal. Help is scrollable, keyboard reachable and returns exact previous focus/selection. Never obscure the fact that a background operation is running.

**Modals:** elevated surface with one thin border, title, concise body and explicit actions. Trap focus while open; Esc dismisses non-destructive dialogs and restores focus. Destructive choices never receive the default focus. Use UX_FLOW's explicit cancellation/quit confirmation semantics; do not add confirmation to ordinary steps. At 80x24 allow up to 76x20 cells, with scrollable body and pinned actions; long content must not push Close/Cancel out of reach.

**Footer:** stable ordering: navigation, selection/toggle, help, Back, quit/cancel; show only applicable actions. Use F1 when editing text. At 80 columns abbreviate descriptions or wrap to two rows; never omit the sole way to cancel/quit. UX_FLOW owns key bindings.

**Progress:** model completion counts are factual; fit uses a spinner + operation + elapsed, no invented percentage/ETA. Static `Working…` remains understandable if animation is unavailable. Model rows show Pending/Running/Completed/Failed, with a short safe failure reason. Success is established by core events, not a visual timer.

## Empty, error and partial-success composition
Use a short title, one sentence explaining the situation, and one primary recovery action. Example: `No usable features` → reason → `Back to features`. Empty results are never an empty table with no explanation. For partial success show `2 completed · 1 failed` (actual counts), retain selectable valid results and expose each failure reason. A cancelled run labels retained results as cancelled/partial. Do not use an all-success banner or force retraining successful candidates. All-failed state provides inspection and Back, with no exportable model.

## Layout and transitions
Preferred verification size is 100x30; minimum supported is 80x24. Use terminal **cell** widths, not Python string length; wide Unicode paths/values must not break borders. No RTL interface/localization requirement is added in V1; arbitrary Unicode data is still displayed safely.

At 100x30: two-column layouts are allowed where useful. With four columns outer padding and a two-column gutter, allocate at least 58 columns to main content and 32 to help; if that cannot fit, stack or use a modal. Do not squeeze two forms side by side merely because the terminal is wide. Large terminals retain a readable main form width (up to 100 columns centered); data tables may use remaining width.

At 80x24: use one column. Reserve at most two rows for header, one for status, two for actions and two for footer, leaving at least 17 rows for the body region (including its padding). Scroll long forms/tables within that region. Important validation remains beside its field or in a visible status summary. Actions are reachable without horizontal page scrolling. Help uses a modal; footer may wrap. No clipping at the right edge.

Below either 80 columns or 24 rows: replace normal content with a compact dimensions/resize message, `Resize to at least 80 × 24`, and available Cancel/Ctrl+Q instructions. At extremely tiny sizes text may be clipped, but bindings remain active. Core work/status/cleanup continue; the guard is not a cancel or reload. Restore screen, field contents, scroll and focus when size recovers.

Transitions are immediate state changes with no artificial delay, flashing full-screen effects or typewriter text. Show loading only for actual work. Back/help/error/resize preserve valid input and focus under UX_FLOW. Async completion updates status without stealing focus; stale events never redraw a newer experiment (ARCHITECTURE revision rules). No raw child output flashes onto the terminal. Normal quit/handled failure restores the terminal.

## Required screen review checklist
Apply during P06, P07 and P08, then repeat across the full flow in P09. Record per-screen evidence and defects in that phase's BUILD_LOG entry; do not mark a screen polished just because widgets render.
1. A first-time user sees one clear title/question and the next action without opening help.
2. Normal content fits the documented terminal sizes; scrollable content and all actions remain reachable, without clipped labels or hidden warnings.
3. Focus, selection, disabled reason and busy state are distinguishable without color; inspect a monochrome capture as well as the normal palette.
4. Keyboard-only forward/back/help flow preserves input and focus; actions do not steal typed characters.
5. Text has readable contrast. Check actual text/background pairs (target >=4.5:1 for normal text in the default palette); do not assume the palette alone proves every selected/disabled state is readable.
6. Empty, loading, validation failure, runtime failure and success each explain the next action using brief, consistent wording.
7. Tables align values, clearly label units/metrics and show full details on demand; displayed mock metrics are never used as real results.
8. Switching screens or resizing does not flash raw logs, lose state or make a primary control unreachable; real async work remains cancellable.
9. Export success explains what was created and how to use it, with a selectable path and task-correct example.

Any ambiguous primary action, invisible focus, inaccessible action at 80x24, severe contrast issue or unreadable error blocks that phase. Fix these while building the screen, not only in a final cosmetic pass. TUI screenshots and PTY evidence must come from the actual implementation; design illustrations are not release evidence.
