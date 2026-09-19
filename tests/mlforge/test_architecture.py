"""Small AST regression guard for ARCHITECTURE.md; not a security sandbox."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "src/mlforge"

# Longest matching owner wins. Within a package the cycle guard still applies.
ALLOWED = {
    "": (),
    "datasets.records": (),
    "contracts": ("datasets.records",),
    "datasets": ("contracts", "datasets"),
    "tasks": ("contracts", "datasets.records"),
    "models": ("contracts",),
    "prediction.runtime": (),
    "prediction.schema": ("contracts", "datasets.records", "prediction.runtime"),
    "prediction": (),
    "preprocessing": ("contracts", "datasets.records", "tasks", "prediction.runtime"),
    "evaluation": ("contracts",),
    "training": (
        "contracts",
        "datasets.records",
        "tasks",
        "preprocessing",
        "models",
        "evaluation",
        "prediction",
    ),
    "export": ("contracts", "prediction"),
    "execution.protocol": ("contracts",),
    "execution.coordinator": ("contracts", "execution.protocol"),
    "execution.worker": (
        "contracts",
        "execution.protocol",
        "datasets",
        "tasks",
        "preprocessing",
        "models",
        "training",
        "evaluation",
        "prediction",
        "export",
    ),
    "execution": (),
    "application": (
        "contracts",
        "datasets.records",
        "datasets.importers",
        "tasks",
        "models",
        "evaluation",
        "execution.coordinator",
        "execution.protocol",
    ),
    "tui": ("application", "contracts", "datasets.records"),
    "__main__": ("application", "tui"),
}


def matches(module, prefix):
    return module == prefix or module.startswith(prefix + ".")


def owner(module):
    return max(
        (key for key in ALLOWED if key and matches(module, key)),
        key=len,
        default="",
    )


def check_sources(sources):
    """Return errors for a mapping of relative .py paths to source text."""
    modules = {}
    for path, source in sources.items():
        parts = path.removesuffix(".py").split("/")
        initializer = parts[-1] == "__init__"
        if initializer:
            parts.pop()
        modules[".".join(["mlforge", *parts])] = (path, source, initializer)
    errors = []
    edges = {module: set() for module in modules}
    for module, (path, source, initializer) in modules.items():
        tree = ast.parse(source, filename=path)
        local = module.removeprefix("mlforge").lstrip(".")
        source_owner = owner(local)
        for node in ast.walk(tree):
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.module in {"importlib", "builtins"} and any(
                    alias.name in {"import_module", "__import__"}
                    for alias in node.names
                ):
                    errors.append(f"{path}:{node.lineno}: dynamic import alias")
                if any(alias.name == "*" for alias in node.names):
                    errors.append(f"{path}:{node.lineno}: star import")
                base = node.module or ""
                if node.level:
                    package = module if initializer else module.rpartition(".")[0]
                    pieces = package.split(".")
                    if node.level > len(pieces):
                        errors.append(f"{path}:{node.lineno}: invalid relative import")
                        continue
                    base = ".".join(pieces[: len(pieces) - node.level + 1])
                    if node.module:
                        base += "." + node.module
                imports = [
                    base + "." + alias.name
                    if base + "." + alias.name in modules
                    else base
                    for alias in node.names
                ]
            elif isinstance(node, ast.Call):
                called = node.func
                if (
                    isinstance(called, ast.Name)
                    and called.id in {"__import__", "import_module"}
                ) or (
                    isinstance(called, ast.Attribute) and called.attr == "import_module"
                ):
                    errors.append(f"{path}:{node.lineno}: dynamic import")
            for target in imports:
                if (
                    target.split(".")[0] in {"textual", "rich"}
                    and source_owner != "tui"
                ):
                    errors.append(f"{path}:{node.lineno}: presentation import {target}")
                if not matches(target, "mlforge"):
                    continue
                target_local = target.removeprefix("mlforge").lstrip(".")
                target_owner = owner(target_local)
                same_package = source_owner == target_owner and source_owner in {
                    "datasets",
                    "application",
                    "tui",
                    "export",
                }
                if not same_package and not any(
                    matches(target_local, allowed) for allowed in ALLOWED[source_owner]
                ):
                    errors.append(
                        f"{path}:{node.lineno}: forbidden {module} -> {target}"
                    )
                candidates = [name for name in modules if matches(target, name)]
                if candidates:
                    edges[module].add(max(candidates, key=len))
    visiting, visited = set(), set()

    def visit(module):
        if module in visiting:
            errors.append(f"import cycle through {module}")
            return
        if module in visited:
            return
        visiting.add(module)
        for target in edges[module]:
            visit(target)
        visiting.remove(module)
        visited.add(module)

    for module in edges:
        visit(module)
    return errors


def test_production_architecture():
    sources = {
        str(path.relative_to(ROOT)): path.read_text() for path in ROOT.rglob("*.py")
    }
    assert sources, "No production modules inspected"
    assert check_sources(sources) == []


@pytest.mark.parametrize(
    "sources",
    [
        {
            "contracts.py": "from mlforge.datasets.records import Cell",
            "datasets/records.py": "",
        },
        {"datasets/inference.py": "from . import records", "datasets/records.py": ""},
        {
            "tui/app.py": (
                "from textual.app import App\nfrom mlforge.contracts import TaskKind"
            )
        },
    ],
)
def test_allowed_fixtures(sources):
    assert check_sources(sources) == []


@pytest.mark.parametrize(
    "sources, reason",
    [
        ({"contracts.py": "import mlforge.application.state"}, "forbidden"),
        ({"contracts.py": "from .application import state"}, "forbidden"),
        ({"models.py": "def factory():\n import mlforge.tui.app"}, "forbidden"),
        (
            {
                "models.py": (
                    "from typing import TYPE_CHECKING\n"
                    "if TYPE_CHECKING:\n import mlforge.application"
                )
            },
            "forbidden",
        ),
        ({"datasets/__init__.py": "from ..tui import app"}, "forbidden"),
        (
            {"datasets/a.py": "from . import b", "datasets/b.py": "from . import a"},
            "cycle",
        ),
        ({"prediction/runtime.py": "from ..contracts import TaskKind"}, "forbidden"),
        ({"tui/app.py": "from ..execution.worker import main"}, "forbidden"),
        ({"models.py": "from rich import print"}, "presentation"),
        ({"models.py": "from mlforge.contracts import *"}, "star import"),
        ({"models.py": "__import__('mlforge.tui')"}, "dynamic import"),
        (
            {
                "models.py": (
                    "from importlib import import_module as load\nload('mlforge.tui')"
                )
            },
            "dynamic import",
        ),
    ],
)
def test_rejected_fixtures(sources, reason):
    assert any(reason in error for error in check_sources(sources))


def test_fresh_headless_imports():
    modules = []
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if relative.parts[0] == "tui" or path.name == "__main__.py":
            continue
        parts = list(relative.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        modules.append(".".join(["mlforge", *parts]))
    code = """
import importlib
import importlib.abc
import sys
class BlockUI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'textual', 'rich'}:
            raise AssertionError('Headless import loaded presentation: ' + fullname)
sys.meta_path.insert(0, BlockUI())
for name in sys.argv[1:]:
    importlib.import_module(name)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, *modules],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
