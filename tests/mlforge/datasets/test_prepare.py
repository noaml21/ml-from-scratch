"""Preparation is local, structural, privacy-preserving and never overwrites."""

import os

import pytest

from mlforge.contracts import DomainError
from mlforge.datasets.prepare import preparation_prompt, save_prompt


def test_prompt_semantic_contract_and_diagnostic_privacy():
    prompt = preparation_prompt("CSV", "ROW_WIDTH")
    for phrase in (
        "Preserve all original information and semantic meaning",
        "Do not invent, infer, fill, delete, merge or deduplicate",
        "Do not choose a target",
        "Do not perform machine-learning preprocessing",
        "normalization, scaling, category encoding, feature engineering or analysis",
        "Only repair/convert the structure",
        "Preserve leading zeros as text",
        "Use empty fields only for values already missing",
        "Preserve ambiguous literals as text",
        "Do not silently discard nested or unrepresentable information",
        "ask me for a mapping decision",
        "Verify row counts, column meanings",
        "Do not claim to have inspected data I have not supplied",
        "20 MiB, 20,000 rows, 100 columns, 128-character headers",
        "4,096-character cells",
        "without silently dropping data",
    ):
        assert phrase in prompt
    assert "CSV" in prompt and "ROW_WIDTH" in prompt
    hostile = preparation_prompt("/private/secret.csv", "private customer 123")
    assert (
        "secret" not in hostile and "customer" not in hostile and "123" not in hostile
    )
    assert "no source values, column names, filenames or paths" in hostile


def test_save_exclusive_private_and_failure(tmp_path, monkeypatch):
    destination = tmp_path / "prompt.txt"
    prompt = preparation_prompt()
    assert save_prompt(destination, prompt) == destination
    assert destination.read_text() == prompt
    assert destination.stat().st_mode & 0o777 == 0o600
    with pytest.raises(DomainError) as caught:
        save_prompt(destination, "overwritten")
    assert caught.value.code == "PROMPT_EXISTS" and destination.read_text() == prompt
    with pytest.raises(DomainError):
        save_prompt(tmp_path / "bad.csv", prompt)
    with pytest.raises(DomainError):
        save_prompt(tmp_path / "missing" / "prompt.txt", prompt)

    def fail(fd):
        raise OSError("disk full private details")

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(DomainError) as caught:
        save_prompt(tmp_path / "failed.txt", prompt)
    assert caught.value.code == "PROMPT_SAVE"
    assert not (tmp_path / "failed.txt").exists()
    assert not list(tmp_path.glob(".mlforge-prompt-*"))


def test_invalid_descriptions_and_permission_failure_are_safe(tmp_path, monkeypatch):
    from mlforge.datasets import prepare

    assert "unsupported or unknown" in preparation_prompt({}, [])

    def denied(*args, **kwargs):
        raise PermissionError("private directory details")

    monkeypatch.setattr(prepare.tempfile, "NamedTemporaryFile", denied)
    with pytest.raises(DomainError) as error:
        save_prompt(tmp_path / "prompt.txt", preparation_prompt())
    assert error.value.code == "PROMPT_SAVE"
    assert "private directory" not in str(error.value)
    assert not list(tmp_path.iterdir())
