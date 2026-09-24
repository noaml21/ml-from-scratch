"""Export parity probes include observed, missing and genuinely unseen categories."""

from mlforge.export.wheel import verification_probes


def test_probe_construction_preserves_inputs_and_avoids_category_collisions():
    fields = [
        {"name": "x", "type": "Number"},
        {
            "name": "city",
            "type": "Category",
            "categories": ["north", "__mlforge_unknown_0__"],
        },
    ]
    records = [{"x": 2, "city": "north"} for _ in range(1000)]
    result = verification_probes(fields, records)
    assert result[:1000] == records
    assert result[1000] == {"x": None, "city": None}
    assert result[1001] == {"x": 2, "city": "__mlforge_unknown_1__"}
    result[0]["city"] = "changed"
    assert records[0]["city"] == "north"
