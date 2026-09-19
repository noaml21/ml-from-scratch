"""Reproduce committed synthetic examples using fixed integer formulas, no inputs."""

import csv
import io
import json
from pathlib import Path


def delimited(headers, rows, delimiter=","):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=delimiter, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue()


def examples() -> dict[str, str]:
    classification = [
        (
            round((i % 2) * 4 + ((i * 7) % 13) / 10, 2),
            round(((i * 11) % 17) / 10, 2),
            "on" if i % 2 else "off",
        )
        for i in range(80)
    ]
    regression = [
        (
            i % 20,
            (i * 7) % 11,
            round(3.2 * (i % 20) - 1.7 * ((i * 7) % 11) + ((i % 5) - 2) / 10, 2),
        )
        for i in range(80)
    ]
    groups = [
        (
            round((i % 3) * 5 + ((i * 7) % 11) / 10, 2),
            round((i % 3) * -4 + ((i * 13) % 17) / 10, 2),
        )
        for i in range(90)
    ]
    reduction = [
        {
            "length": i % 20 + 1,
            "width": round(0.8 * (i % 20 + 1) + (i % 3) / 10, 2),
            "mass": round(1.2 * (i % 20 + 1) + ((i * 7) % 11) / 10, 2),
        }
        for i in range(60)
    ]
    mixed = [
        (
            f"demo_{i:03d}",
            20 + (i * 7) % 45,
            "" if i % 13 == 0 else 2000 + (i * 137) % 5000,
            f"{i % 5 + 1:04d}",
            ("North", "East", "West")[i % 3],
            "true" if i % 2 else "false",
            f"2024-01-{i % 28 + 1:02d}",
            "retained" if i % 3 else "left",
        )
        for i in range(90)
    ]
    return {
        "classification.csv": delimited(
            ("signal", "variation", "outcome"), classification
        ),
        "regression.tsv": delimited(("length", "width", "response"), regression, "\t"),
        "clustering.csv": delimited(("x", "y"), groups),
        "reduction.jsonl": "".join(
            json.dumps(row, separators=(",", ":")) + "\n" for row in reduction
        ),
        "mixed.csv": delimited(
            (
                "customer_id",
                "age",
                "income",
                "zip_code",
                "region",
                "active",
                "joined",
                "outcome",
            ),
            mixed,
        ),
    }


if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[1] / "src/mlforge/examples"
    destination.mkdir(exist_ok=True)
    for filename, content in examples().items():
        (destination / filename).write_text(content, encoding="utf-8")
