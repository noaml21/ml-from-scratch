"""Real service configuration journeys; no mocked domain choices or fitting."""

import asyncio
from pathlib import Path

import pytest
from textual.widgets import Input, OptionList, Static

from mlforge.application.service import Service
from mlforge.contracts import DomainError, TaskKind
from mlforge.tui.app import MLForgeApp
from mlforge.tui.screens.configuration import (
    Features,
    Goal,
    Models,
    Preprocessing,
    Target,
)
from mlforge.tui.screens.preview import Preview
from mlforge.tui.screens.shell import Help, ResizeGuard


async def until(predicate):
    async with asyncio.timeout(30):
        while not predicate():
            await asyncio.sleep(0.02)


async def activate(app, pilot, button):
    app.screen.query_one(f"#{button}").focus()
    await pilot.press("enter")


@pytest.mark.parametrize("task", list(TaskKind))
async def test_four_goal_journeys_use_real_review_and_preflight(task):
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        example = next(e for e in app.service.examples if e.task == task)
        assert await app.service.load_example(example.filename)
        await app.push_screen(Preview())
        await activate(app, pilot, "correct")
        await until(lambda: isinstance(app.screen, Goal))
        await pilot.pause()
        goals = app.screen.query_one("#choices", OptionList)
        assert app.focused is goals and app.service.snapshot.configuration.task is None
        goals.highlighted = list(TaskKind).index(task)
        await pilot.press("question_mark")
        assert isinstance(app.screen, Help)
        await pilot.press("escape")
        assert app.focused is goals and goals.highlighted == list(TaskKind).index(task)
        await pilot.press("enter")
        await until(
            lambda: isinstance(app.screen, Target if task.supervised else Features)
        )
        await pilot.pause()
        if task.supervised:
            assert app.service.snapshot.configuration.target_id is None
            target_screen = app.screen
            await pilot.press("question_mark")
            assert (
                "Unique:" in app.screen.body_text and "Samples:" in app.screen.body_text
            )
            await pilot.press("escape", "enter")
            await until(lambda: isinstance(app.screen, Features))
            await pilot.pause()
            assert app.service.snapshot.configuration.target_id is not None
            assert target_screen in app.screen_stack
        else:
            assert all(not isinstance(s, Target) for s in app.screen_stack)
        owner = app.screen
        chosen = app.service.snapshot.configuration.feature_ids
        assert chosen
        listing = owner.query_one("#choices", OptionList)
        eligible = next(i for i, c in enumerate(owner.shown) if c.eligible)
        listing.highlighted = eligible
        await pilot.press("space")
        await until(lambda: app.screen is owner)
        await pilot.pause()
        changed = app.service.snapshot.configuration.feature_ids
        assert changed != chosen and listing.highlighted == eligible
        await pilot.press("space")
        await until(lambda: app.screen is owner)
        await pilot.pause()
        assert app.service.snapshot.configuration.feature_ids == chosen
        await pilot.press("question_mark")
        assert isinstance(app.screen, Help)
        await pilot.press("escape")
        assert app.focused is listing and listing.highlighted == eligible
        for size in [(79, 23), (100, 30), (140, 40), (80, 24)]:
            await pilot.resize_terminal(*size)
            await pilot.pause()
            assert (
                isinstance(app.screen, ResizeGuard)
                if size[0] < 80
                else app.screen is owner
            )
        assert app.service.snapshot.configuration.feature_ids == chosen
        await activate(app, pilot, "continue")
        await until(lambda: isinstance(app.screen, Preprocessing))
        await pilot.pause()
        prepared = app.service.snapshot.prepared
        assert prepared and app.service.snapshot.run is None
        assert bool(prepared.test_rows) == task.supervised
        await pilot.press("escape")
        assert app.screen is owner
        assert app.service.snapshot.configuration.feature_ids == chosen
        await activate(app, pilot, "continue")
        await until(lambda: isinstance(app.screen, Preprocessing))
        assert app.service.snapshot.prepared == prepared
        await activate(app, pilot, "continue")
        assert isinstance(app.screen, Models)
        assert len(app.screen.shown) == (2 if task.supervised else 1)
        assert app.service.snapshot.run is None
        await pilot.press("escape")
        assert isinstance(app.screen, Preprocessing)
    assert not app.service._coordinator.root.exists()


async def test_invalid_goal_and_no_features_explain_recovery(tmp_path):
    source = tmp_path / "tiny.csv"
    source.write_text("x\n1\n")
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        assert await app.service.load(source)
        await app.push_screen(Preview())
        await activate(app, pilot, "correct")
        await until(lambda: isinstance(app.screen, Goal))
        await pilot.pause()
        await pilot.press("enter")
        assert isinstance(app.screen, Goal)
        assert "Error:" in str(app.screen.query_one("#error", Static).content)
        assert app.service.snapshot.configuration.task is None
        await pilot.press("escape")
        assert isinstance(app.screen, Preview)
        assert not app.screen.query_one("#correct").disabled


