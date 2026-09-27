# Synthetic examples

These five tables are generated entirely from row indices by
`scripts/generate_examples.py`. They contain no real people or measurements,
external data, downloads or randomly sampled inputs. No random seed is needed:
the integer formulas are the complete deterministic provenance.

- `classification.csv`: 80 rows, alternating on/off outcomes; signal has a
  four-unit class offset and modular variation. The second feature varies modulo 17.
- `regression.tsv`: 80 rows; response = 3.2 × length − 1.7 × width plus a small
  five-step residual. Length cycles modulo 20; width uses 7 × row modulo 11.
- `clustering.csv`: 90 rows around three separated centers, with modular offsets.
  There is no target column; cluster identifiers are arbitrary.
- `reduction.jsonl`: 60 rows; width and mass are correlated with length plus
  small modular variation. PCA describes these measurements, not predictive quality.
- `mixed.csv`: 90 fictional records with a clearly synthetic identifier,
  numeric values, missing incomes every thirteenth row, leading-zero codes,
  categories, booleans, dates and two outcomes. It demonstrates schema review.

All examples pass through the normal importer and explicit Preview confirmation.
No example bypasses feature/target eligibility or fitting rules. These simple
relationships demonstrate the workflow; their scores do not establish usefulness
on real data. Regeneration tests require byte-for-byte equality with committed files.
