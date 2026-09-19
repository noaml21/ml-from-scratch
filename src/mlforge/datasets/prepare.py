"""Local structural preparation instructions; never invoke AI or include data."""

import os
import tempfile
from pathlib import Path

from mlforge.contracts import DomainError

SAFE_CODES = frozenset(
    {
        "DATA_LIMIT",
        "ENCODING",
        "CSV_QUOTES",
        "HEADERS",
        "ROW_WIDTH",
        "JSON_KEYS",
        "JSON_STRUCTURE",
        "LOCAL_FILE",
        "FORMAT",
        "FILE_CHANGED",
        "FILE_READ",
        "NO_DATA",
        "PREVIEW",
    }
)


def preparation_prompt(
    source_format: str | None = None, diagnostic: str = "PREVIEW"
) -> str:
    format_name = (
        source_format
        if source_format in {"CSV", "TSV", "JSONL"}
        else "unsupported or unknown"
    )
    issue = diagnostic if diagnostic in SAFE_CODES else "unspecified structure"
    return (
        "You are helping me convert a local dataset to a clean tabular file. I will "
        "separately decide what source material to share. The source format is "
        f"{format_name}; the structural issue is {issue}.\n"
        "Preserve all original information and semantic meaning. Do not invent, "
        "infer, fill, delete, merge or deduplicate rows or values. Do not choose a "
        "target. Do not perform machine-learning preprocessing, normalization, "
        "scaling, category encoding, feature engineering or analysis.\n"
        "Only repair/convert the structure. Prefer UTF-8 CSV with one nonempty "
        "unique header per column, comma separators, consistent field counts, "
        "correctly escaped quotes and no index column. TSV or flat JSONL are "
        "acceptable under the same scalar-table rules. Preserve leading zeros as "
        "text. Use empty fields only for values already missing. Preserve ambiguous "
        "literals as text. Do not silently discard nested or unrepresentable "
        "information: explain the obstacle and ask me for a mapping decision before "
        "conversion.\n"
        "Return the converted file and a concise list of structural changes. Verify "
        "row counts, column meanings and representative original values against the "
        "source. Do not claim to have inspected data I have not supplied. MLForge "
        "supports at most 20 MiB, 20,000 rows, 100 columns, 128-character headers "
        "and 4,096-character cells; if exceeded, explain the limit without silently "
        "dropping data.\n"
        "\n"
        "Privacy: MLForge has included no source values, column names, filenames or "
        "paths. If I choose to copy private data into an external service, that "
        "service receives it. This prompt was generated locally; MLForge has "
        "contacted no service.\n"
    )


def save_prompt(destination: str | Path, prompt: str) -> Path:
    path = Path(destination).expanduser()
    if path.suffix.lower() != ".txt":
        raise DomainError(
            "PROMPT_NAME", "Use a .txt filename.", "Choose a prompt destination."
        )
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".mlforge-prompt-",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(prompt)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    except FileExistsError:
        raise DomainError(
            "PROMPT_EXISTS", "That file already exists.", "Choose a different filename."
        ) from None
    except (OSError, ValueError):
        raise DomainError(
            "PROMPT_SAVE",
            "Could not save the prompt.",
            "Choose a writable location with free space.",
        ) from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path
