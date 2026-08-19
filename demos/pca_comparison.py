"""Compare the project PCA implementation with scikit-learn."""

from pathlib import Path
import sys

import numpy as np
from sklearn.decomposition import PCA as SklearnPCA


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.pca import PCA


def main() -> None:
    rng = np.random.default_rng(42)
    latent_data = rng.normal(size=(200, 2))
    mixing_matrix = np.array(
        [[1.0, 0.5], [2.0, -0.2], [-0.5, 1.5], [1.0, 1.0]]
    )
    X = latent_data @ mixing_matrix.T + rng.normal(scale=0.1, size=(200, 4))

    our_pca = PCA(n_components=2).fit(X)
    sklearn_pca = SklearnPCA(n_components=2).fit(X)

    our_reduced = our_pca.transform(X)
    sklearn_reduced = sklearn_pca.transform(X)
    our_reconstructed = our_pca.inverse_transform(our_reduced)
    sklearn_reconstructed = sklearn_pca.inverse_transform(sklearn_reduced)

    our_mse = np.mean((X - our_reconstructed) ** 2)
    sklearn_mse = np.mean((X - sklearn_reconstructed) ** 2)

    np.set_printoptions(precision=8, suppress=True)
    print(f"Our mean: {our_pca.mean_}")
    print(f"Scikit-learn mean: {sklearn_pca.mean_}")
    print(f"Our explained variance: {our_pca.explained_variance_}")
    print(f"Scikit-learn explained variance: {sklearn_pca.explained_variance_}")
    print("Our components (columns):")
    print(our_pca.components_)
    print("Scikit-learn components (rows):")
    print(sklearn_pca.components_)
    print(f"Our reconstruction MSE: {our_mse:.8f}")
    print(f"Scikit-learn reconstruction MSE: {sklearn_mse:.8f}")


if __name__ == "__main__":
    main()
