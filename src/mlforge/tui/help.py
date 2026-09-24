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
