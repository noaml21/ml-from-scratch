"""Actual exporter cancellation and inherited no-network guard in every child."""

import asyncio
import json
import os
import subprocess
import sys
import sysconfig
import uuid
from pathlib import Path

import pytest

from mlforge.contracts import CandidateResult, CandidateStatus, candidate_data
from mlforge.execution.coordinator import Coordinator
from mlforge.execution.protocol import (
    Identity,
    Operation,
    Request,
    json_data,
    write_owned,
)

GUARD = """import os, sys
from pathlib import Path
root = Path(os.environ["MLFORGE_AUDIT_DIR"])
(root / ("audit-" + str(os.getpid()))).write_text("active")
def guard(event, args):
    if event in {"socket.connect", "socket.connect_ex",
                 "socket.getaddrinfo", "socket.sendto"}:
        os._exit(93)
sys.addaudithook(guard)
if (os.environ.get("MLFORGE_PAUSE_BACKEND") == "1"
        and sys.argv[0].endswith("_in_process.py")):
    import signal
    import setuptools.build_meta
    def blocked(*args, **kwargs):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        child = os.fork()
        if child == 0:
            while True:
                signal.pause()
        (root / "backend-ready.json").write_text(
            '{"pid":%d,"child":%d}' % (os.getpid(), child))
        while True:
            signal.pause()
    setuptools.build_meta.build_wheel = blocked
"""


