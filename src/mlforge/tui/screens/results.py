"""Accepted result presentation; evaluation and selection remain application-owned."""

import json

from rich.style import Style
from rich.text import Text
from textual.widgets import Button, DataTable, Static

from mlforge.contracts import CandidateStatus, DomainError, TaskKind
from mlforge.datasets.records import visible_text
from mlforge.tui.help import CATALOG
from mlforge.tui.screens.shell import Action, Frame


def cell(value, width=18, *, numeric=False):
    text = Text(visible_text(str(value)), justify="right" if numeric else "left")
    text.truncate(width, overflow="ellipsis")
    if numeric:
        text.align("right", width)
    return text


def number(value):
    return "N/A" if value is None else format(value, ".6g")


def run_context(run):
    completed = sum(c.status == CandidateStatus.COMPLETED for c in run.candidates)
    failed = sum(c.status == CandidateStatus.FAILED for c in run.candidates)
    pending = len(run.experiment.model_ids) - len(run.candidates)
    return (
        f"Cancelled — {completed} models completed. " if run.cancelled else ""
    ) + f"{completed} completed · {failed} failed · {pending} not completed"


def scope(task, training_count, test_count):
    return (
        f"Trained on 80%; evaluated on 20% · {training_count} training / "
        f"{test_count} test rows"
        if task.supervised
        else f"Exploration on this dataset; no test split · {training_count} rows"
    )


def warning_text(code, state):
    if code.startswith("TRAIN_ALL_MISSING:"):
        column_id = code.split(":", 1)[1]
        name = next(c.name for c in state.dataset.columns if c.id == column_id)
        return (
            f"{visible_text(name)} was entirely missing in training; "
            "numeric imputation used zero. Holdout values were not used."
        )
    if code == "PCA_RANK_DEFICIENT":
        return (
            "Some retained components have near-zero variance; "
            "inspect component values."
        )
    if code.startswith("FIT_WARNING:"):
        return (
            "Fitting reported "
            + visible_text(code.split(":", 1)[1])
            + "; review diagnostics before using this model."
        )
    return visible_text(code)


