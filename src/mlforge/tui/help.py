"""One presentation-only help catalog for contextual keyboard help."""

CATALOG = {
    "welcome": (
        "Welcome to MLForge",
        "Load a local table, review its types, and choose what to learn. "
        "Your data stays on your machine. Local temporary files are removed "
        "when the session closes normally.\n\n"
        "Tab and Shift+Tab move focus. Enter activates a choice. "
        "? opens help; use F1 inside a text field. Esc closes help and restores "
        "focus. Ctrl+Q is always available to quit safely.",
    ),
    "load": (
        "Load a local dataset",
        "Browse local folders, enter a path, or select a synthetic example. "
        "The picker starts in the working directory; hidden files require its "
        "explicit toggle. Parent folder moves up one level. "
        "Use a UTF-8 CSV, TSV, or flat JSONL file. Paths may contain spaces "
        "or Unicode. Relative paths start at the current working directory; "
        "~/ expands to your home directory. Shell commands and environment "
        "variables are never evaluated.\n\n"
        "Limits: 20 MiB, 20,000 rows, 100 columns. The source file is read only. "
        "You will review the complete table's inferred schema before continuing.",
    ),
    "path": (
        "Local file path",
        "Enter a local CSV, TSV, or JSONL path, then press Enter. "
        "q, b, ?, and spaces are ordinary text here. F1 opens this help. "
        "Esc leaves the field; a second Esc goes back. URLs are not supported.",
    ),
    "preview": (
        "Review your dataset",
        "The source values are preserved. Type inference examines the full "
        "bounded table, not just a sample. Blank fields are missing; literals "
        "such as NA remain values. Review types before confirming the dataset. "
        "Help and Back never change committed data.",
    ),
    "prepare": (
        "Local preparation guidance",
        "The read-only prompt contains only safe format/error categories, never "
        "your data or column names. Copy sends a request to your terminal clipboard "
        "only when you activate it; terminal settings may refuse it. Select text or "
        "Save to a new .txt file if Copy is unavailable. Saving is atomic and never "
        "overwrites an existing file; Back and quit wait for publication to finish. "
        "MLForge does not open a browser or contact an AI service.",
    ),
    "types": (
        "Column types",
        "Every present value is checked before a type change is accepted. "
        "Number, Boolean and Date must parse every value. Category and Identifier "
        "keep original text. Unknown is diagnostic and cannot be selected. "
        "Reset restores the detected type. Accepted changes invalidate prior "
        "confirmation and dependent experiment choices; "
        "failed changes keep the old schema.",
    ),
    "busy": (
        "Local work in progress",
        "The operation runs in an owned child process. The elapsed timer "
        "does not predict completion. Cancel requests a stop immediately; "
        "Stopping remains visible until the child and its resources are cleaned up. "
        "Help stays available while work continues.",
    ),
}

CATALOG.update(
    {
        "goal": (
            "Choose a goal",
            "Choose one of the four tasks. Help on a goal explains its data "
            "requirements.",
        ),
        "classification": (
            "Predict an outcome",
            "Learn discrete outcomes, such as a product category. The target "
            "needs 2–20 classes and at least five rows per class; no missing "
            "targets.",
        ),
        "regression": (
            "Predict a number",
            "Learn a numeric outcome, such as a price. Choose a finite Number "
            "target with at least two distinct values and no missing targets.",
        ),
        "clustering": (
            "Find groups",
            "Explore groups of similar rows with K-Means. There is no target or "
            "holdout test; results describe this dataset.",
        ),
        "reduction": (
            "Reduce complexity",
            "Summarize at least two varying Number inputs using PCA. There is no "
            "target or holdout test. Dimensions are bounded by the selected "
            "features and rows.",
        ),
        "target": (
            "Choose what to predict",
            "No target is chosen automatically. Suggested columns pass "
            "eligibility checks; Show all columns exposes other columns and "
            "reasons. Review types in Preview to change interpretation.",
        ),
        "features": (
            "Choose the information to use",
            "Defaults select usable inputs. The target, constants, identifiers "
            "and dates cannot be inputs. Space toggles the focused row. Warnings "
            "identify possible leakage or high cardinality; explicitly keep them "
            "or change the selection.",
        ),
        "preprocessing": (
            "Automatic preprocessing",
            "Supervised data is split before any fitting. Each candidate fits its "
            "own imputation, encoding and scaling on training rows only. Unseen "
            "categories use the fitted encoder's unknown-category behavior. "
            "Models are never silently refitted for prediction or export.",
        ),
    }
)
