# UX flow and interaction specification

## Shell and visual system
Full-screen Textual app, one primary task per screen. Persistent compact brand/step header, scrollable body, visible status and context footer. Primary surface #101820, elevated #182630, text #E6EEF3, muted #AEC0CC, accent #66D9C3, warning #F3C477, error #FF8A91; tune for real terminal legibility without relying on color alone. Use restrained bold labels, 1-row vertical gaps and 2-column horizontal padding. No ASCII logo wall, dense dashboard or animation beyond activity feedback.

At >=100 columns split preview/help where useful; 80..99 stack panels and scroll. Primary buttons/labels remain reachable at 80x24; tables scroll horizontally and expose selected-cell details. Below 80x24 show dimensions and "Resize to at least 80 × 24"; keep Cancel/Ctrl+Q functioning and restore prior focus/state on resize. Resize never reloads data or retrains.

Tab/Shift+Tab move among controls. Up/Down navigate focused lists; Left/Right scroll tables where appropriate. Enter activates focused action/selects. Space toggles selections. ? opens help for the focused item, Esc closes help restoring exact focus. B/Esc go back when not editing/modal. Q quits outside text inputs; Ctrl+Q works everywhere through quit confirmation/cleanup. In editable text, q/b/? and Space are normal characters; F1 provides help and Esc exits field/modal before back. Never intercept these letters as global priority bindings. Footer shows only active keys, with F1 in text fields. Mouse is optional.

Help is a compact scrollable modal at small sizes, optional side panel at wide sizes, backed by one help catalog. It must not move the selected list item, advance a workflow or clear inputs. Focus order follows reading order; screen entry focuses its primary list/input, errors focus the invalid field, async completion never unexpectedly steals focus.

## Welcoming visual direction and screen quality gate
The experience should feel calm, inviting and deliberate to a first-time user. The existing palette is the V1 default dark theme; one coherent theme is sufficient, no theme editor or decorative feature scope. Use named TCSS tokens for the colors defined above, so screens cannot drift into unrelated styles.

| Role | Treatment |
|---|---|
| Background and structure | Dark blue-charcoal main surface, slightly lighter content areas, restrained thin separators; no border around every label |
| Primary choice/focus | Turquoise accent with a visible marker/border and clear selected text; focus and checked state must be visually distinguishable |
| Success | Turquoise check plus a word such as Completed; no color-only meaning |
| Warning | Amber label and short reason, next to the affected choice |
| Error | Soft red label, short explanation and recovery action; never a red full-screen traceback |
| Secondary information | Readable muted blue-grey; important input labels never look disabled |

Use one prominent primary action per decision screen, stable Back placement and a small context footer. The Welcome screen still has only the Enter instruction. Keep headings short, sentence-case controls, aligned label/input columns and consistent spacing; terminal font is user-controlled, so use hierarchy through weight, spacing and grouping. No gradients, gratuitous emoji, flashing text, typewriter introductions, full-screen transitions or artificial waiting. Activity is the only animated state; a static busy indicator remains understandable when animations are disabled.

Keep the user's language practical: "Choose what to predict", "Choose the information to use", "Ready to train". Technical terms and full explanations belong in contextual help, while safety-critical warnings stay visible. Do not hide required decisions in help. Keep the four Goal labels exactly as specified, with descriptions hidden until help is requested. State labels such as Number and Category remain consistent across preview, selection and Try.

At each step, the user can tell where they are, what needs a decision and what happens next. Use a small named stage indicator (Dataset / Goal / Training / Results / Export) after Welcome; it is orientation, not a second clickable route that bypasses guards. Within screens show only relevant detail, not a long progress questionnaire. Good defaults are visibly selected, never silently committed. Errors retain inputs and point to a correction. Example datasets are easy to reach directly from Load; no tutorial wizard or signup.

### Required screen review checklist
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

