"""Principal Component Analysis implemented with NumPy."""

from __future__ import annotations

import numpy as np


class PCA:
    """Reduce numeric data using covariance-matrix eigendecomposition.

    Parameters
    ----------
    n_components:
        Number of principal components to retain.

    Notes
    -----
    The columns of ``components_`` are the selected principal components.
    """

    def __init__(self, n_components: int) -> None:
        if not isinstance(n_components, (int, np.integer)) or n_components <= 0:
            raise ValueError("n_components must be a positive integer")

        self.n_components = int(n_components)
        self.mean_: np.ndarray | None = None
        self.components_: np.ndarray | None = None
        self.explained_variance_: np.ndarray | None = None

    def fit(self, X: np.ndarray) -> "PCA":
        """Learn the leading principal components from X."""
        X = self._validate_X(X)
        if X.shape[0] < 2:
            raise ValueError("X must contain at least two samples")
        if self.n_components > X.shape[1]:
            raise ValueError("n_components cannot exceed the number of features")

        self.mean_ = np.mean(X, axis=0)
        X_centered = X - self.mean_
        covariance_matrix = np.atleast_2d(np.cov(X_centered, rowvar=False))

        eigenvalues, eigenvectors = np.linalg.eigh(covariance_matrix)
        sorted_indices = np.argsort(eigenvalues)[::-1]

        selected_indices = sorted_indices[: self.n_components]
        self.components_ = eigenvectors[:, selected_indices]
        self.explained_variance_ = eigenvalues[selected_indices]
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Project X onto the learned principal components."""
        self._check_is_fitted()
        X = self._validate_X(X)
        if X.shape[1] != self.mean_.shape[0]:
            raise ValueError("X must have the same number of features as the fitted data")

        X_centered = X - self.mean_
        return X_centered @ self.components_

    def inverse_transform(self, X_reduced: np.ndarray) -> np.ndarray:
        """Reconstruct reduced data in the original feature space."""
        self._check_is_fitted()
        X_reduced = self._validate_X(X_reduced)
        if X_reduced.shape[1] != self.n_components:
            raise ValueError("X_reduced must have n_components columns")

        return X_reduced @ self.components_.T + self.mean_

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

    def _check_is_fitted(self) -> None:
        if self.mean_ is None or self.components_ is None:
            raise RuntimeError("PCA must be fitted before transforming data")
