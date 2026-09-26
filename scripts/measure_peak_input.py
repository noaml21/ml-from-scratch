"""Peak supported input guard: time and memory at the documented dataset limits.

Generates a legal 20,000-row x 100-column CSV just under 20 MiB, then runs the
real headless workflow (owned worker children): load and infer, train both
classification models, predict a maximum 1,000-record batch and export a wheel.
Each operation must succeed within its coordinator-enforced deadline; results, including
peak child RSS, go to .mlforge-build/performance-<python>.json. This documents
one environment; it is not a universal speed claim.
"""

import asyncio
import json
import os
import platform
import resource
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from mlforge.application.service import Service
from mlforge.contracts import CandidateStatus, TaskKind
from mlforge.datasets.records import raw_records

ROOT = Path(__file__).resolve().parents[1]
ROWS, COLUMNS, LIMIT = 20_000, 100, 20 * 1024 * 1024
# Enforced by the coordinator: a breach fails the operation (asserted below).
DEADLINES = {
    "load": 30,
    "train": "120 per model, 300 per run",
    "predict": 30,
    "export": 60,
}


def dataset(path):
    rng = np.random.default_rng(42)
    signal = rng.normal(size=(ROWS, COLUMNS - 1)).round(3)
    score = signal[:, :5].sum(axis=1)
    labels = np.where(score > 1, "high", np.where(score < -1, "low", "mid"))
    header = ",".join(f"f{i:02d}" for i in range(COLUMNS - 1)) + ",label\n"
    with path.open("w") as stream:
        stream.write(header)
        for row, label in zip(signal, labels, strict=True):
            stream.write(",".join(f"{v:.3f}" for v in row) + f",{label}\n")
    size = path.stat().st_size
    assert size < LIMIT, f"Peak fixture exceeds the input limit: {size}"
    return size


async def measure(directory):
    source = directory / "peak.csv"
    size = dataset(source)
    timings = {}
    async with Service() as app:
        started = time.monotonic()
        assert await app.load(source), app.snapshot.failure
        timings["load"] = time.monotonic() - started
        state = app.snapshot
        assert len(state.dataset.rows) == ROWS
        assert len(state.dataset.columns) == COLUMNS
        app.confirm_schema()
        app.choose_task(TaskKind.CLASSIFICATION)
        ids = [c.id for c in state.dataset.columns]
        app.choose_target(ids[-1])
        app.choose_features(tuple(ids[:-1]))
        assert await app.review_configuration(), app.snapshot.failure
        app.acknowledge(tuple(w.code for w in app.snapshot.review.warnings))
        started = time.monotonic()
        assert await app.train(), app.snapshot.failure
        timings["train"] = time.monotonic() - started
        run = app.snapshot.run
        assert all(c.status == CandidateStatus.COMPLETED for c in run.candidates)
        assert len(run.candidates) == 2
        app.select_candidate(app.ranked_results[0].model_id)
        records = raw_records(
            app.snapshot.dataset, run.experiment.feature_ids, tuple(range(1000))
        )
        started = time.monotonic()
        prediction = await app.predict(records)
        timings["predict"] = time.monotonic() - started
        assert prediction is not None and len(prediction.data) == 1000
        started = time.monotonic()
        wheel = await app.export(directory / "exports", "peak_model", "1.0.0")
        timings["export"] = time.monotonic() - started
        assert wheel is not None, app.snapshot.failure
        wheel_size = Path(wheel).stat().st_size
        selected = app.ranked_results[0].model_id
    return {
        "rows": ROWS,
        "columns": COLUMNS,
        "csv_bytes": size,
        "selected_model": selected,
        "seconds": {k: round(v, 2) for k, v in timings.items()},
        "deadlines_seconds": DEADLINES,
        "peak_child_rss_mib": round(
            resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024, 1
        ),
        "parent_rss_mib": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1
        ),
        "wheel_bytes": wheel_size,
        "python": sys.version,
        "platform": platform.platform(),
        "cpus": os.cpu_count(),
        "status": "passed",
    }


def main():
    with tempfile.TemporaryDirectory(prefix="mlforge-peak-") as directory:
        result = asyncio.run(measure(Path(directory)))
    minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    report = ROOT / ".mlforge-build" / f"performance-{minor}.json"
    report.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Peak input guard passed: {json.dumps(result['seconds'])} -> {report}")


if __name__ == "__main__":
    main()
