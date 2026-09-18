# Repository audit

## Evidence and freshness

On 2026-09-18 GitHub branch listings and local clean checkouts agreed:
- `noaml21/ml-from-scratch`, default/only remote branch `main`: [93272b473b6079960e903b45bd3a625c0d19be59](https://github.com/noaml21/ml-from-scratch/tree/93272b473b6079960e903b45bd3a625c0d19be59).
- Reference `noaml21/linux-concurrency-ipc`, `v3/reliable-ipc-lab`: [4711931ec1eca8238cc3aa2e4838263182f08fec](https://github.com/noaml21/linux-concurrency-ipc/tree/4711931ec1eca8238cc3aa2e4838263182f08fec).

Read all three algorithm modules, all three test modules, all six demos/comparisons, requirements, ignore file and README. There is no pyproject/setup, installed command, CI workflow, importer, license file, package namespace initializer, orchestration or TUI in the ML baseline. Original files are small and understandable; a wholesale rewrite is unjustified.

## Implementation findings

| Area | Actual implementation | Product consequence |
|---|---|---|
| K-Means | Random sample initialization; one run; Euclidean distance broadcast; retains labels/centroids every iteration; empty cluster keeps previous centroid | Useful teaching tool; O(n*k*d) distance temporary and retained histories are unsuitable default workbench behavior |
| Logistic regression | Binary 0/1 only; nested Python per-sample SGD; clipped sigmoid; unregularized; default 10,000 epochs; loss history | Good educational identity, insufficient multiclass/default runtime characteristics |
| PCA | Covariance eigendecomposition; components are columns; centers but does not scale; accepts components up to feature count | Preserve semantics; workbench uses a separately validated estimator and scaling policy |
| Validation | Finite 2-D numeric X checks, shapes, prefit errors in code; limited constructor checks | Additional edge cases exist: bool-as-int parameters, nonfinite learning rate, degenerate PCA, failed refit state |
| Tests | 15 pytest functions: toy learning, deterministic seeds, simple reconstruction/history, prefit errors | Existing coverage is useful but not broad importer/security/product coverage; invalid data and constructor behavior are largely untested |
| Demos | Six runnable scripts; inject root into sys.path; matplotlib demos write assets then show a GUI; comparisons print results | Keep these educational workflows; their GUI behavior is not the MLForge TUI product flow |
| Dependencies | `numpy>=2.5`, `matplotlib>=3.11`, `scikit-learn>=1.9`, `pytest>=9.1`; unbounded upper versions | Resolve real available compatible releases; separate runtime/dev/demo dependencies and freeze tested constraints |
| Packaging | Tests import `src.kmeans` etc. as a namespace; no distribution | Add `src/mlforge` and explicit package discovery without breaking source-checkout imports |
| README | Accurately calls algorithms educational and sklearn a reference tool | Preserve that explanation in an educational section, distinguish new workbench sklearn runtime use |
| CI / license | Neither present in tracked tree | Add CI; do not invent a license grant or publish to PyPI |

Planning baseline test attempts with system Python and the bundled workspace Python both failed before collection because pytest is absent. This is environment evidence, not a failing algorithm test. A repository-local venv was then created using unchanged requirements.txt: all 15 tests passed on Python 3.12.3; pip check passed; all three comparison scripts completed. K-Means cost matched at 47.699582; logistic test accuracy matched at 0.9200; PCA reconstruction MSE matched at 0.00407484 (component signs differ legitimately). This verifies the educational baseline, not V1 packaging or a Python 3.13 installation.

## Reference lessons, grounded in code

Read `ipc_lab/models.py`, `runner.py`, `experiment.py`, `presentation.py`, `app.py`, `lab.tcss`, UI/execution tests and V3 design documentation:
- Validated dataclasses and headless runner are independent of Textual; copy the boundary concept.
- App uses async workers, elapsed state, serial execution and cancellation events. Quit waits for engine cleanup.
- Runner tracks the actual child, deadlines and completed attempts. MLForge needs a Python process owner because a CPU fit cannot be cancelled reliably merely by cancelling an async task/thread.
- Literal Text rendering and explicit failed/pending states are valuable for untrusted dataset content.
- Pilot tests cover real engine flow, invalid input, cancellation, quit, persistence failure and keyboard use at 60x20.
- TCSS gives consistent surfaces, focus and restrained accents. Its fixed horizontal forms and single large App are not MLForge's target architecture; use separate screens and responsive content.
- Documentation separates timing meaning, ownership, limitations and measured evidence. Adopt this honesty for ML metrics, fit state and cancellation.

No claim is made that the IPC UI was manually reviewed live in this planning task. No IPC code or branches are modified. No dependency or code copied from it.

## Decisions resulting from audit

Preserve the three original modules, tests and demos as the learning track. V1 workbench uses six sklearn estimators through a concrete registry; a second backend abstraction would add unvalidated behavior, serialization and fit-state complexity. Future scratch adapters require independent conformance tests and are deferred, not silently swapped in.

Build a new cohesive package alongside the educational source. Test packaging and export very early because those are absent and central, before investing in screen polish.

Research-only feasibility probe: sklearn 1.9.1 + skops 0.15.0 round-tripped all six planned pipeline shapes. Additional trusted types observed were numpy.dtype and sklearn.tree._tree.Tree for forests. Local source review of skops DTypeNode, ArrayNode, ReduceNode and TreeNode confirmed that Tree is deliberately not default-trusted because malformed indices can crash native inference. EXPORT_SPEC therefore requires per-model fixed trust and forest structure validation. This probe is not a clean-wheel install or hostile-artifact security proof.

## Primary technical references

Consulted during planning (2026-09-18); pin actual implementation dependencies, not these floating documentation versions:
- [sklearn persistence](https://scikit-learn.org/stable/model_persistence.html): environment compatibility and serialization tradeoffs.
- [skops persistence](https://skops.readthedocs.io/en/stable/persistence.html): trusted-type inspection; no automatic trust of discovered types.
- [sklearn common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html): split before learned transforms.
- [OneHotEncoder](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.OneHotEncoder.html): bounded category grouping and unseen values.
- [Textual workers](https://textual.textualize.io/guide/workers/) and [testing](https://textual.textualize.io/guide/testing/): UI workers and Pilot.
- [Wheel format](https://packaging.python.org/en/latest/specifications/binary-distribution-format/): metadata/RECORD and platform tagging.
- [Python subprocess](https://docs.python.org/3/library/subprocess.html): child ownership and process APIs.

These links support library facts; product limits and choices in the specifications are MLForge design decisions.