@pytest.mark.parametrize("monochrome", [False, True])
async def test_warnings_show_all_and_visual_evidence(tmp_path, monkeypatch, monochrome):
    from pathlib import Path

    from textual.widgets import Checkbox

    if monochrome:
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.delenv("NO_COLOR", raising=False)
    destination = Path(".mlforge-build/p07-configuration")
    destination.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "synthetic.csv"
    source.write_text(
        "x,outcome,target,empty\n"
        + "".join(f"{i},{i % 2},{i % 2},\n" for i in range(40))
    )
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:

        async def capture(name):
            for size in [(80, 24), (100, 30), (140, 40)]:
                await pilot.resize_terminal(*size)
                await pilot.pause()
                app.save_screenshot(
                    f"{name}-{size[0]}-{'mono' if monochrome else 'color'}.svg",
                    path=str(destination),
                )
            await pilot.resize_terminal(80, 24)
            await pilot.pause()

        assert await app.service.load(source)
        await app.push_screen(Preview())
        await activate(app, pilot, "correct")
        await until(lambda: isinstance(app.screen, Goal))
        await pilot.pause()
        await capture("goal")
        await pilot.press("enter")
        await until(lambda: isinstance(app.screen, Target))
        await pilot.pause()
        listing = app.screen.query_one("#choices", OptionList)
        assert listing.highlighted == 0
        assert app.service.snapshot.configuration.target_id is None
        app.screen.query_one("#show-all", Checkbox).focus()
        await pilot.press("space")
        await pilot.pause()
        assert len(app.screen.shown) == 4
        listing.focus()
        listing.highlighted = next(
            i for i, c in enumerate(app.screen.shown) if c.column_id == "c3"
        )
        await pilot.press("enter")
        assert "Error:" in str(app.screen.query_one("#error", Static).content)
        assert app.service.snapshot.configuration.target_id is None
        listing.highlighted = next(
            i for i, c in enumerate(app.screen.shown) if c.column_id == "c2"
        )
        await capture("target")
        await pilot.press("enter")
        await until(lambda: isinstance(app.screen, Features))
        await pilot.pause()
        owner = app.screen
        assert app.service.snapshot.configuration.acknowledgements == ()
        assert "Warning: outcome:" in str(owner.query_one("#warnings", Static).content)
        assert "Keep selected features" in str(owner.query_one("#continue").label)
        await capture("features-warnings")
        await activate(app, pilot, "continue")
        await until(lambda: isinstance(app.screen, Preprocessing))
        await pilot.pause()
        assert "EQUAL_TARGET:c1" in app.service.snapshot.configuration.acknowledgements
        assert app.service.snapshot.run is None
        await capture("preprocessing")
        await pilot.press("question_mark")
        assert isinstance(app.screen, Help)
        await capture("preprocessing-help")
        await pilot.press("escape", "escape")
        assert app.screen is owner
        await activate(app, pilot, "continue")
        await until(lambda: isinstance(app.screen, Preprocessing))
        await pilot.press("escape")
        listing = owner.query_one("#choices", OptionList)
        listing.highlighted = 1
        listing.focus()
        await pilot.press("space")
        await until(lambda: app.screen is owner)
        await pilot.pause()
        assert not app.service.snapshot.configuration.acknowledgements
        assert not app.service.snapshot.review.warnings


async def test_interrupted_feature_review_preserves_choices_and_can_retry(monkeypatch):
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        assert await app.service.load_example("clustering.csv")
        app.service.confirm_schema()
        app.service.choose_task("clustering")
        assert await app.service.review_configuration()
        await app.push_screen(Features())
        await pilot.pause()
        owner = app.screen
        listing = owner.query_one("#choices", OptionList)
        listing.highlighted = next(i for i, c in enumerate(owner.shown) if c.eligible)
        before = app.service.snapshot.configuration.feature_ids
        original = app.service.review_configuration

        async def stopped():
            return False

        monkeypatch.setattr(app.service, "review_configuration", stopped)
        await pilot.press("space")
        await until(lambda: app.screen is owner)
        await pilot.pause()
        changed = app.service.snapshot.configuration.feature_ids
        assert changed != before and changed
        assert "Review stopped" in str(owner.query_one("#error", Static).content)
        for choice, option in zip(owner.shown, range(listing.option_count)):
            prompt = str(listing.get_option_at_index(option).prompt)
            assert ("[x]" in prompt) == (choice.column_id in changed)
        monkeypatch.setattr(app.service, "review_configuration", original)
        await activate(app, pilot, "continue")
        await until(
            lambda: app.screen is owner and app.service.snapshot.review is not None
        )
        await pilot.pause()
        assert app.service.snapshot.prepared is None
        await activate(app, pilot, "continue")
        await until(lambda: isinstance(app.screen, Preprocessing))
        assert app.service.snapshot.prepared.experiment.feature_ids == changed


