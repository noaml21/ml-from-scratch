"""Configuration views over application-owned, worker-reviewed choices."""

import json

from rich.style import Style
from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.widgets import Button, Checkbox, OptionList, Static
from textual.widgets.option_list import Option

from mlforge.contracts import DomainError
from mlforge.datasets.records import visible_text
from mlforge.tui.help import CATALOG
from mlforge.tui.screens.shell import Action, Busy, Frame, operation_message


class Choices(OptionList):
    """A focus marker independent of checked state and terminal color."""

    def on_option_list_option_highlighted(self, event):
        for index in range(self.option_count):
            prompt = self.get_option_at_index(index).prompt
            text = prompt.copy() if isinstance(prompt, Text) else Text(str(prompt))
            if text.plain.startswith(("> ", "  ")):
                text = text[2:]
            text = Text("> " if index == event.option_index else "  ") + text
            self.replace_option_prompt_at_index(index, text)


class ConfigurationFrame(Frame):
    stage = "Goal"
    primary_id = "choices"

    def fail(self, message):
        self.query_one("#error", Static).update(f"Error: {message}")
        self.query_one(f"#{self.primary_id}").focus()

    def change(self, command, next_screen):
        def apply(discard):
            try:
                command(discard)
            except DomainError as error:
                self.fail(f"{error.message} {error.action}")
            else:
                self.review(next_screen)

        self.app.confirm_discard(apply)

    @work(group="configuration", exclusive=True)
    async def review(self, next_screen, *, preflight=False):
        busy = Busy("Checking current choices", heading="Reviewing configuration")
        busy.stage = "Goal"
        await self.app.push_screen(busy)
        try:
            accepted = await (
                self.app.service.preview_preprocessing()
                if preflight
                else self.app.service.review_configuration()
            )
            message = operation_message(
                self.app.service.snapshot, "Review stopped. Retry or go Back."
            )
        except DomainError as error:
            accepted = False
            message = f"{error.message} {error.action}"

        def finish():
            self.app.pop_screen()
            if accepted:
                if next_screen is None:
                    self.refresh_choices()
                else:
                    self.app.push_screen(next_screen())
            else:
                self.fail(message)

        self.app.after_modal(finish)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "back":
            self.app.action_back()


