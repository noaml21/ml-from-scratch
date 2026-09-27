"""Regenerate the documentation screenshots from the real application.

python scripts/capture_screenshots.py

Uses the packaged synthetic mixed-type example, real child-process training and
the actual Textual renderer; writes SVGs to docs/assets/. Presentation only.
"""

import asyncio
import os
from importlib.resources import as_file, files
from pathlib import Path

from mlforge.application.service import Service
from mlforge.contracts import TaskKind
from mlforge.tui.app import MLForgeApp
from mlforge.tui.screens.results import Results, SelectedModel
from mlforge.tui.screens.trial import Trial

ASSETS = Path(__file__).resolve().parents[1] / "docs/assets"
SIZE = (100, 30)


async def until(predicate):
    async with asyncio.timeout(120):
        while not predicate():
            await asyncio.sleep(0.05)


async def focus_and_press(app, pilot, identifier):
    for _ in range(30):
        if app.focused is not None and app.focused.id == identifier:
            await until(lambda: not app.focused.has_class("-active"))
            await pilot.press("enter")
            return
        await pilot.press("tab")
    raise AssertionError(f"Unreachable action: {identifier}")


async def trained(app, pilot, example, task, target):
    service = app.service
    with as_file(files("mlforge").joinpath("examples", example)) as source:
        assert await service.load(source)
    service.confirm_schema()
    service.choose_task(task)
    columns = {c.name: c.id for c in service.snapshot.dataset.columns}
    service.choose_target(columns[target])
    assert await service.review_configuration()
    service.acknowledge(tuple(w.code for w in service.snapshot.review.warnings))
    assert await service.train(), service.snapshot.failure
    await app.push_screen(Results())
    await pilot.pause()


async def capture():
    os.environ.pop("NO_COLOR", None)
    ASSETS.mkdir(parents=True, exist_ok=True)
    app = MLForgeApp(Service())
    async with app.run_test(size=SIZE) as pilot:
        await trained(app, pilot, "regression.tsv", TaskKind.REGRESSION, "response")
        app.save_screenshot("results.svg", path=str(ASSETS))

    app = MLForgeApp(Service())
    async with app.run_test(size=SIZE) as pilot:
        await trained(app, pilot, "mixed.csv", TaskKind.CLASSIFICATION, "outcome")
        await pilot.press("enter")
        await until(lambda: isinstance(app.screen, SelectedModel))
        await focus_and_press(app, pilot, "try")
        await until(lambda: isinstance(app.screen, Trial))
        await pilot.pause()
        trial = app.screen
        for index, field in enumerate(trial.fields):
            control = trial.query_one(f"#value-{index}")
            if field.kind == "Boolean":
                control.value = "true"
            elif field.kind == "Category":
                control.value = field.categories[0]
            else:  # One ordinary value and one outside the training range.
                control.value = "31" if index == 0 else "250000"
        attempts = trial.attempts
        await focus_and_press(app, pilot, "predict")
        await until(lambda: trial.attempts == attempts + 1)
        await pilot.pause()
        app.save_screenshot("try.svg", path=str(ASSETS))


if __name__ == "__main__":
    asyncio.run(capture())
    print(f"Screenshots written to {ASSETS}")