class Results(Frame):
    stage = "Results"
    heading = "Review results"
    help_topic = "results"
    status = "Arrows: inspect cells · Enter: select completed model · ?: metric/details"

    def content(self):
        yield Static("", id="provenance", markup=False)
        yield Static("", id="run-context", markup=False)
        yield Static("", id="recommendation", markup=False)
        yield DataTable(id="results", cursor_type="cell", fixed_columns=3)
        yield Static("", id="failure-summary", classes="error", markup=False)
        yield Static("", id="diagnostic-summary", markup=False)
        yield Static("", id="row-detail", markup=False)
        yield Static("", id="error", classes="error", markup=False)

    def actions(self):
        yield Action("Select model", id="select-model", variant="primary")
        yield Action("Back to models", id="back")

    def on_mount(self):
        service = self.app.service
        run = service.snapshot.run
        self.run_id = run.id
        self.task_kind = run.experiment.task
        self.names = {model.id: model.name for model in service.models}
        self.metrics = service.primary_metrics
        self.candidates = {c.model_id: c for c in run.candidates}
        ranked_ids = tuple(c.model_id for c in service.ranked_results)
        self.shown = ranked_ids + tuple(
            m for m in run.experiment.model_ids if m not in ranked_ids
        )
        table = self.query_one("#results", DataTable)
        name_width = 24 if self.task_kind.supervised else 16
        for title, key, width in [
            ("", "marker", 5),
            ("Model", "model", name_width),
            ("Status", "status", 9),
        ]:
            table.add_column(Text(title), key=key, width=width)
        for metric in self.metrics:
            table.add_column(
                cell(metric.label, max(9, len(metric.label)), numeric=True),
                key=metric.key,
                width=max(9, len(metric.label)),
            )
        for model_id in self.shown:
            candidate = self.candidates.get(model_id)
            completed = candidate and candidate.status == CandidateStatus.COMPLETED
            values = {m.key: m for m in candidate.metrics} if completed else {}
            table.add_row(
                "",
                cell(self.names[model_id], name_width),
                "Completed"
                if completed
                else "Failed"
                if candidate
                else "Stopped"
                if run.cancelled
                else "Not run",
                *(
                    cell(
                        number(values[m.key].value) if m.key in values else "—",
                        max(9, len(m.label)),
                        numeric=True,
                    )
                    for m in self.metrics
                ),
                key=model_id,
            )
        prepared = service.snapshot.prepared
        self.query_one("#provenance", Static).update(
            scope(self.task_kind, len(prepared.train_rows), len(prepared.test_rows))
        )
        self.query_one("#run-context", Static).update(run_context(run))
        self.query_one("#failure-summary", Static).update(
            "\n".join(
                self.names[c.model_id]
                + ": Failed — "
                + visible_text(c.error_message or c.error_code or "Training failed.")
                for c in run.candidates
                if c.status == CandidateStatus.FAILED
            )
        )
        self.query_one("#failure-summary").display = any(
            c.status == CandidateStatus.FAILED for c in run.candidates
        )
        recommended = service.recommended
        if recommended:
            self.query_one("#recommendation", Static).update(
                f"{recommended[1]}: {self.names[recommended[0]]}"
            )
        if not self.task_kind.supervised and ranked_ids:
            diagnostics = json.loads(self.candidates[ranked_ids[0]].diagnostics_json)
            summary = (
                "Cluster sizes: "
                + ", ".join(
                    f"{key}: {value}"
                    for key, value in diagnostics["cluster_sizes"].items()
                )
                + ". IDs are arbitrary."
                if self.task_kind == TaskKind.CLUSTERING
                else f"{diagnostics['retained_components']} retained / "
                f"{diagnostics['original_features']} original features. "
                "Descriptive variance, not predictive accuracy."
            )
            self.query_one("#diagnostic-summary", Static).update(summary)
        table.move_cursor(column=1)
        table.focus()
        self.refresh_selection()

    def on_screen_resume(self):
        if hasattr(self, "shown"):
            self.call_after_refresh(self.refresh_selection)

    def refresh_selection(self):
        table = self.query_one("#results", DataTable)
        selected = self.app.service.snapshot.selected_model_id
        selected_style = table.get_component_rich_style("datatable--cursor")
        for index, model_id in enumerate(self.shown):
            table.update_cell(
                model_id,
                "marker",
                Text(
                    (">" if index == table.cursor_row else " ")
                    + (" [x]" if model_id == selected else " [ ]")
                ),
            )
            for key in ("model", "status", *(m.key for m in self.metrics)):
                previous = table.get_cell(model_id, key)
                styled = (
                    previous.copy() if isinstance(previous, Text) else Text(previous)
                )
                styled.style = (
                    Style(color=selected_style.color, bgcolor=selected_style.bgcolor)
                    if model_id == selected
                    else ""
                )
                table.update_cell(model_id, key, styled)
        self.show_row()

    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted):
        if hasattr(self, "shown"):
            self.refresh_selection()

    def show_row(self):
        candidate = self.candidates.get(
            self.shown[self.query_one("#results", DataTable).cursor_row]
        )
        messages = []
        if candidate is None:
            messages.append(
                "Unavailable: this model did not complete. Go Back to retry."
            )
        elif candidate.status == CandidateStatus.FAILED:
            messages.append(
                "Unavailable: "
                + (
                    candidate.error_message
                    or candidate.error_code
                    or "Training failed."
                )
                + " Use ? for details or go Back to retry."
            )
        else:
            messages.extend(
                f"N/A: {m.reason}" for m in candidate.metrics if m.value is None
            )
            messages.extend(
                "Warning: " + warning_text(w, self.app.service.snapshot)
                for w in candidate.warnings
            )
        self.query_one("#row-detail", Static).update(visible_text("\n".join(messages)))

    def context_help(self, focused):
        if not isinstance(focused, DataTable):
            return None
        model_id = self.shown[focused.cursor_row]
        candidate = self.candidates.get(model_id)
        if focused.cursor_column >= 3:
            metric = self.metrics[focused.cursor_column - 3]
            value = (
                next((m for m in candidate.metrics if m.key == metric.key), None)
                if candidate
                else None
            )
            title, explanation = CATALOG[f"metric.{metric.key}"]
            actual = (
                str(value.value)
                if value and value.value is not None
                else "N/A: "
                + (value.reason if value else "No completed metric for this model.")
            )
            return title, explanation + "\n\n" + self.names[
                model_id
            ] + ": " + visible_text(actual)
        return self.names[model_id], (
            visible_text(
                candidate.error_message
                or candidate.error_code
                or "Completed; select to inspect the exact evaluated model."
            )
            if candidate
            else "This candidate did not complete. Go Back to retry."
        )

    def select(self):
        model_id = self.shown[self.query_one("#results", DataTable).cursor_row]
        try:
            self.app.service.select_candidate(model_id, run_id=self.run_id)
        except DomainError as error:
            self.query_one("#error", Static).update(
                f"Error: {error.message} {error.action}"
            )
            self.query_one("#results").focus()
        else:
            self.app.push_screen(SelectedModel(self.run_id))

    def on_data_table_cell_selected(self, event: DataTable.CellSelected):
        self.select()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "select-model":
            self.select()
        else:
            self.app.action_back()


