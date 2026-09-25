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
NETWORK_GUARD = """
import os
import sys
from pathlib import Path
ACTIVE = True
log = Path(os.environ['MLFORGE_GUARD_LOG'])
with log.open('a') as stream:
    stream.write(f'active {os.getpid()}\\n')
def reject_network(event, args):
    if event in {'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo',
                 'socket.gethostbyname', 'socket.sendto'}:
        with log.open('a') as stream:
            stream.write(f'denied {event}\\n')
        os._exit(93)
sys.addaudithook(reject_network)
"""


def run(command, *, cwd, env=None):
    result = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True, timeout=600
    )
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
    with tempfile.TemporaryDirectory(prefix="mlforge-package-") as temporary:
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
            site = Path(
                run(
                    [
                        python,
                        "-I",
                        "-c",
                        "import sysconfig; print(sysconfig.get_path('purelib'))",
                    ],
                    cwd=root,
                    env=env,
                )
            )
            (site / "mlforge_installed_guard.py").write_text(NETWORK_GUARD)
            (site / "zz_mlforge_installed_guard.pth").write_text(
                "import mlforge_installed_guard\n"
            )
            destination = WORK / f"installed-{sys.version_info.minor}-{kind}"
            destination.mkdir(exist_ok=True)
            control_env = dict(env, MLFORGE_GUARD_LOG=str(destination / "control.log"))
            control = subprocess.run(
                [
                    python,
                    "-I",
                    "-c",
                    "import socket; socket.socket().connect(('127.0.0.1', 9))",
                ],
                cwd=root,
                env=control_env,
                capture_output=True,
                timeout=30,
            )
            assert control.returncode == 93, "Installed network guard inactive"
            runtime = root / f"{kind}-runtime"
            runtime.mkdir()
            temporary_files = runtime / "temporary"
            temporary_files.mkdir()
            log = destination / "network.log"
            log.write_text("")
            guarded_env = dict(
                env,
                MLFORGE_GUARD_LOG=str(log),
                TMPDIR=str(temporary_files),
                OPENBLAS_NUM_THREADS="1",
                OMP_NUM_THREADS="1",
            )
            run(
                [
                    python,
                    "-I",
                    str(ROOT / "scripts/installed_dataset_smoke.py"),
                    str(destination),
                    str(ROOT),
                ],
                cwd=runtime,
                env=guarded_env,
            )
            attempts = log.read_text().splitlines()
            assert attempts and all(line.startswith("active ") for line in attempts)
            # Real loads/overrides use fresh operation interpreters, each guarded.
            assert len(attempts) >= 12, "Missing child network-guard evidence"
            assert not list(temporary_files.iterdir()), "Installed session leaked files"
            examples = run(
                [
                    python,
                    "-I",
                    "-c",
                    """
from importlib import resources
from mlforge.datasets.importers import EXAMPLES, load_dataset
from mlforge.datasets.inference import infer_schema
assert len(EXAMPLES) == 5
for example in EXAMPLES:
    resource = resources.files('mlforge').joinpath('examples', example.filename)
    with resources.as_file(resource) as path:
        table = load_dataset(path)
    assert len(table.rows) >= 60
    assert len(infer_schema(table).columns) == len(table.columns)
print('5 packaged examples parsed and inferred')
""",
                ],
                cwd=root,
                env=guarded_env,
            )
            evidence["installations"].append(
                {
                    "kind": kind,
                    "status": "passed",
                    "examples": examples,
                    "dataset_journey": json.loads(
                        (destination / "journey.json").read_text()
                    ),
                    "network_guard": "active in parent/children; zero attempts",
                    "pip_check": run(
                        [python, "-m", "pip", "check"], cwd=root, env=guarded_env
                    ),
                    "versions": run(
                        [python, "-m", "pip", "list", "--format=json"],
                        cwd=root,
                        env=guarded_env,
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
