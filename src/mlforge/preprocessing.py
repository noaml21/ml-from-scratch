"""Prepare one immutable split and fresh transforms; never learn shared fit state."""

import json

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from mlforge.contracts import DomainError, ExperimentSpec, PreparedRun, TaskKind
from mlforge.datasets.records import Schema, TabularDataset
from mlforge.prediction.runtime import (
    MISSING,
    InputValidationError,
    environment,
    normalize_record,
)
from mlforge.tasks import target_values, validate_selection

MAX_FEATURES = 512
MAX_MATRIX_BYTES = 128 * 1024 * 1024


def input_fields(
    dataset: TabularDataset, schema: Schema, feature_ids: tuple[str, ...]
) -> list[dict]:
    columns = {column.id: column for column in dataset.columns}
    return [
        {
            "name": columns[column_id].name,
            "type": schema.profile(column_id).effective.value,
        }
        for column_id in feature_ids
    ]


def raw_records(
    dataset: TabularDataset, feature_ids: tuple[str, ...], rows: tuple[int, ...]
) -> list[dict]:
    indices = {column.id: index for index, column in enumerate(dataset.columns)}
    chosen = [indices[column_id] for column_id in feature_ids]
    return [
        {
            dataset.columns[index].name: None
            if dataset.rows[row][index].missing
            else dataset.rows[row][index].raw_text
            for index in chosen
        }
        for row in rows
    ]


def matrix_limit(rows: int, fields: list[dict]) -> int:
    maximum = sum(1 if field["type"] == "Number" else 32 for field in fields)
    if not 1 <= maximum <= MAX_FEATURES or rows * maximum * 8 > MAX_MATRIX_BYTES:
        raise DomainError(
            "MATRIX_LIMIT",
            "The transformed table exceeds 512 features or 128 MiB.",
            "Choose fewer features or simplify categories.",
        )
    return maximum


def input_matrix(
    dataset: TabularDataset,
    schema: Schema,
    feature_ids: tuple[str, ...],
    rows: tuple[int, ...],
) -> np.ndarray:
    fields = input_fields(dataset, schema, feature_ids)
    matrix_limit(len(rows), fields)
    try:
        return np.asarray(
            [
                normalize_record(row, fields)[0]
                for row in raw_records(dataset, feature_ids, rows)
            ],
            dtype=object,
        )
    except InputValidationError:
        raise DomainError(
            "INPUT_SCHEMA",
            "Input values do not match the confirmed schema.",
            "Return to Preview and review column types.",
        ) from None


def prepare_run(
    dataset: TabularDataset, schema: Schema, experiment: ExperimentSpec
) -> PreparedRun:
    """Split row IDs before any fitting. Every candidate consumes this same plan."""
    if experiment.dataset_fingerprint != dataset.fingerprint or [
        p.column_id for p in schema.columns
    ] != [c.id for c in dataset.columns]:
        raise DomainError(
            "STALE_DATA",
            "Dataset and schema no longer match this experiment.",
            "Confirm the current dataset and configuration again.",
        )
    warnings = validate_selection(dataset, schema, experiment)
    fields = input_fields(dataset, schema, experiment.feature_ids)
    maximum = matrix_limit(len(dataset.rows), fields)
    rows = tuple(range(len(dataset.rows)))
    if experiment.task.supervised:
        labels = target_values(dataset, schema, experiment.target_id, experiment.task)
        try:
            train, test = train_test_split(
                rows,
                test_size=(len(rows) + 4) // 5,
                random_state=experiment.seed,
                stratify=labels if experiment.task == TaskKind.CLASSIFICATION else None,
            )
        except ValueError:
            raise DomainError(
                "SPLIT",
                "Cannot put the required classes in both partitions.",
                "Choose another target or dataset.",
            ) from None
        train, test = tuple(int(i) for i in train), tuple(int(i) for i in test)
        if (
            len(train) + len(test) != len(rows)
            or set(train) & set(test)
            or set(train) | set(test) != set(rows)
            or len(set(train)) != len(train)
            or len(set(test)) != len(test)
        ):
            raise DomainError(
                "SPLIT",
                "The split did not preserve every row exactly once.",
                "Retry preparation.",
            )
        if experiment.task == TaskKind.CLASSIFICATION and (
            {labels[i] for i in train} != set(labels)
            or {labels[i] for i in test} != set(labels)
        ):
            raise DomainError(
                "SPLIT",
                "Every class must appear in train and test.",
                "Choose another target or dataset.",
            )
    else:
        train, test = rows, ()
    # This is stateless validation, never fit or fit_transform on either partition.
    input_matrix(dataset, schema, experiment.feature_ids, rows)
    policy = {
        "fields": fields,
        "maximum_transformed_features": maximum,
        "numeric_missing": "training median; zero if entirely missing in training",
        "categorical": "constant missing marker; "
        "one-hot encoding capped at 32 categories",
        "scaling": "model-specific; fitted independently on permitted rows",
        "split": "80/20 stratified holdout"
        if experiment.task == TaskKind.CLASSIFICATION
        else "80/20 shuffled holdout"
        if experiment.task.supervised
        else "all-row exploration",
        "scope": "Trained on 80%; evaluated on 20%"
        if test
        else "Exploration on this dataset; no test split",
        "warning_codes": [warning.code for warning in warnings],
        "split_caution": "Random splits can be optimistic "
        "for time-ordered or grouped observations.",
    }
    return PreparedRun(
        experiment,
        schema,
        train,
        test,
        json.dumps(policy, sort_keys=True),
        json.dumps(environment(), sort_keys=True),
    )


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