class SelectedModel(Frame):
    stage = "Results"
    heading = "Selected model"
    help_topic = "selected-model"
    status = "The exact evaluated model is retained; selection does not refit it."

    def __init__(self, run_id):
        super().__init__()
        self.run_id = run_id

    def content(self):
        state = self.app.service.snapshot
        candidate = state.selected
        self.model_id = candidate.model_id
        metadata = json.loads(candidate.bundle.metadata_json)
        name = next(
            m.name for m in self.app.service.models if m.id == candidate.model_id
        )
        task = candidate.bundle.task
        yield Static(name, id="model-name", markup=False)
        yield Static(
            next(t.label for t in self.app.service.tasks if t.task == task),
            markup=False,
        )
        yield Static(
            scope(task, metadata["training_count"], metadata["test_count"]),
            id="provenance",
            markup=False,
        )
        yield Static(run_context(state.run), id="run-context", markup=False)
        yield Static(
            f"Seed {metadata['seed']} · Exact evaluated pipeline; no full-data refit",
            classes="muted",
            markup=False,
        )
        yield Static(
            "\n".join("Warning: " + warning_text(w, state) for w in candidate.warnings),
            classes="warning",
            markup=False,
        )
        yield Static("", id="error", classes="error", markup=False)

    def actions(self):
        yield Action("Inspect details", id="inspect", variant="primary")
        yield Action("Back to results", id="back")

    def on_mount(self):
        self.query_one("#inspect").focus()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id != "inspect":
            self.app.action_back()
            return
        try:
            self.app.service.select_candidate(self.model_id, run_id=self.run_id)
        except DomainError as error:
            self.query_one("#error", Static).update(
                f"Error: {error.message} {error.action}"
            )
        else:
            self.app.push_screen(Inspection())


