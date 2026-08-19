"""Compare the project Logistic Regression with scikit-learn."""

from pathlib import Path
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression as SklearnLogisticRegression


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.logistic_regression import LogisticRegression


def main() -> None:
    rng = np.random.default_rng(42)
    class_zero = rng.normal(loc=[-1.0, -0.8], scale=1.0, size=(100, 2))
    class_one = rng.normal(loc=[1.0, 0.8], scale=1.0, size=(100, 2))
    X = np.vstack((class_zero, class_one))
    y = np.concatenate((np.zeros(100, dtype=int), np.ones(100, dtype=int)))

    shuffled_indices = rng.permutation(len(y))
    train_indices = shuffled_indices[:150]
    test_indices = shuffled_indices[150:]
    X_train, y_train = X[train_indices], y[train_indices]
    X_test, y_test = X[test_indices], y[test_indices]

    our_model = LogisticRegression(
        learning_rate=0.01, epochs=500, random_state=42
    ).fit(X_train, y_train)
    sklearn_model = SklearnLogisticRegression(
        C=np.inf, solver="lbfgs", max_iter=1_000, random_state=42
    ).fit(X_train, y_train)

    our_training_accuracy = np.mean(our_model.predict(X_train) == y_train)
    our_test_accuracy = np.mean(our_model.predict(X_test) == y_test)

    print(f"Our training accuracy: {our_training_accuracy:.4f}")
    print(f"Scikit-learn training accuracy: {sklearn_model.score(X_train, y_train):.4f}")
    print(f"Our test accuracy: {our_test_accuracy:.4f}")
    print(f"Scikit-learn test accuracy: {sklearn_model.score(X_test, y_test):.4f}")
    print(f"Our learned weights: {our_model.weights_}")
    print(f"Scikit-learn learned coefficients: {sklearn_model.coef_[0]}")
    print(f"Our bias: {our_model.bias_:.6f}")
    print(f"Scikit-learn intercept: {sklearn_model.intercept_[0]:.6f}")
    print(f"Our final training loss: {our_model.loss_history_[-1]:.6f}")


if __name__ == "__main__":
    main()
