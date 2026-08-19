import numpy as np
import pytest

from src.pca import PCA


RNG = np.random.default_rng(42)
X = RNG.normal(size=(100, 5))


def test_dimensionality_reduction():
    pca = PCA(n_components=2).fit(X)

    assert pca.transform(X).shape == (100, 2)


def test_reconstruction_shape():
    pca = PCA(n_components=2).fit(X)
    reduced = pca.transform(X)
    reconstructed = pca.inverse_transform(reduced)

    assert reconstructed.shape == X.shape


def test_correlated_data_reconstruction():
    rng = np.random.default_rng(42)
    first_feature = rng.normal(size=100)
    second_feature = 2.0 * first_feature + rng.normal(scale=0.1, size=100)
    correlated_data = np.column_stack((first_feature, second_feature))

    pca = PCA(n_components=1).fit(correlated_data)
    reduced = pca.transform(correlated_data)
    reconstructed = pca.inverse_transform(reduced)
    reconstruction_mse = np.mean((correlated_data - reconstructed) ** 2)

    assert reconstruction_mse < 0.01


def test_explained_variance_is_non_increasing():
    pca = PCA(n_components=4).fit(X)

    assert np.all(np.diff(pca.explained_variance_) <= 0)


def test_transform_before_fit_raises_runtime_error():
    pca = PCA(n_components=2)

    with pytest.raises(RuntimeError):
        pca.transform(X)