class Inspection(Frame):
    stage = "Results"
    heading = "Inspect model details"
    help_topic = "inspection"
    status = (
        "Tab: tables · Arrows: cells · ?: complete literal value · Back: selected model"
    )

    def content(self):
        candidate = self.app.service.snapshot.selected
        self.task_kind = candidate.bundle.task
        self.diagnostics = json.loads(candidate.diagnostics_json)
        self.metrics = {m.key: m for m in candidate.metrics}
        self.tables = {}
        d = self.diagnostics
        if self.task_kind == TaskKind.CLASSIFICATION:
            yield Static(
                "Confusion matrix · true rows / predicted columns", markup=False
            )
            self.tables["confusion"] = (
                ["True / predicted", *d["labels"]],
                [
                    (label, *row)
                    for label, row in zip(
                        d["labels"], d["confusion_matrix"], strict=True
                    )
                ],
            )
            yield DataTable(id="confusion", fixed_columns=1)
            yield Static("Per-class diagnostics", markup=False)
            self.tables["per-class"] = (
                ["Class", "Precision", "Recall", "F1", "Support", "Train", "Test"],
                [
                    (
                        r["label"],
                        r["precision"],
                        r["recall"],
                        r["f1"],
                        r["support"],
                        d["train_class_counts"][r["label"]],
                        d["test_class_counts"][r["label"]],
                    )
                    for r in d["per_class"]
                ],
            )
            yield DataTable(id="per-class", fixed_columns=1)
            baseline = d["baseline"]
            yield Static(
                f"Training-majority baseline: {visible_text(baseline['label'])}\n"
                f"Accuracy {number(baseline['accuracy'])} · "
                f"Macro F1 {number(baseline['macro_f1'])}",
                markup=False,
            )
        elif self.task_kind == TaskKind.REGRESSION:
            r = d["residuals"]
            self.tables["residuals"] = (
                ["Diagnostic", "Value"],
                [
                    ("RMSE", self.metrics["rmse"].value),
                    *[(f"Residual {key}", value) for key, value in r.items()],
                    ("Training target mean", d["baseline_mean"]),
                    *[
                        (f"Baseline {key.upper()}", value)
                        for key, value in d["baseline"].items()
                    ],
                ],
            )
            yield Static(
                "Residual = observed − predicted · baseline predicts training mean",
                markup=False,
            )
            yield DataTable(id="residuals", fixed_columns=1)
            reason = self.metrics["r2"].reason
            if reason:
                yield Static("N/A: " + visible_text(reason), markup=False)
        elif self.task_kind == TaskKind.CLUSTERING:
            yield Static(
                "Cluster IDs are arbitrary. Centers are in standardized feature space.",
                markup=False,
            )
            self.tables["centers"] = (
                [
                    "Cluster",
                    "Size",
                    *[f"Feature {i + 1}" for i in range(len(d["centers"][0]))],
                ],
                [
                    (str(i), d["cluster_sizes"].get(str(i), 0), *center)
                    for i, center in enumerate(d["centers"])
                ],
            )
            yield DataTable(id="centers", fixed_columns=2)
            yield Static(
                f"Inertia {number(d['inertia'])} · Iterations {d['iterations']} · "
                f"Actual clusters {d['actual_clusters']}",
                markup=False,
            )
            yield Static(
                f"Silhouette: {number(self.metrics['silhouette'].value)} · "
                + (
                    "Deterministic sample"
                    if d["silhouette_sampled"]
                    else "All observations"
                )
                + f" ({d['silhouette_rows']} rows; seed 42)",
                markup=False,
            )
            if self.metrics["silhouette"].reason:
                yield Static(
                    "N/A: " + visible_text(self.metrics["silhouette"].reason),
                    markup=False,
                )
            prepared = self.app.service.snapshot.prepared
            names = prepared.experiment.feature_ids
            # Use confirmed column names, in the exact prepared feature order.
            dataset = self.app.service.snapshot.dataset
            by_id = {c.id: c.name for c in dataset.columns}
            yield Static(
                "Feature order: " + ", ".join(visible_text(by_id[i]) for i in names),
                markup=False,
            )
        else:
            yield Static(
                "Retained variance "
                f"{number(self.metrics['retained_variance'].value)} · "
                f"{d['retained_components']} retained / "
                f"{d['original_features']} original features",
                markup=False,
            )
            self.tables["components"] = (
                ["Component", "Variance", "Variance ratio"],
                [
                    (r["component"], r["variance"], r["variance_ratio"])
                    for r in d["per_component"]
                ],
            )
            yield DataTable(id="components", fixed_columns=1)
            yield Static(
                f"Reconstruction MSE: {number(d['reconstruction_mse'])}\n"
                "Standardized feature space; descriptive variance, "
                "not predictive accuracy.",
                markup=False,
            )

    def actions(self):
        yield Action("Back to selected model", id="back", variant="primary")

    def on_mount(self):
        for identifier, (headers, rows) in self.tables.items():
            table = self.query_one(f"#{identifier}", DataTable)
            widths = [
                min(24 if i == 0 else 16, max(8, Text(str(header)).cell_len))
                for i, header in enumerate(headers)
            ]
            if identifier == "residuals":
                widths[0] = 24
            for index, header in enumerate(headers):
                numeric = all(
                    isinstance(row[index], (int, float)) or row[index] is None
                    for row in rows
                )
                table.add_column(
                    cell(header, widths[index], numeric=numeric), width=widths[index]
                )
            for row in rows:
                table.add_row(
                    *(
                        cell(
                            number(value)
                            if isinstance(value, float)
                            else "N/A"
                            if value is None
                            else value,
                            widths[i],
                            numeric=isinstance(value, (int, float)),
                        )
                        for i, value in enumerate(row)
                    )
                )
        self.query_one(DataTable).focus()

    def context_help(self, focused):
        if not isinstance(focused, DataTable):
            return None
        headers, rows = self.tables[focused.id]
        value = rows[focused.cursor_row][focused.cursor_column]
        return visible_text(str(headers[focused.cursor_column])), visible_text(
            "N/A: metric is undefined for this test target."
            if value is None
            else str(value)
        )

    def on_button_pressed(self, event: Button.Pressed):
        self.app.action_back()