class Goal(ConfigurationFrame):
    heading = "What would you like to do?"
    help_topic = "goal"
    status = "Choose a goal · ?: suitability and examples"

    def content(self):
        state = self.app.service.snapshot
        yield Choices(
            *(Option(t.label, id=t.task.value) for t in self.app.service.tasks),
            id="choices",
            markup=False,
        )
        yield Static("", id="error", classes="error", markup=False)
        self.reasons = state.review.goal_reasons
        reasons = self.reasons
        if all(reasons):
            yield Static(
                "No available goal. Go Back to review types or choose another dataset.",
                classes="warning",
                markup=False,
            )

    def actions(self):
        yield Action("Back", id="back")

    def on_mount(self):
        self.query_one("#choices").focus()

    def context_help(self, focused):
        if not isinstance(focused, OptionList) or focused.highlighted is None:
            return None
        index = focused.highlighted
        task = self.app.service.tasks[index]
        reason = self.reasons[index]
        return task.label, CATALOG[task.task.value][1] + "\n\n" + (
            f"Unavailable: {reason}" if reason else "Available for this dataset."
        )

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted):
        reason = self.reasons[event.option_index]
        self.query_one("#error", Static).update(
            f"Unavailable: {reason}" if reason else ""
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        if reason := self.reasons[event.option_index]:
            self.fail(reason)
            return
        task = self.app.service.tasks[event.option_index].task
        self.change(
            lambda discard: self.app.service.choose_task(task, discard=discard),
            Target if task.supervised else Features,
        )


class Target(ConfigurationFrame):
    heading = "Choose what to predict"
    help_topic = "target"
    status = "Choose a target explicitly · ?: type, samples and suitability"

    def content(self):
        yield Choices(id="choices", markup=False)
        yield Checkbox("Show all columns", id="show-all")
        yield Static("", id="error", classes="error", markup=False)

    def actions(self):
        yield Action("Back", id="back")

    def on_mount(self):
        self.refresh_choices()
        self.query_one("#choices").focus()

    def refresh_choices(self):
        self.review_record = self.app.service.snapshot.review or self.review_record
        choices = self.review_record.targets
        show_all = self.query_one("#show-all", Checkbox).value
        self.shown = tuple(c for c in choices if show_all or c.default)
        listing = self.query_one("#choices", OptionList)
        listing.clear_options()
        listing.add_options(
            Option(
                Text(
                    visible_text(c.name) + (" — Unavailable" if not c.eligible else "")
                ),
                id=c.column_id,
            )
            for c in self.shown
        )
        if self.shown:
            listing.highlighted = 0
        if not self.shown:
            self.query_one("#error", Static).update(
                "No suggested targets. Show all columns or go Back to review types."
            )

    def on_checkbox_changed(self, event: Checkbox.Changed):
        self.refresh_choices()

    def context_help(self, focused):
        if not isinstance(focused, OptionList) or focused.highlighted is None:
            return None
        choice = self.shown[focused.highlighted]
        profile = self.app.service.snapshot.schema.profile(choice.column_id)
        return "Target details", (
            f"{visible_text(choice.name)}\nType: {profile.effective.value}\n"
            f"Unique: {profile.distinct_count} · Missing: {profile.missing_count}\n"
            f"Samples: {' · '.join(visible_text(v) for v in profile.samples)}\n"
            f"{choice.reason}\n\n{CATALOG['target'][1]}"
        )

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted):
        if event.option_index < len(self.shown):
            choice = self.shown[event.option_index]
            self.query_one("#error", Static).update(
                f"Unavailable: {choice.reason}" if not choice.eligible else ""
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        self.change(
            lambda discard: self.app.service.choose_target(
                event.option_id, discard=discard
            ),
            Features,
        )


class Features(ConfigurationFrame):
    BINDINGS = [Binding("space", "toggle", "Toggle")]
    heading = "Choose the information to use"
    help_topic = "features"
    status = "Space: toggle · ?: reasons and leakage notes"

    def check_action(self, action, parameters):
        if action == "toggle":
            return isinstance(self.focused, OptionList)
        return super().check_action(action, parameters)

    def content(self):
        yield Static("", id="count", markup=False)
        yield Choices(id="choices", markup=False)
        yield Static("", id="warnings", classes="warning", markup=False)
        yield Static("", id="error", classes="error", markup=False)

    def actions(self):
        yield Action("Continue", id="continue", variant="primary")
        yield Action("Back", id="back")

    def on_mount(self):
        self.refresh_choices()
        self.query_one("#choices").focus()

    def refresh_choices(self):
        state = self.app.service.snapshot
        self.review_record = state.review or self.review_record
        self.shown = self.review_record.features
        selected = state.configuration.feature_ids
        listing = self.query_one("#choices", OptionList)
        highlighted = listing.highlighted
        listing.clear_options()
        selected_style = listing.get_component_rich_style(
            "option-list--option-highlighted"
        )
        listing.add_options(
            Option(
                Text(
                    f"[{'x' if c.column_id in selected else ' '}] "
                    f"{visible_text(c.name)}"
                    + (" — Unavailable" if not c.eligible else ""),
                    style=Style(
                        color=selected_style.color, bgcolor=selected_style.bgcolor
                    )
                    if c.column_id in selected
                    else "",
                ),
                id=c.column_id,
            )
            for c in self.shown
        )
        if highlighted is not None:
            listing.highlighted = min(highlighted, len(self.shown) - 1)
        elif self.shown:
            listing.highlighted = 0
        self.query_one("#count", Static).update(f"{len(selected)} features selected")
        warnings = (
            self.review_record.warnings
            if self.review_record.selected_features == selected
            else ()
        )
        names = {c.id: visible_text(c.name) for c in state.dataset.columns}
        self.query_one("#warnings", Static).update(
            "\n".join(
                "Warning: "
                + (names[w.column_id] + ": " if w.column_id else "")
                + visible_text(w.message)
                for w in warnings
            )
        )
        button = self.query_one("#continue", Action)
        button.caption = (
            "Keep selected features and continue" if warnings else "Continue"
        )
        button.label = ("> " if button.has_focus else "  ") + button.caption
        self.query_one("#error", Static).update(
            "Choose at least one usable feature, or go Back to review types."
            if not selected
            else ""
        )

    def fail(self, message):
        self.refresh_choices()
        super().fail(message)

    def context_help(self, focused):
        if not isinstance(focused, OptionList) or focused.highlighted is None:
            return None
        choice = self.shown[focused.highlighted]
        return (
            "Feature details",
            f"{visible_text(choice.name)}\n{choice.reason}\n\n{CATALOG['features'][1]}",
        )

    def action_toggle(self):
        listing = self.query_one("#choices", OptionList)
        if not listing.has_focus or listing.highlighted is None:
            return
        choice = self.shown[listing.highlighted]
        if not choice.eligible:
            self.fail(choice.reason)
            return
        chosen = set(self.app.service.snapshot.configuration.feature_ids)
        chosen.symmetric_difference_update((choice.column_id,))
        ids = tuple(c.column_id for c in self.shown if c.column_id in chosen)
        self.change(
            lambda discard: self.app.service.choose_features(ids, discard=discard), None
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        self.action_toggle()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id != "continue":
            return super().on_button_pressed(event)
        state = self.app.service.snapshot
        if not state.configuration.feature_ids:
            self.fail("Choose at least one usable feature, or go Back.")
            return
        if self.review_record.selected_features != state.configuration.feature_ids:
            self.review(None)
            return
        try:
            self.app.service.acknowledge(
                tuple(w.code for w in self.review_record.warnings)
            )
        except DomainError as error:
            self.fail(f"{error.message} {error.action}")
            return
        self.review(Preprocessing, preflight=True)


class Preprocessing(ConfigurationFrame):
    heading = "Review automatic preprocessing"
    help_topic = "preprocessing"
    primary_id = "back"
    status = "These rules are applied independently to each candidate."

    def content(self):
        prepared = self.app.service.snapshot.prepared
        policy = json.loads(prepared.policy_json)
        yield Static(
            "Plan: fit on 80%; evaluate on 20%"
            if prepared.experiment.task.supervised
            else policy["scope"],
            markup=False,
        )
        yield Static(
            f"{len(prepared.train_rows)} training/exploration rows · "
            f"{len(prepared.test_rows)} holdout rows\n"
            f"Split: {policy['split']}\n\n"
            f"Missing numbers: {policy['numeric_missing']}\n"
            f"Categories: {policy['categorical']}\n"
            f"Scaling: {policy['scaling']}",
            markup=False,
        )
        if prepared.experiment.task.supervised:
            yield Static(
                "Warning: " + policy["split_caution"], classes="warning", markup=False
            )
        yield Static("No model has been fitted yet.", classes="muted", markup=False)
        yield Static("", id="error", classes="error", markup=False)

    def actions(self):
        yield Action("Back to features", id="back", variant="primary")

    def on_mount(self):
        self.query_one("#back").focus()
