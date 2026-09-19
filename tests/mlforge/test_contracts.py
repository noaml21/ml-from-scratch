"""Value ownership and fixed estimator defaults."""

from dataclasses import FrozenInstanceError

import pytest

from mlforge.contracts import ExperimentSpec, TaskKind
from mlforge.datasets.records import Cell, Column, TabularDataset
from mlforge.models import MODELS, model_spec


def test_dataset_copies_nested_sequences():
    rows = [[Cell("001")]]
    table = TabularDataset([Column("c0", "zip")], rows, "csv", "fingerprint")
    rows[0][0] = Cell("changed")
    assert table.rows[0][0].raw_text == "001"
    with pytest.raises(FrozenInstanceError):
        table.rows[0][0].raw_text = "changed"


@pytest.mark.parametrize(
    "features,target,task",
    [
        (["y"], "y", TaskKind.CLASSIFICATION),
        (["x", "x"], "y", TaskKind.CLASSIFICATION),
        (["x"], None, TaskKind.REGRESSION),
        (["x"], "y", TaskKind.CLUSTERING),
        ([], None, TaskKind.REDUCTION),
    ],
)
def test_experiment_structural_gates(features, target, task):
    with pytest.raises(ValueError):
        ExperimentSpec(1, "fingerprint", task, target, features, ["model"])


def test_fixed_registry_defaults():
    assert len(MODELS) == 6
    assert len({model.id for model in MODELS}) == 6
    for model in MODELS:
        estimator = model.factory(None)
        params = estimator.get_params()
        if model.id.endswith("forest"):
            assert params["n_estimators"] == 100
            assert params["max_depth"] == 12
            assert params["min_samples_leaf"] == 2
            assert params["n_jobs"] == 1
        if "random_state" in params and model.id != "reduction.pca":
            assert params["random_state"] == 42
        assert model.scale_numeric == (not model.id.endswith("forest"))
    assert model_spec("classification.logistic").factory(None).max_iter == 1000
    assert model_spec("clustering.kmeans").factory(4).n_clusters == 4
    assert model_spec("reduction.pca").factory(1).n_components == 1
    assert model_spec("reduction.pca").factory(1).svd_solver == "full"


def test_unknown_model_is_refused():
    with pytest.raises(ValueError, match="Unknown model"):
        model_spec("user.estimator")
