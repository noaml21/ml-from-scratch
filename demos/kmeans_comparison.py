"""Compare the project K-Means implementation with scikit-learn."""

from pathlib import Path
import sys

import numpy as np
from sklearn.cluster import KMeans as SklearnKMeans


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.kmeans import KMeans


def sorted_centroids(centroids: np.ndarray) -> np.ndarray:
    order = np.lexsort((centroids[:, 1], centroids[:, 0]))
    return centroids[order]


def main() -> None:
    rng = np.random.default_rng(42)
    cluster_centers = np.array([[-4.0, -3.0], [0.0, 4.0], [5.0, -1.0]])
    X = np.vstack(
        [rng.normal(loc=center, scale=0.6, size=(30, 2)) for center in cluster_centers]
    )

    our_model = KMeans(n_clusters=3, random_state=42).fit(X)
    sklearn_model = SklearnKMeans(
        n_clusters=3, random_state=42, n_init=10
    ).fit(X)

    print(f"Our implementation iterations: {our_model.n_iter_}")
    print(f"Scikit-learn iterations: {sklearn_model.n_iter_}")
    print(f"Our implementation final cost: {our_model.costs[-1]:.6f}")
    print(f"Scikit-learn inertia: {sklearn_model.inertia_:.6f}")
    print("Our implementation centroids (sorted):")
    print(sorted_centroids(our_model.centroids))
    print("Scikit-learn centroids (sorted):")
    print(sorted_centroids(sklearn_model.cluster_centers_))


if __name__ == "__main__":
    main()
