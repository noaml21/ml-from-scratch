import copy
import io
import json
import shutil
import zipfile
from contextlib import nullcontext
from pathlib import Path

import pytest
import skops.io as sio

from mlforge.prediction import runtime
from mlforge.prediction.runtime import (
    ArtifactError,
    CompatibilityError,
    Predictor,
    load_pipeline,
    validate_archive,
    validate_tree_state,
)


class Unreviewed:
    pass


def test_unreviewed_type_is_refused():
    with pytest.raises(ArtifactError, match="UNTRUSTED_TYPE"):
        load_pipeline(sio.dumps(Unreviewed()), "classification.logistic")


@pytest.mark.parametrize(
    "names",
    [
        ["../x"],
        ["/x"],
        ["x", "x"],
        ["dir\\x"],
        ["C:/absolute"],
        ["./alias"],
        ["dir//alias"],
    ],
)
def test_bad_archive_paths(names):
    buffer = io.BytesIO()
    expected = (
        pytest.warns(UserWarning, match="Duplicate name")
        if names == ["x", "x"]
        else nullcontext()
    )
    with expected, zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, b"content")
    with pytest.raises(ArtifactError):
        validate_archive(buffer.getvalue(), members=200)


def test_archive_budgets(monkeypatch):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("large", b"x" * 1000)
    with pytest.raises(ArtifactError, match="ARCHIVE_LIMIT"):
        validate_archive(buffer.getvalue(), members=0)
    monkeypatch.setattr(runtime, "MAX_EXPANDED", 999)
    with pytest.raises(ArtifactError, match="ARCHIVE_LIMIT"):
        validate_archive(buffer.getvalue(), members=2000)


def test_hash_and_compatibility_before_model_load(fitted_bundle, tmp_path):
    bundle, _, _, _, _ = fitted_bundle
    copied = tmp_path / "copy"
    shutil.copytree(bundle.directory, copied)
    metadata = json.loads((copied / "metadata.json").read_text())
    original = copy.deepcopy(metadata)
    metadata["environment"]["dependencies"]["numpy"] = "0.0.0"
    (copied / "metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(CompatibilityError):
        Predictor._from_directory(copied)
    (copied / "metadata.json").write_text(json.dumps(original))
    (copied / "model.skops").write_bytes(b"corrupt")
    with pytest.raises(ArtifactError, match="HASH_MISMATCH"):
        Predictor._from_directory(copied)


def test_valid_forest_nested_budget_and_corrupt_state(fitted_bundle):
    bundle, _, pipeline, _, _ = fitted_bundle
    if not bundle.model_id.endswith("forest"):
        # Nonforest variants also exercise their real nested archives.
        validate_archive(
            (Path(bundle.directory) / "model.skops").read_bytes(), members=2000
        )
        return
    data = (Path(bundle.directory) / "model.skops").read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert 200 < len(archive.infolist()) <= 2000
    forest = pipeline.steps[-1][1]
    classes = (
        int(forest.n_classes_) if bundle.model_id.startswith("classification") else 1
    )
    state = forest.estimators_[0].tree_.__getstate__()
    validate_tree_state(state, forest.n_features_in_, classes)
    for mutation in (
        "child",
        "feature",
        "cycle",
        "shape",
        "finite",
        "unreachable",
        "leaf",
        "missing_branch",
        "depth",
    ):
        bad = copy.deepcopy(state)
        if mutation == "child":
            bad["nodes"]["left_child"][0] = bad["node_count"] + 1
        elif mutation == "feature":
            bad["nodes"]["feature"][0] = forest.n_features_in_
        elif mutation == "cycle":
            bad["nodes"]["left_child"][0] = 0
        elif mutation == "shape":
            bad["values"] = bad["values"][:-1]
        elif mutation == "finite":
            bad["values"][0] = float("nan")
        elif mutation == "leaf":
            leaf = (bad["nodes"]["left_child"] == -1).nonzero()[0][0]
            bad["nodes"]["threshold"][leaf] = 0
        elif mutation == "missing_branch":
            bad["nodes"]["missing_go_to_left"][0] = 2
        elif mutation == "depth":
            bad["max_depth"] = 13
        else:
            bad["nodes"]["left_child"][0] = -1
            bad["nodes"]["right_child"][0] = -1
            bad["nodes"]["feature"][0] = -2
        with pytest.raises(ArtifactError, match="TREE_STRUCTURE"):
            validate_tree_state(bad, forest.n_features_in_, classes)
