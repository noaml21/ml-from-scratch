"""Build and test isolated app installations; preparation alone may use network."""

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".mlforge-build"


def run(command, *, cwd, env=None):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {command}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result.stdout.strip()


def verify(wheelhouse):
    if not wheelhouse.is_dir() or not any(wheelhouse.glob("*.whl")):
        raise SystemExit(
            "Missing wheelhouse. Run: python scripts/verify_package.py "
            "--prepare-wheelhouse"
        )
    env = dict(os.environ, PIP_NO_INDEX="1", PIP_FIND_LINKS=str(wheelhouse))
    env.pop("PYTHONPATH", None)
    WORK.mkdir(exist_ok=True)
    evidence = {"python": sys.version, "installations": []}
    with tempfile.TemporaryDirectory(prefix="package-", dir=WORK) as temporary:
        root = Path(temporary)
        dist = root / "dist"
        run(
            [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(dist)],
            cwd=ROOT,
            env=env,
        )
        wheel = next(dist.glob("*.whl"))
        sdist = next(dist.glob("*.tar.gz"))
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            assert "mlforge/__main__.py" in names
            assert all(
                name.startswith("mlforge/")
                or name.startswith("mlforge-0.1.0.dist-info/")
                for name in names
            ), names
        with tarfile.open(sdist) as archive:
            archive.extractall(root / "source", filter="data")
        source = next((root / "source").iterdir())
        for kind in ("wheel", "sdist"):
            venv = root / kind
            run([sys.executable, "-m", "venv", str(venv)], cwd=root)
            python = str(venv / "bin/python")
            run(
                [
                    python,
                    "-m",
                    "pip",
                    "install",
                    "--no-index",
                    "--find-links",
                    str(wheelhouse),
                    "-r",
                    str(ROOT / "requirements/constraints-runtime.txt"),
                ],
                cwd=root,
                env=env,
            )
            artifact = wheel
            if kind == "sdist":
                output = root / "rebuilt"
                run(
                    [
                        python,
                        "-m",
                        "build",
                        "--wheel",
                        "--no-isolation",
                        "--outdir",
                        str(output),
                    ],
                    cwd=source,
                    env=env,
                )
                artifact = next(output.glob("*.whl"))
            run(
                [
                    python,
                    "-m",
                    "pip",
                    "install",
                    "--no-index",
                    "--no-deps",
                    str(artifact),
                ],
                cwd=root,
                env=env,
            )
            assert (
                run([python, "-m", "mlforge", "--version"], cwd=root, env=env)
                == "0.1.0"
            )
            assert "Your data stays" in run(
                [str(venv / "bin/mlforge"), "--help"], cwd=root, env=env
            )
            location = run(
                [python, "-I", "-c", "import mlforge; print(mlforge.__file__)"],
                cwd=root,
                env=env,
            )
            assert str(venv) in location, location
            evidence["installations"].append(
                {
                    "kind": kind,
                    "status": "passed",
                    "pip_check": run([python, "-m", "pip", "check"], cwd=root, env=env),
                    "versions": run(
                        [python, "-m", "pip", "list", "--format=json"],
                        cwd=root,
                        env=env,
                    ),
                }
            )
    report = WORK / f"package-{sys.version_info.major}.{sys.version_info.minor}.json"
    report.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"Wheel and sdist-derived isolated installs passed: {report}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-wheelhouse", action="store_true")
    args = parser.parse_args()
    wheelhouse = WORK / "wheelhouse"
    if args.prepare_wheelhouse:
        wheelhouse.mkdir(parents=True, exist_ok=True)
        print(
            run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "download",
                    "--only-binary=:all:",
                    "--dest",
                    str(wheelhouse),
                    "-r",
                    str(ROOT / "requirements/constraints-runtime.txt"),
                ],
                cwd=ROOT,
            )
        )
    else:
        verify(wheelhouse)


if __name__ == "__main__":
    main()
