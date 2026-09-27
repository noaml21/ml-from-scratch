"""The installed bootstrap must remain usable without presentation imports."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize("argument", ["--help", "--version"])
def test_noninteractive_bootstrap_without_ui(argument):
    code = """
import importlib.abc
import sys
class BlockUI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'textual', 'rich'}:
            raise AssertionError('Bootstrap imported presentation')
sys.meta_path.insert(0, BlockUI())
from mlforge.__main__ import main
main([sys.argv[1]])
"""
    result = subprocess.run(
        [sys.executable, "-c", code, argument], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert ("0.1.0" if argument == "--version" else "Your data stays") in result.stdout


def test_unknown_argument_is_an_error():
    result = subprocess.run(
        [sys.executable, "-m", "mlforge", "--unknown"], capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
