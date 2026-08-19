"""Small visual demonstration of the project's K-Means implementation."""

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.kmeans import KMeans


def main() -> None:
    rng = np.random.default_rng(42)
    cluster_centers = np.array([[-4.0, -3.0], [0.0, 4.0], [5.0, -1.0]])
    X = np.vstack(
        [rng.normal(loc=center, scale=0.6, size=(30, 2)) for center in cluster_centers]
    )

    model = KMeans(n_clusters=3, random_state=27)
    model.fit(X)

    figure, (cluster_ax, cost_ax) = plt.subplots(1, 2, figsize=(12, 5))
    for cluster_index in range(model.n_clusters):
        points = X[model.labels_ == cluster_index]
        cluster_ax.scatter(
            points[:, 0], points[:, 1], label=f"Cluster {cluster_index}"
        )
    cluster_ax.scatter(
        model.centroids[:, 0],
        model.centroids[:, 1],
        marker="X",
        s=180,
        c="black",
        edgecolors="white",
        linewidths=1.2,
        label="Centroids",
    )
    cluster_ax.set(title="K-Means Clusters", xlabel="Feature 1", ylabel="Feature 2")
    cluster_ax.legend()
    cluster_ax.grid(alpha=0.25)

    iterations = np.arange(1, len(model.costs) + 1)
    cost_ax.plot(iterations, model.costs, marker="o")
    cost_ax.set(
        title="K-Means Cost by Iteration",
        xlabel="Iteration",
        ylabel="Cost",
    )
    cost_ax.set_xticks(iterations)
    cost_ax.grid(alpha=0.25)

    print("Final centroids:")
    print(model.centroids)
    print(f"Number of iterations: {model.n_iter_}")
    print(f"Final cost: {model.costs[-1]:.6f}")

    figure.savefig(
        PROJECT_ROOT / "assets" / "kmeans_demo.png",
        dpi=150,
        bbox_inches="tight",
    )
    plt.show()


if __name__ == "__main__":
    main()