@pytest.fixture(scope="module")
def guarded_python(tmp_path_factory):
    import mlforge

    root = tmp_path_factory.mktemp("guarded-worker")
    env = root / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(env)], check=True
    )
    site = (
        env
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    # Reuse the pinned test dependencies; this is a guarded worker interpreter,
    # not a consumer-installation claim. -I children still process site .pth files.
    (site / "test_dependencies.pth").write_text(
        sysconfig.get_path("purelib")
        + "\n"
        + str(Path(mlforge.__file__).parent.parent)
        + "\n"
    )
    (site / "mlforge_test_guard.py").write_text(GUARD)
    (site / "zz_mlforge_test_guard.pth").write_text("import mlforge_test_guard\n")
    guarded = subprocess.run(
        [
            str(env / "bin/python"),
            "-I",
            "-c",
            "import socket; socket.socket().connect(('127.0.0.1', 9))",
        ],
        env=dict(os.environ, MLFORGE_AUDIT_DIR=str(root)),
        capture_output=True,
    )
    assert guarded.returncode == 93, (
        "Inherited network guard did not block a connection"
    )
    return env / "bin/python"


def export_request(owner, evaluated_bundle, destination, publication):
    bundle, _, _, records, _ = evaluated_bundle
    operation_id = uuid.uuid4().hex
    source = owner.root / uuid.uuid4().hex
    source.mkdir(mode=0o700)
    candidate = CandidateResult(
        bundle.model_id, CandidateStatus.COMPLETED, 0, bundle=bundle
    )
    refs = [
        write_owned(
            owner.root,
            f"{source.name}/candidate.json",
            json_data(candidate_data(candidate)),
        )
    ]
    for name in ("schema.json", "metadata.json", "model.skops"):
        refs.append(
            write_owned(
                owner.root,
                f"{source.name}/{name}",
                (Path(bundle.directory) / name).read_bytes(),
            )
        )
    refs.append(
        write_owned(owner.root, f"probes-{operation_id}.json", json_data(records[:2]))
    )
    identity = Identity(
        uuid.uuid4().hex, 1, operation_id, Operation.EXPORT, bundle.model_id
    )
    options = {
        "publication_directory": str(publication),
        "module_name": "owned_model",
        "version": "1.0.0",
    }
    return Request(
        identity, tuple(refs), (f"{operation_id}/export.json",), json.dumps(options)
    )


async def ready(path, task):
    while not path.exists():
        if task.done():
            result = task.result()
            raise AssertionError(
                f"Export exited before handshake: {result.error_code}, "
                f"exit {result.returncode}"
            )
        await asyncio.sleep(0.01)
    return json.loads(path.read_text())


@pytest.mark.parametrize("boundary", ["publication", "backend"])
async def test_cancel_actual_export_cleans_owned_staging_and_descendants(
    evaluated_bundle,
    guarded_python,
    boundary,
    tmp_path,
    monkeypatch,
):
    destination = tmp_path / "chosen"
    destination.mkdir()
    sentinel = destination / "unrelated"
    sentinel.write_text("preserved")
    async with Coordinator() as owner:
        monkeypatch.setenv("MLFORGE_AUDIT_DIR", str(owner.root))
        monkeypatch.setenv(
            "MLFORGE_PAUSE_BACKEND", "1" if boundary == "backend" else "0"
        )
        original = asyncio.create_subprocess_exec
        launched = []
        pause_publication = boundary == "publication"

        async def launch(*args, **kwargs):
            command = (
                [
                    str(guarded_python),
                    str(Path(__file__).parent / "fixtures/export_child.py"),
                    args[3],
                    args[4],
                ]
                if pause_publication
                else [str(guarded_python), *args[1:]]
            )
            child = await original(*command, **kwargs)
            launched.append(child.pid)
            return child

        monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
        async with owner.publication_staging(destination) as staging:
            req = export_request(owner, evaluated_bundle, destination, staging)
            task = asyncio.create_task(owner.run(req))
            try:
                marker = owner.root / f"{boundary}-ready.json"
                info = await asyncio.wait_for(ready(marker, task), 40)
                if boundary == "publication":
                    assert Path(info["path"]).parent == staging
                owner.cancel()
                result = await asyncio.wait_for(task, 5)
                assert result.cancelled and not result.completed
                for pid in {
                    *launched,
                    info["pid"],
                    *([info["child"]] if "child" in info else []),
                }:
                    with pytest.raises(ProcessLookupError):
                        os.kill(pid, 0)
            finally:
                owner.cancel()
                await asyncio.wait_for(task, 5)
        assert not staging.exists()
        assert list(destination.iterdir()) == [sentinel]
        assert sentinel.read_text() == "preserved"
        # Worker, build frontend/backend (and verifier for publication) are guarded.
        assert len(list(owner.root.glob("audit-*"))) >= 3
        if boundary == "publication":
            # Retained evaluated bundle retries successfully with the same runtime.
            pause_publication = False
            async with owner.publication_staging(destination) as retry_staging:
                retry = export_request(
                    owner, evaluated_bundle, destination, retry_staging
                )
                outcome = await owner.run(retry)
                assert outcome.completed
            assert not retry_staging.exists()
            assert len(list(destination.glob("*.whl"))) == 1
            assert sentinel.read_text() == "preserved"


async def test_replaced_staging_never_removes_unrelated_path(tmp_path):
    from mlforge.contracts import DomainError

    owner = await Coordinator().__aenter__()
    moved = None
    try:
        with pytest.raises(DomainError, match="ownership changed"):
            async with owner.publication_staging(tmp_path) as staging:
                moved = tmp_path / "owned-moved"
                staging.rename(moved)
                staging.symlink_to(tmp_path / "sentinel", target_is_directory=True)
                sentinel = tmp_path / "sentinel"
                sentinel.mkdir()
                (sentinel / "keep").write_text("unrelated")
        assert (sentinel / "keep").read_text() == "unrelated"
        # Restore only this test's substitution so normal owner cleanup can finish.
        staging.unlink()
        moved.rename(staging)
    finally:
        await owner.close()


async def test_destination_failure_preserves_existing_resource(tmp_path):
    from mlforge.contracts import DomainError

    existing = tmp_path / "existing"
    existing.write_text("keep")
    async with Coordinator() as owner:
        with pytest.raises(DomainError, match="private export staging"):
            async with owner.publication_staging(existing):
                pytest.fail("A file cannot become a staging directory")
        assert existing.read_text() == "keep"


async def test_unowned_publication_directory_is_rejected_before_spawn(
    tmp_path, monkeypatch
):
    foreign = tmp_path / ".mlforge-unowned"
    foreign.mkdir(mode=0o700)
    (foreign / "keep").write_text("unrelated")

    async def forbidden(*args, **kwargs):
        pytest.fail("Unowned export staging must not reach a child")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    async with Coordinator() as owner:
        identity = Identity(
            uuid.uuid4().hex,
            1,
            uuid.uuid4().hex,
            Operation.EXPORT,
            "classification.logistic",
        )
        req = Request(
            identity,
            (),
            (f"{identity.operation_id}/export.json",),
            json.dumps(
                {
                    "publication_directory": str(foreign),
                    "module_name": "owned_model",
                    "version": "1.0.0",
                }
            ),
        )
        result = await owner.run(req)
        assert result.error_code == "PROTOCOL" and result.fatal
        assert not list(owner.root.iterdir())
    assert (foreign / "keep").read_text() == "unrelated"
