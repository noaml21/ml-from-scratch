"""Build unfitted transforms; never learn shared state before splitting."""

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from mlforge.prediction.runtime import MISSING


def build_pipeline(fields: list[dict], estimator, *, scale_numeric: bool) -> Pipeline:
    """Each candidate receives fresh transform instances and its own estimator."""
    numbers = [index for index, field in enumerate(fields) if field["type"] == "Number"]
    categories = [
        index
        for index, field in enumerate(fields)
        if field["type"] in {"Category", "Boolean"}
    ]
    if len(numbers) + len(categories) != len(fields) or not fields:
        raise ValueError("Features must be Number, Category or Boolean")
    if len(numbers) + 32 * len(categories) > 512:
        raise ValueError("Choose fewer features or simplify categories")
    transforms = []
    if numbers:
        steps = [
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True))
        ]
        if scale_numeric:
            steps.append(("scaler", StandardScaler()))
        transforms.append(("number", Pipeline(steps), numbers))
    if categories:
        transforms.append(
            (
                "category",
                Pipeline(
                    [
                        (
                            "imputer",
                            SimpleImputer(
                                strategy="constant",
                                fill_value=MISSING,
                                keep_empty_features=True,
                            ),
                        ),
                        (
                            "encoder",
                            OneHotEncoder(
                                handle_unknown="ignore",
                                max_categories=32,
                                sparse_output=False,
                                drop=None,
                            ),
                        ),
                    ]
                ),
                categories,
            )
        )
    return Pipeline(
        [
            (
                "preprocessing",
                ColumnTransformer(transforms, remainder="drop", sparse_threshold=0),
            ),
            ("model", estimator),
        ]
    )
