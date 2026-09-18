# Dataset contract

Canonical owner of parsing, values, type inference, overrides, preparation help and input limits. ML_PIPELINE owns task eligibility and feature selection.

## Limits and provenance
Enforce before and during reading: local regular file only, max 20 MiB, 20,000 data rows, 100 columns, 128 Unicode characters/header, 4,096 characters/cell. Refuse FIFOs/devices/directories/URLs; resolve symlinks to a regular file, record the resolved location only in session memory, and check file identity on open. Stream with byte/row/cell counters so a growing file cannot bypass stat limits. No compressed files.

Only UTF-8 (optional BOM) is supported; no heuristic encoding or locale guessing. Do not silently truncate, sample for training, coerce invalid values or skip malformed records. Samples are for display only. A limit error reports the limit and suggests a smaller/clean supported table.

Canonical representation: immutable TabularDataset with ordered Column records (stable internal column ID, exact source header), ordered rows, and source-format metadata. Each Cell has raw_text (str or null) and source_kind (text/number/boolean/null). Row IDs are stable zero-based logical data-record indices independent of CSV physical multiline locations; retain line locations for parse errors. Schema/overrides are separate from raw cells. Never mutate raw cells when interpreting or training.

CSV text retains lexical forms (including leading zeros and spaces). JSON numbers preserve their lexical token via parse hooks; boolean tokens use "true"/"false". JSON null becomes a null Cell. Types/normalized values are derived views. A fingerprint of canonical content + parser options + schema overrides is session provenance; full source paths and raw fingerprints are not exported by default.

## Formats
| Format | Required structure | Handling |
|---|---|---|
| CSV | First record headers; comma delimiter; double-quote quoting; CRLF/LF, escaped quotes, multiline quoted cells | Strict csv reader; exact field counts on every record; no dialect sniffing |
| TSV | Same rules with tab delimiter | Same canonical importer |
| JSONL | One JSON object per nonempty line; identical exact key set; scalar string/finite number/bool/null values | First object fixes column order; later key order may differ; reject duplicate keys, nested values, array/root scalar, nonstandard NaN/Infinity and missing/extra keys |

A completely empty physical CSV record or whitespace-only JSONL line may be ignored and counted in the parse summary. A CSV record containing delimiters is a real row, even if all cells are empty. CSV whitespace-only field is preserved text, not silently treated as missing.
Headers must be unique exact strings and nonempty after whitespace inspection; do not trim or rename accepted headers. Reject control characters in headers; reserved internal IDs never depend on names. Empty file/header-only input fails as no data. One-column data may preview, but later eligibility can reject it. Malformed quotes, inconsistent widths and duplicates are errors with row/column location and no sensitive value echo.

Extension selects importer case-insensitively; unsupported extension explains supported formats. Parser errors provide Prepare with AI / Choose another dataset / Back. Do not reinterpret an XLSX file as CSV.

## Missing values and interpretation
Only CSV empty field, JSON null, or JSON empty string are missing. Strings "NA", "N/A", "null", "None", "?" and whitespace are literal values. Quoted and unquoted CSV empty fields are both missing (document this limitation). Numeric interpretation may strip surrounding whitespace for parsing, while raw values remain unchanged. No currency/grouping separators or locale decimals. Numeric grammar: optional sign, decimal digits/dot, optional exponent; finite float64 only. Integer magnitudes above 2^53-1 must not be converted silently: infer Identifier/Category or require Category override, with a precision warning.

Boolean inference: JSON booleans or case-insensitive text true/false only; not 0/1, yes/no. Date inference: strict valid YYYY-MM-DD only, no timezone/locale guesses. No automatic date expansion in V1.

Inference inspects all bounded data, not only preview:
1. All missing → Unknown (unusable until data changes).
2. ID-name signal: case-insensitive exact id/uuid/guid/identifier or suffix _id, plus at least 90% distinct nonmissing values with at least 10 present → Identifier.
3. All present values valid boolean → Boolean.
4. All present values valid strict date → Date.
5. All present values numeric and exactly representable under the above integer rule → Number, except digit strings with leading zeros → Category with a leading-zero note.
6. Otherwise → Category; incompatible native JSON scalar kinds produce a mixed-kind warning requiring acknowledgement or correction.

Number columns can be nearly unique legitimately; uniqueness alone never classifies all real-valued measurements as identifiers. Identifier is an advisory semantic role, not a guarantee. Categories with >50 distinct values or >80% unique (n>=20), and columns with long text (any value >200 characters), receive a high-cardinality/text warning; preview remains valid.

Missing counts use raw missing markers; distinct/suitability counts use effective interpreted values (so numeric 1 and 1.0 are the same number); raw samples retain lexical text.

Display exact row/column counts, effective type, detected type when overridden, nonmissing unique count, missing count/percentage and first three distinct present sample values in stable order. Table shows first 50 rows with row count label, horizontal/vertical scrolling and full cell detail. Controls/ANSI sequences are rendered visibly as escaped characters and all content uses literal rendering, never Rich markup. Values may be truncated visually only; help shows a bounded escaped full value.

## Verification and override
Preview offers "Looks correct", "Change type", "Preview is not correct", and "Choose another dataset". Explicit confirmation is required before Goal. Types: Number, Category, Boolean, Date, Identifier, Unknown (Unknown is diagnostic, not a selectable override). Category and Identifier preserve present text exactly; Number/Boolean/Date overrides must parse every present cell or report failure counts/locations and keep the previous effective schema. Mixed JSON scalars may become Category only after explicit override, using lexical text; explain that bool/numeric/string distinctions become categorical strings.

Reset to detected type is available. Type changes invalidate preview confirmation and all dependent selections/results through application state rules. A zip_code that was Number can become Category with exact original lexical values preserved. Date is retained for inspection but cannot be a feature/target unless the user explicitly changes interpretation. No automatic date-to-integer conversion.

## Prepare with AI
Available from unsupported/invalid import and "Preview is not correct". Creates a selectable read-only text area, optional Copy action and "Save prompt as .txt" using an explicit chosen destination with no overwrite. Clipboard failure leaves text/save available. App never invokes AI, opens a browser or uploads a file. No automatic inclusion of source values, column names, filename or full path. Include only safe format, structural error code, approximate dimensions if known and a user-visible note describing what would be shared if the user copies private data themselves.

Required generated prompt (stable sections; fill safe diagnostic placeholders):
"You are helping me convert a local dataset to a clean tabular file. I will separately decide what source material to share. The source format is [format]; the structural issue is [safe diagnostic].
Preserve all original information and semantic meaning. Do not invent, infer, fill, delete, merge or deduplicate rows or values. Do not choose a target. Do not perform machine-learning preprocessing, normalization, scaling, category encoding, feature engineering or analysis.
Only repair/convert the structure. Prefer UTF-8 CSV with one nonempty unique header per column, comma separators, consistent field counts, correctly escaped quotes and no index column. TSV or flat JSONL are acceptable under the same scalar-table rules. Preserve leading zeros as text. Use empty fields only for values already missing. Preserve ambiguous literals as text. Do not silently discard nested or unrepresentable information: explain the obstacle and ask me for a mapping decision before conversion.
Return the converted file and a concise list of structural changes. Verify row counts, column meanings and representative original values against the source. Do not claim to have inspected data I have not supplied. MLForge supports at most 20 MiB, 20,000 rows, 100 columns, 128-character headers and 4,096-character cells; if exceeded, explain the limit without silently dropping data."

The prompt is structural help, not a bypass of import validation. Returning prepared data goes through Load and Preview again.