@pytest.mark.parametrize("task", list(TaskKind))
@pytest.mark.parametrize("monochrome", [False, True])
async def test_models_state_options_help_and_visuals(task, monochrome, monkeypatch):
    if monochrome:
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.delenv("NO_COLOR", raising=False)
    destination = Path(".mlforge-build/p07-models")
    destination.mkdir(parents=True, exist_ok=True)
    app = MLForgeApp(Service())
    async with app.run_test(size=(80, 24)) as pilot:
        example = next(e for e in app.service.examples if e.task == task)
        assert await app.service.load_example(example.filename)
        app.service.confirm_schema()
        app.service.choose_task(task)
        assert await app.service.review_configuration()
        if task.supervised:
            app.service.choose_target(
                next(
                    c.column_id
                    for c in app.service.snapshot.review.targets
                    if c.default
                )
            )
            assert await app.service.review_configuration()
        app.service.acknowledge(
            tuple(w.code for w in app.service.snapshot.review.warnings)
        )
        assert await app.service.preview_preprocessing()
        await app.push_screen(Preprocessing())
        await activate(app, pilot, "continue")
        assert isinstance(app.screen, Models)
        owner = app.screen
        listing = owner.query_one("#choices", OptionList)
        assert app.focused is listing
        defaults = app.service.snapshot.configuration.model_ids
        assert len(defaults) == (2 if task.supervised else 1)
        await pilot.press("question_mark")
        assert isinstance(app.screen, Help)
        await pilot.press("escape")
        assert app.focused is listing
        if task.supervised:
            await pilot.press("space")
            assert app.service.snapshot.configuration.model_ids == (defaults[1],)
            await pilot.press("down", "space")
            assert app.service.snapshot.configuration.model_ids == ()
            assert "at least one" in str(
                owner.query_one("#selection-note", Static).content
            )
            await activate(app, pilot, "train")
            assert "at least one" in str(owner.query_one("#error", Static).content)
            assert app.focused is listing
            with pytest.raises(DomainError):
                await app.service.train()
            assert app.service.snapshot.run is None
            await pilot.press("escape")
            assert isinstance(app.screen, Preprocessing)
            await activate(app, pilot, "continue")
            owner = app.screen
            listing = owner.query_one("#choices", OptionList)
            assert app.service.snapshot.configuration.model_ids == ()
            await pilot.press("space")
            assert app.service.snapshot.configuration.model_ids == (defaults[0],)
        else:
            bounds = app.service.model_option_bounds
            config = app.service.snapshot.configuration
            assert config.option == bounds[2]
            field = owner.query_one("#option", Input)
            field.focus()
            for value in ["", "3.5", str(bounds[0] - 1), str(bounds[1] + 1), "bq?"]:
                field.value = value
                await pilot.press("enter")
                assert app.service.snapshot.configuration == config
                assert app.focused is field and field.value == value
                assert "Error:" in str(owner.query_one("#error", Static).content)
                await activate(app, pilot, "train")
                assert app.service.snapshot.run is None and app.focused is field
            await pilot.press("f1")
            assert isinstance(app.screen, Help)
            await pilot.press("escape")
            assert app.focused is field and field.value == "bq?"
            field.value = str(bounds[0])
            await pilot.press("enter")
            assert app.service.snapshot.configuration.option == bounds[0]
            await pilot.press("escape", "escape")
            assert isinstance(app.screen, Preprocessing)
            await activate(app, pilot, "continue")
            owner = app.screen
            listing = owner.query_one("#choices", OptionList)
            assert owner.query_one("#option", Input).value == str(bounds[0])
            assert app.service.snapshot.configuration.model_ids == defaults
        config = app.service.snapshot.configuration
        focused = app.focused
        for size in [(80, 24), (100, 30), (79, 23), (140, 40), (80, 24)]:
            await pilot.resize_terminal(*size)
            await pilot.pause()
            if size[0] < 80:
                assert isinstance(app.screen, ResizeGuard)
            else:
                assert app.screen is owner and app.focused is focused
                app.save_screenshot(
                    f"{task}-{size[0]}-{'mono' if monochrome else 'color'}.svg",
                    path=str(destination),
                )
        assert app.service.snapshot.configuration == config
        assert app.service.snapshot.run is None
        await pilot.press("escape")
        await activate(app, pilot, "continue")
        assert app.service.snapshot.configuration == config
