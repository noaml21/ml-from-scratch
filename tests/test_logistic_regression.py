import numpy as np
import pytest

from src.logistic_regression import LogisticRegression


RNG = np.random.default_rng(42)
X = np.vstack(
    (
        RNG.normal(loc=[-2.0, -2.0], scale=0.4, size=(25, 2)),
        RNG.normal(loc=[2.0, 2.0], scale=0.4, size=(25, 2)),
    )
)
Y = np.concatenate((np.zeros(25, dtype=int), np.ones(25, dtype=int)))


def test_basic_learning():
    model = LogisticRegression(
        learning_rate=0.1, epochs=100, random_state=42
    ).fit(X, Y)

    accuracy = np.mean(model.predict(X) == Y)
    assert accuracy >= 0.95


def test_loss_decreases():
    model = LogisticRegression(
        learning_rate=0.1, epochs=100, random_state=42
    ).fit(X, Y)

    assert model.loss_history_[-1] < model.loss_history_[0]


def test_probability_range():
    model = LogisticRegression(
        learning_rate=0.1, epochs=100, random_state=42
    ).fit(X, Y)

    probabilities = model.predict_proba(X)
    assert np.all((probabilities >= 0.0) & (probabilities <= 1.0))


def test_reproducibility():
    first_model = LogisticRegression(
        learning_rate=0.1, epochs=100, random_state=42
    ).fit(X, Y)
    second_model = LogisticRegression(
        learning_rate=0.1, epochs=100, random_state=42
    ).fit(X, Y)

    np.testing.assert_allclose(first_model.weights_, second_model.weights_)
    np.testing.assert_allclose(first_model.bias_, second_model.bias_)
    np.testing.assert_array_equal(first_model.predict(X), second_model.predict(X))


def test_predict_before_fit_raises_runtime_error():
    model = LogisticRegression()

    with pytest.raises(RuntimeError):
        model.predict(X)