## Screen contract
| State | Content and primary action | Exit/guards |
|---|---|---|
| Welcome | MLForge; tagline; privacy line; "Press Enter to begin" | Enter → Load, Q quit; no Start New Project button |
| Load Dataset | Three choices: Browse local files, Enter a path, Example dataset | All paths remain in terminal; Enter confirms local selection |
| Parse | Filename (literal/escaped), operation, elapsed, Cancel | Completion → Preview; error → recoverable load error; cancel → Load with path preserved |
| Preview | Counts; column/type/missing/sample summary; first-50-row table | "Looks correct" confirms; Change type; Preview is not correct → Prepare; choose another → Load |
| Goal | Four clean labels from PRODUCT_SPEC | No descriptions by default; ? on focus explains examples/eligibility; select supported goal |
| Target | Suggested columns, Show all columns | No autochoice; help gives type, unique/missing/sample, suitability; invalid rows explain |
| Features | Checkbox list with default/reason and selection count | Target not selectable; ? explains exclusions/leakage; explicit warning acknowledgement where required |
| Preprocessing summary | Rows/split or exploration; missing/encoding/scaling summary; warnings | Details under ?; Back to features; Continue; no manual preprocessing editor |
| Models | Applicable list; both supervised choices selected | Space toggle; >=1 needed; ? explains bias/tradeoff; K-Means k/PCA dimensions simple bounded input |
| Training | Current operation/model; completed/failed/pending states; elapsed | Cancel; live footer; configuration locked |
| Results | At most two primary metrics + model name/status; concise provenance | Failed rows show safe reason; select successful candidate; ? on metric; no false recommendation |
| Selected model | Model name, task, training/evaluation scope | Try the model / Inspect details / Export package; Back to results |
| Try | Scrollable typed feature form, Missing toggles | Predict → task output; correct field errors in place; return without retraining |
| Export | Destination, module name, version; concise privacy/compatibility note | Build wheel → success path + pip/import usage; retry on failure keeps selected model |

No Target screen for clustering/PCA. Their results use task diagnostics, not a fabricated multi-model comparison. Inspection is entirely terminal: confusion matrix/per-class list for classification; residual summary for regression; cluster sizes/centers and silhouette note; PCA per-component variance/reconstruction summary. Feature importance and browser graphs are absent.

## Loading details
File picker is a lazy directory list/tree with current path, parent navigation, file filter and keyboard select. Start at current working directory; show hidden files only by explicit toggle. Permission-denied directories are recoverable and don't crash the app. Do not recursively scan user's home at startup. Manual path accepts relative paths against cwd and ~/ expansion; no shell/env-variable evaluation or glob execution. Entering a URL explains "Choose a local file." Spaces/non-ASCII paths work.

Examples show task and synthetic-data label after focus/help, load from package resources and enter the same parsing/verification flow as a file. No privileged demo shortcut around validation.

## Preview and errors
Column selector and table focus are separate but predictable. Type menu shows current detected/effective values; invalid override keeps old schema and shows counts/locations, not raw private values in logs. Truncated values have a clear ellipsis and help view. Control sequences/markup are always literal, including filenames/model/package names.

"Preview is not correct" opens Prepare with AI even after a valid parse. It does not assert that inferred types are certainly right. Prepare shows the full prompt, local-only notice, Copy/Save actions and Back/Choose another dataset. Clipboard action is user-triggered, no automatic OSC52 or remote integration. Saved prompts contain only the safe content in DATASET_SPEC.

Every empty/error state has a next action: missing path → edit path; unreadable → choose file; no usable features → return to types/features; impossible split → choose another target/dataset; all models failed → inspect errors or Back; export permission/disk/full/collision → change destination/retry. No disabled primary action without a visible reason.

## Training, navigation and quit
Display "Preparing data", "Training Logistic Regression", "Evaluating", "Validating artifact" as actual child phases. Candidate completion counts are factual; never show guessed fit percent/ETA. Spinner remains active while child is alive; completed count and elapsed update without freezing input.

Cancel is immediate request, then "Stopping training…" until actual reaping. Retain valid earlier results labeled "Cancelled — N models completed." No candidate interrupted mid-fit is exportable. Back while busy offers Cancel and go back / Keep running. Q/Ctrl+Q during active work offers Cancel and quit / Keep running, default Keep running. Quit with an unexported successful result warns once that the session is not saved. No confirmation for ordinary form transitions.

Starting a new dataset or changing a completed experiment confirms discard once; closing help never asks. After a failed operation, preserve user choices. After export success show full selectable artifact path, install command and task-correct Python example; "Back to results" and "Quit" are sufficient. No publish/share button.

## Visual verification deliverables
Use Pilot navigation assertions plus human-readable SVG captures from synthetic fixtures at 100x30 and 80x24: welcome, picker, preview override, help, training, partial failure, results, try validation, export success/error. Record checks in V1_BUILD_REPORT; generated captures alone do not prove focus/cancellation. A real PTY smoke verifies alternate-screen restoration after normal quit, Ctrl+C and handled failure. No physical mouse required.
