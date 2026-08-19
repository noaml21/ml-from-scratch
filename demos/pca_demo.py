"""Visual demonstration of image reconstruction with the project's PCA."""

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
from sklearn.datasets import load_digits


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.pca import PCA


def main() -> None:
    digits = load_digits()
    X = digits.data

    rng = np.random.default_rng(42)
    image_index = rng.integers(X.shape[0])
    original = X[image_index : image_index + 1]

    component_counts = [30, 10, 3]
    reconstructions = []

    for n_components in component_counts:
        pca = PCA(n_components=n_components).fit(X)
        reduced = pca.transform(original)
        reconstructed = pca.inverse_transform(reduced)
        reconstructions.append(reconstructed)

        mse = np.mean((original - reconstructed) ** 2)
        print(f"{n_components} components reconstruction MSE: {mse:.6f}")

    images = [original, *reconstructions]
    titles = ["Original", "30 components", "10 components", "3 components"]
    grayscale_min, grayscale_max = X.min(), X.max()

    figure, axes = plt.subplots(1, 4, figsize=(10, 3))
    for axis, image, title in zip(axes, images, titles):
        axis.imshow(
            image.reshape(digits.images[0].shape),
            cmap="gray",
            vmin=grayscale_min,
            vmax=grayscale_max,
        )
        axis.set_title(title)
        axis.axis("off")

    plt.tight_layout()
    figure.savefig(
        PROJECT_ROOT / "assets" / "pca_reconstruction.png",
        dpi=150,
        bbox_inches="tight",
    )
    plt.show()


if __name__ == "__main__":
    main()
