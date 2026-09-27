"""Real application sessions configured from the canonical six-model fixtures."""

import csv

import pytest_asyncio

from mlforge.application.service import Service


@pytest_asyncio.fixture
async def trained_app(prepared_candidate, tmp_path):
    dataset, prepared, model = prepared_candidate
    source = tmp_path / "canonical.csv"
    with source.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(c.name for c in dataset.columns)
        writer.writerows([cell.raw_text for cell in row] for row in dataset.rows)
    async with Service() as app:
        assert await app.load(source)
        app.confirm_schema()
        app.choose_task(model.task)
        if model.task.supervised:
            app.choose_target(prepared.experiment.target_id)
        app.choose_features(prepared.experiment.feature_ids)
        app.choose_models((model.id,))
        app.choose_option(prepared.experiment.option)
        app.acknowledge(prepared.experiment.acknowledgements)
        assert await app.train(), app.snapshot.failure
        app.select_candidate(model.id)
        yield app
