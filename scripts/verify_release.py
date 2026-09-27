"""Deterministic V1 release verifier; composes existing gates, not a product CLI.

python scripts/verify_release.py --prepare-wheelhouse  # may download declared wheels
python scripts/verify_release.py                       # offline, index disabled

Verification runs the application wheel and sdist-derived installations (help,
version, installed Pilot/PTY dataset and four-task Try/Export journeys, and
exported-wheel consumer parity) and then the six model consumer installations.
Every command and exit status is recorded in .mlforge-build/release-<python>.json.
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".mlforge-build"
WHEELHOUSE = WORK / "wheelhouse"
MINOR = f"{sys.version_info.major}.{sys.version_info.minor}"
MODELS = (
    "classification.logistic",
    "classification.forest",
    "regression.linear",
    "regression.forest",
    "clustering.kmeans",
    "reduction.pca",
)


def step(report, name, command, env):
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    report["steps"].append(
        {
            "name": name,
            "command": command,
            "exit": result.returncode,
            "seconds": round(time.monotonic() - started, 1),
            "tail": (result.stdout + result.stderr).strip().splitlines()[-3:],
        }
    )
    if result.returncode:
        write(report, "failed")
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit(f"Release step failed: {name} (exit {result.returncode})")
    return result.stdout


def write(report, status):
    report["status"] = status
    path = WORK / f"release-{MINOR}.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    return path


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prepare-wheelhouse", action="store_true")
    args = parser.parse_args()
    package = [sys.executable, str(ROOT / "scripts/verify_package.py")]
    if args.prepare_wheelhouse:
        subprocess.run([*package, "--prepare-wheelhouse"], cwd=ROOT, check=True)
        return
    if not WHEELHOUSE.is_dir() or not any(WHEELHOUSE.glob("*.whl")):
        raise SystemExit(
            "Missing prepared wheelhouse. Run once with network access:\n"
            "  python scripts/verify_release.py --prepare-wheelhouse"
        )
    env = dict(
        os.environ,
        PIP_NO_INDEX="1",
        PIP_FIND_LINKS=str(WHEELHOUSE),
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
    )
    report = {
        "commit": git("rev-parse", "HEAD"),
        "worktree_clean": not git("status", "--porcelain", "--untracked-files=no"),
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "steps": [],
    }
    step(report, "application installs and installed journeys", package, env)
    for model in MODELS:
        (WORK / f"consumer-{sys.version_info.minor}-{model}.json").unlink(
            missing_ok=True
        )
    step(
        report,
        "six model consumer installations",
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-m",
            "install",
            "tests/mlforge/export/test_install.py",
        ],
        env,
    )
    consumers = {}
    for model in MODELS:
        path = WORK / f"consumer-{sys.version_info.minor}-{model}.json"
        evidence = json.loads(path.read_text())
        assert evidence["parity"] == "passed" and evidence["outside_checkout"], model
        consumers[model] = {
            "wheel": evidence["wheel"],
            "pip_check": evidence["pip_check"],
            "network_guard": evidence["network_guard"],
        }
    package_report = json.loads((WORK / f"package-{MINOR}.json").read_text())
    report["application_installations"] = [
        {
            "kind": item["kind"],
            "status": item["status"],
            "tui_export_consumers": [
                c["task"] for c in item["exported_consumers"] if c["try_parity"]
            ],
        }
        for item in package_report["installations"]
    ]
    report["model_consumers"] = consumers
    print(f"Release verification passed: {write(report, 'passed')}")


if __name__ == "__main__":
    main()
