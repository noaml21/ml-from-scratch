# UX flow and interaction specification

## Shell and visual system
Full-screen Textual app, one primary task per screen. Persistent compact brand/step header, scrollable body, visible status and context footer. Primary surface #101820, elevated #182630, text #E6EEF3, muted #AEC0CC, accent #66D9C3, warning #F3C477, error #FF8A91; tune for real terminal legibility without relying on color alone. Use restrained bold labels, 1-row vertical gaps and 2-column horizontal padding. No ASCII logo wall, dense dashboard or animation beyond activity feedback.

At >=100 columns split preview/help where useful; 80..99 stack panels and scroll. Primary buttons/labels remain reachable at 80x24; tables scroll horizontally and expose selected-cell details. Below 80x24 show dimensions and "Resize to at least 80 × 24"; keep Cancel/Ctrl+Q functioning and restore prior focus/state on resize. Resize never reloads data or retrains.

Tab/Shift+Tab move among controls. Up/Down navigate focused lists; Left/Right scroll tables where appropriate. Enter activates focused action/selects. Space toggles selections. ? opens help for the focused item, Esc closes help restoring exact focus. B/Esc go back when not editing/modal. Q quits outside text inputs; Ctrl+Q works everywhere through quit confirmation/cleanup. In editable text, q/b/? and Space are normal characters; F1 provides help and Esc exits field/modal before back. Never intercept these letters as global priority bindings. Footer shows only active keys, with F1 in text fields. Mouse is optional.

Help is a compact scrollable modal at small sizes, optional side panel at wide sizes, backed by one help catalog. It must not move the selected list item, advance a workflow or clear inputs. Focus order follows reading order; screen entry focuses its primary list/input, errors focus the invalid field, async completion never unexpectedly steals focus.

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
