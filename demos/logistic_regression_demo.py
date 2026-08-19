"""Visual demonstration of the project's Logistic Regression model."""

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.logistic_regression import LogisticRegression


def main() -> None:
    rng = np.random.default_rng(42)
    class_zero = rng.normal(loc=[-0.9, -0.7], scale=[1.1, 1.0], size=(60, 2))
    class_one = rng.normal(loc=[0.9, 0.7], scale=[1.1, 1.0], size=(60, 2))
    X = np.vstack((class_zero, class_one))
    y = np.concatenate((np.zeros(60, dtype=int), np.ones(60, dtype=int)))

    model = LogisticRegression(
        learning_rate=0.01, epochs=300, random_state=42
    ).fit(X, y)

    figure, (boundary_ax, loss_ax) = plt.subplots(1, 2, figsize=(12, 5))
    boundary_ax.scatter(
        class_zero[:, 0], class_zero[:, 1], color="tab:blue", marker="o", label="Class 0"
    )
    boundary_ax.scatter(
        class_one[:, 0], class_one[:, 1], color="tab:orange", marker="^", label="Class 1"
    )
    x_boundary = np.array([X[:, 0].min(), X[:, 0].max()])
    y_boundary = -(model.bias_ + model.weights_[0] * x_boundary) / model.weights_[1]
    boundary_ax.plot(x_boundary, y_boundary, color="black", label="Decision boundary")
    boundary_ax.set(
        title="Logistic Regression Classification",
        xlabel="Feature 1",
        ylabel="Feature 2",
    )
    boundary_ax.legend()
    boundary_ax.grid(alpha=0.25)

    epochs = np.arange(1, len(model.loss_history_) + 1)
    loss_ax.plot(epochs, model.loss_history_)
    loss_ax.set(
        title="Training Loss by Epoch",
        xlabel="Epoch",
        ylabel="Binary cross-entropy loss",
    )
    loss_ax.grid(alpha=0.25)

    accuracy = np.mean(model.predict(X) == y)
    print(f"Training accuracy: {accuracy:.4f}")
    print(f"Learned weights: {model.weights_}")
    print(f"Learned bias: {model.bias_:.6f}")
    print(f"First recorded loss: {model.loss_history_[0]:.6f}")
    print(f"Final loss: {model.loss_history_[-1]:.6f}")

    figure.savefig(
        PROJECT_ROOT / "assets" / "logistic_regression_demo.png",
        dpi=150,
        bbox_inches="tight",
    )
    plt.show()


if __name__ == "__main__":
    main()
