"""Six concrete sklearn factories; importing descriptions performs no fitting."""

from collections.abc import Callable
from dataclasses import dataclass

from mlforge.contracts import TaskKind


def logistic(option: int | None = None) -> object:
    from sklearn.linear_model import LogisticRegression

    return LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000, random_state=42)


def classifier_forest(option: int | None = None) -> object:
    from sklearn.ensemble import RandomForestClassifier

    return RandomForestClassifier(
        n_estimators=100, max_depth=12, min_samples_leaf=2, random_state=42, n_jobs=1
    )


def linear(option: int | None = None) -> object:
    from sklearn.linear_model import LinearRegression

    return LinearRegression()


def regressor_forest(option: int | None = None) -> object:
    from sklearn.ensemble import RandomForestRegressor

    return RandomForestRegressor(
        n_estimators=100, max_depth=12, min_samples_leaf=2, random_state=42, n_jobs=1
    )


def kmeans(option: int | None = None) -> object:
    from sklearn.cluster import KMeans

    return KMeans(
        n_clusters=3 if option is None else option,
        init="k-means++",
        n_init=10,
        max_iter=300,
        random_state=42,
    )


def pca(option: int | None = None) -> object:
    from sklearn.decomposition import PCA

    return PCA(n_components=2 if option is None else option, svd_solver="full")


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    task: TaskKind
    factory: Callable[[int | None], object]
    scale_numeric: bool
    help_key: str


MODELS = (
    ModelSpec(
        "classification.logistic",
        "Logistic Regression",
        TaskKind.CLASSIFICATION,
        logistic,
        True,
        "model.logistic",
    ),
    ModelSpec(
        "classification.forest",
        "Random Forest",
        TaskKind.CLASSIFICATION,
        classifier_forest,
        False,
        "model.classifier_forest",
    ),
    ModelSpec(
        "regression.linear",
        "Linear Regression",
        TaskKind.REGRESSION,
        linear,
        True,
        "model.linear",
    ),
    ModelSpec(
        "regression.forest",
        "Random Forest Regressor",
        TaskKind.REGRESSION,
        regressor_forest,
        False,
        "model.regressor_forest",
    ),
    ModelSpec(
        "clustering.kmeans",
        "K-Means",
        TaskKind.CLUSTERING,
        kmeans,
        True,
        "model.kmeans",
    ),
    ModelSpec("reduction.pca", "PCA", TaskKind.REDUCTION, pca, True, "model.pca"),
)


def model_spec(model_id: str) -> ModelSpec:
    for spec in MODELS:
        if spec.id == model_id:
            return spec
    raise ValueError("Unknown model ID")
