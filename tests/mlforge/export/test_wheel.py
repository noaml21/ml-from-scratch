import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from mlforge.contracts import DomainError
from mlforge.export.wheel import export_wheel, validate_options, validate_wheel
from mlforge.prediction import runtime


@pytest.mark.parametrize("module_name", ["sample_model", "foo__bar", "foo_"])
def test_six_offline_wheels_and_exact_resources(
    fitted_bundle, tmp_path, monkeypatch, module_name
):
    bundle, _, pipeline, records, _ = fitted_bundle
    monkeypatch.setattr(
        pipeline, "fit", lambda *args: pytest.fail("Export refitted model")
    )
    probe = dict(records[0], x=None)
    if "city" in probe:
        probe["city"] = "unseen probe category"
    wheel = export_wheel(bundle, tmp_path, module_name, "1.0.0", [records[0], probe])
    data = wheel.read_bytes()
    expected_name = {"foo__bar": "foo_bar", "foo_": "foo"}.get(module_name, module_name)
    assert wheel.name == f"{expected_name}-1.0.0-py3-none-any.whl"
    validate_wheel(data, module_name, "1.0.0")
    with zipfile.ZipFile(wheel) as archive:
        assert (
            archive.read(f"{module_name}/_runtime.py")
            == Path(runtime.__file__).read_bytes()
        )
        assert (
            hashlib.sha256(archive.read(f"{module_name}/model.skops")).hexdigest()
            == bundle.model_sha256
        )
        assert not any(
            "probes" in name or name.endswith((".csv", ".jsonl", ".tsv"))
            for name in archive.namelist()
        )
        for name in ("schema.json", "metadata.json", "MODEL_CARD.md"):
            contents = archive.read(module_name + "/" + name)
            assert b"unseen probe category" not in contents
            assert str(Path(bundle.directory).parent).encode() not in contents
        meta = json.loads(archive.read(f"{module_name}/metadata.json"))
        assert meta["training_count"] == (48 if bundle.task.supervised else 60)
    before = hashlib.sha256(data).hexdigest()
    with pytest.raises(DomainError, match="already exists"):
        export_wheel(bundle, tmp_path, module_name, "1.0.0", [records[0]])
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == before


@pytest.mark.parametrize(
    "name",
    [
        "ab",
        "class",
        "numpy",
        "numpy_",
        "scikit_learn",
        "json",
        "mlforge",
        "_hidden",
        "x;touch bad",
        "a'bad",
        "Aname",
        "a" * 51,
    ],
)
def test_invalid_names(name):
    with pytest.raises(DomainError):
        validate_options(name, "1.0.0")


@pytest.mark.parametrize(
    "version", ["1", "1.2", "01.2.3", "1.2.3rc1", "1.2.3;bad", "-1.0.0"]
)
def test_invalid_versions(version):
    with pytest.raises(DomainError):
        validate_options("valid_model", version)


def test_no_replace_publish_failure(fitted_bundle, tmp_path, monkeypatch):
    bundle, _, _, records, _ = fitted_bundle

    def fail_link(*args):
        raise OSError("simulated unsupported filesystem")

    monkeypatch.setattr("mlforge.export.wheel.os.link", fail_link)
    with pytest.raises(DomainError, match="publish"):
        export_wheel(bundle, tmp_path, "sample_model", "1.0.0", [records[0]])
    assert list(tmp_path.iterdir()) == []
