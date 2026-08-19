import numpy as np
import pytest

from src.kmeans import KMeans


X = np.array(
    [
        [1, 1],
        [1, 2],
        [2, 1],
        [8, 8],
        [8, 9],
        [9, 8],
    ],
    dtype=float,
)


def test_basic_clustering():
    model = KMeans(n_clusters=2, random_state=42).fit(X)

    assert np.all(model.labels_[:3] == model.labels_[0])
    assert np.all(model.labels_[3:] == model.labels_[3])
    assert model.labels_[0] != model.labels_[3]


def test_centroid_correctness():
    model = KMeans(n_clusters=2, random_state=42).fit(X)
    centroids = model.centroids[np.argsort(model.centroids[:, 0])]
    expected = np.array([[1.333333, 1.333333], [8.333333, 8.333333]])

    np.testing.assert_allclose(centroids, expected, rtol=1e-6)


def test_reproducibility():
    first_model = KMeans(n_clusters=2, random_state=42).fit(X)
    second_model = KMeans(n_clusters=2, random_state=42).fit(X)

    np.testing.assert_array_equal(first_model.labels_, second_model.labels_)
    np.testing.assert_allclose(first_model.centroids, second_model.centroids)


def test_cost_history_is_non_increasing():
    model = KMeans(n_clusters=2, random_state=42).fit(X)

    assert all(
        later_cost <= earlier_cost
        for earlier_cost, later_cost in zip(model.costs, model.costs[1:])
    )


def test_predict_before_fit_raises_runtime_error():
    model = KMeans(n_clusters=2, random_state=42)

    with pytest.raises(RuntimeError):
        model.predict(X)
