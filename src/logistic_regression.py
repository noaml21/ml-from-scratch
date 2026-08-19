"""Binary Logistic Regression trained with stochastic gradient descent."""

from __future__ import annotations

import numpy as np


class LogisticRegression:
    """Binary Logistic Regression using the student's SGD training algorithm.

    Parameters
    ----------
    learning_rate:
        Step size used for each stochastic gradient update.
    epochs:
        Number of complete passes over the training data.
    random_state:
        Seed used when shuffling samples during each epoch.
    """

    def __init__(
        self,
        learning_rate: float = 0.01,
        epochs: int = 10_000,
        random_state: int | None = None,
    ) -> None:
        if learning_rate <= 0:
            raise ValueError("learning_rate must be positive")
        if not isinstance(epochs, (int, np.integer)) or epochs <= 0:
            raise ValueError("epochs must be a positive integer")

        self.learning_rate = float(learning_rate)
        self.epochs = int(epochs)
        self.random_state = random_state

        self.weights_: np.ndarray | None = None
        self.bias_: float | None = None
        self.loss_history_: list[float] = []
        self.n_iter_: int = 0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LogisticRegression":
        """Fit the model to a numeric feature matrix and binary labels."""
        X, y = self._validate_training_data(X, y)
        X_with_intercept = np.column_stack((np.ones(X.shape[0]), X))
        theta = np.zeros(X_with_intercept.shape[1], dtype=float)
        rng = np.random.default_rng(self.random_state)

        self.loss_history_ = []
        self.n_iter_ = 0

        for epoch in range(self.epochs):
            for sample_index in rng.permutation(y.size):
                xi = X_with_intercept[sample_index]
                yi = y[sample_index]
                probability = self._sigmoid(xi @ theta)
                gradient = (probability - yi) * xi
                theta -= self.learning_rate * gradient

            self.loss_history_.append(self._calculate_loss(theta, X_with_intercept, y))
            self.n_iter_ = epoch + 1

        self.bias_ = float(theta[0])
        self.weights_ = theta[1:].copy()
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return the estimated probability of the positive class."""
        self._check_is_fitted()
        X = self._validate_X(X)
        if X.shape[1] != self.weights_.shape[0]:
            raise ValueError("X must have the same number of features as the fitted data")
        return self._sigmoid(X @ self.weights_ + self.bias_)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict binary labels using a probability threshold of 0.5."""
        return (self.predict_proba(X) >= 0.5).astype(int)

    @staticmethod
    def _sigmoid(z: np.ndarray) -> np.ndarray:
        z = np.clip(z, -500.0, 500.0)
        return 1.0 / (1.0 + np.exp(-z))

    def _calculate_loss(
        self, theta: np.ndarray, X: np.ndarray, y: np.ndarray
    ) -> float:
        probabilities = self._sigmoid(X @ theta)
        epsilon = 1e-15
        probabilities = np.clip(probabilities, epsilon, 1.0 - epsilon)
        loss = -np.mean(
            y * np.log(probabilities) + (1.0 - y) * np.log(1.0 - probabilities)
        )
        return float(loss)

    @staticmethod
    def _validate_X(X: np.ndarray) -> np.ndarray:
        try:
            array = np.asarray(X, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError("X must contain numeric values") from exc

        if array.ndim != 2:
            raise ValueError("X must be a two-dimensional array")
        if array.shape[0] == 0 or array.shape[1] == 0:
            raise ValueError("X must contain at least one sample and one feature")
        if not np.all(np.isfinite(array)):
            raise ValueError("X must contain only finite values")
        return array

    @classmethod
    def _validate_training_data(
        cls, X: np.ndarray, y: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        X = cls._validate_X(X)
        y = np.asarray(y)

        if y.ndim != 1:
            raise ValueError("y must be a one-dimensional array")
        if y.shape[0] != X.shape[0]:
            raise ValueError("X and y must contain the same number of samples")
        if not np.all(np.isin(y, (0, 1))):
            raise ValueError("y must contain only binary labels 0 and 1")
        return X, y.astype(float)

    def _check_is_fitted(self) -> None:
        if self.weights_ is None or self.bias_ is None:
            raise RuntimeError("LogisticRegression must be fitted before prediction")
