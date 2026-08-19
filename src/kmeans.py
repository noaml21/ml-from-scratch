"""A NumPy implementation of K-Means clustering."""

from __future__ import annotations

import numpy as np


class KMeans:
    """Cluster numeric observations using Lloyd's K-Means algorithm.

    Parameters
    ----------
    n_clusters:
        Number of clusters to form.
    max_iter:
        Maximum number of centroid-update iterations.
    random_state:
        Seed used to make centroid initialization reproducible.
    """

    def __init__(
        self,
        n_clusters: int = 8,
        max_iter: int = 300,
        random_state: int | None = None,
    ) -> None:
        if not isinstance(n_clusters, (int, np.integer)) or n_clusters <= 0:
            raise ValueError("n_clusters must be a positive integer")
        if not isinstance(max_iter, (int, np.integer)) or max_iter <= 0:
            raise ValueError("max_iter must be a positive integer")

        self.n_clusters = int(n_clusters)
        self.max_iter = int(max_iter)
        self.random_state = random_state

        self.labels_: np.ndarray | None = None
        self.centroids: np.ndarray | None = None
        self.labels_history: list[np.ndarray] = []
        self.centroids_history: list[np.ndarray] = []
        self.costs: list[float] = []
        self.n_iter_: int = 0

    def fit(self, X: np.ndarray) -> "KMeans":
        """Fit the model to a two-dimensional numeric array."""
        X = self._validate_X(X)
        if self.n_clusters > X.shape[0]:
            raise ValueError("n_clusters cannot exceed the number of samples")

        self.labels_ = None
        self.labels_history = []
        self.centroids_history = []
        self.costs = []
        self.n_iter_ = 0

        rng = np.random.default_rng(self.random_state)
        initial_indices = rng.choice(X.shape[0], self.n_clusters, replace=False)
        self.centroids = X[initial_indices].copy()

        for iteration in range(self.max_iter):
            old_centroids = self.centroids.copy()

            labels = self._get_labels(X)
            self.centroids = self._get_centroids(X, labels)
            self.labels_ = self._get_labels(X)

            self.labels_history.append(self.labels_.copy())
            self.centroids_history.append(self.centroids.copy())
            self.costs.append(self._calculate_cost(X))
            self.n_iter_ = iteration + 1

            if np.allclose(old_centroids, self.centroids):
                break

        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Assign each observation to its nearest fitted centroid."""
        self._check_is_fitted()
        X = self._validate_X(X)
        if X.shape[1] != self.centroids.shape[1]:
            raise ValueError("X must have the same number of features as the fitted data")
        return self._get_labels(X)

    def _get_distances(self, X: np.ndarray) -> np.ndarray:
        return np.linalg.norm(
            X[:, np.newaxis, :] - self.centroids[np.newaxis, :, :], axis=2
        )

    def _get_labels(self, X: np.ndarray) -> np.ndarray:
        return np.argmin(self._get_distances(X), axis=1)

    def _get_centroids(self, X: np.ndarray, labels: np.ndarray) -> np.ndarray:
        centroids = np.empty((self.n_clusters, X.shape[1]), dtype=float)

        for cluster_index in range(self.n_clusters):
            cluster_points = X[labels == cluster_index]
            if len(cluster_points) > 0:
                centroids[cluster_index] = np.mean(cluster_points, axis=0)
            else:
                # Keep the previous position when no samples select this cluster.
                centroids[cluster_index] = self.centroids[cluster_index]

        return centroids

    def _calculate_cost(self, X: np.ndarray) -> float:
        distances = self._get_distances(X)
        return float(np.sum(np.min(distances**2, axis=1)))

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
        if self.centroids is None:
            raise RuntimeError("KMeans must be fitted before prediction")
