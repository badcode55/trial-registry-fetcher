# Trial Registry Scraper

Extensible clinical trial registry lookup and export toolkit. The current version works from known literature registry IDs instead of keyword searching.

## Quick Start

Create a TXT input file such as `literature_ids.txt`:

```text
- 11 Arezzo 2021.pdf: NCT04438655
- 11 Ikeda 2016.pdf: UMIN000019339
- 11 Horie 2007.pdf: not found
```

Run the batch:

```bash
python3 -m trial_registry.cli --input-file literature_ids.txt --input-format txt --formats csv
```

Single UMIN ID lookup is still available:

```bash
python3 -m trial_registry.cli UMIN000019339 --formats csv
```

The older script path is kept as a compatibility wrapper:

```bash
python3 umin_ctr_scraper.py UMIN000019339
```

## Current Behavior

- `UMIN\d{9}` is fetched from UMIN-CTR and exported to a query CSV.
- `NCT\d+` is recorded in `index.csv` as `pending_source_integration`; NCT fetching will be integrated later with the external implementation.
- Other registry IDs are recorded as `pending_source_integration` so new registry websites can be added through source adapters.
- `not found` is recorded as `not_found` and is not searched online.
- Keyword/title search is intentionally disabled in this version.

## Outputs

Successful lookups create a batch directory:

```text
outputs/<run_id>/
  <run_id>.csv
  manifest.json
```

The output root keeps a cumulative query index:

```text
outputs/index.csv
```

Additional requested formats create `<run_id>.json`, `<run_id>.md`, or `<run_id>.txt`.

`<run_id>.csv` uses a stable main field mapping based on the UMIN registration preparation template, then preserves unmapped detail-page fields as `extra_*` columns. CSV files are written as Excel-friendly UTF-8 with BOM (`utf-8-sig`) so Chinese and Japanese text opens correctly in Excel.

`index.csv` appends one row for every input line and records literature file, registry ID, registry type, status, result CSV path, manifest path, and messages for pending or invalid rows.

## Python API

```python
from trial_registry import run_batch, run_query

batch = run_batch(
    "literature_ids.txt",
    input_format="txt",
    formats=["csv"],
    output_root="outputs",
)

single = run_query(
    "UMIN000019339",
    source="umin_ctr",
    formats=["csv"],
    output_root="outputs",
)
```

## Extension Points

To add a registry source, add an ID pattern in the registry ID resolver, implement `RegistrySource`, and register it in `trial_registry/sources/__init__.py`.

NCT fetching is intentionally represented as a pending adapter boundary for later integration:

```text
NCT fetching will be integrated with the external implementation later; this placeholder keeps the adapter boundary stable.
```

To add an export format, implement `Exporter` and register it in `trial_registry/exporters/__init__.py`.

## Tests

The local tests do not require network access:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_umin_ctr_unittest -v
```

Use a live UMIN smoke test manually when needed:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m trial_registry.cli UMIN000019339 --formats csv --output-dir outputs --run-id smoke-id-only
```
