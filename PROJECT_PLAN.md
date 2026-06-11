# Literature Registry ID Batch Lookup Project

## Goal

Build an extensible tool that reads literature file names and known registry IDs, fetches available registry information, and exports CSV by default.

The current version is ID-only: it does not search by keywords, study titles, or PDF file names. UMIN-CTR is the only active fetch source. NCT and future registry websites are tracked through a pending source-adapter path so they can be integrated later without changing the batch runner.

## Current Interfaces

Batch TXT input:

```bash
python -m trial_registry.cli --input-file literature_ids.txt --input-format txt --formats csv
```

Single UMIN lookup:

```bash
python -m trial_registry.cli UMIN000019339 --formats csv
```

Python API:

```python
from trial_registry import run_batch, run_query

run_batch("literature_ids.txt", input_format="txt", formats=["csv"], output_root="outputs")
run_query("UMIN000019339", source="umin_ctr", formats=["csv"], output_root="outputs")
```

## Input Rules

Default TXT lines use the current upstream program output shape:

```text
- 11 Arezzo 2021.pdf: NCT04438655
- 11 Ikeda 2016.pdf: UMIN000019339
- 11 Horie 2007.pdf: not found
```

- `UMIN\d{9}` maps to `registry_type=umin`, `source=umin_ctr`, `status=ready`.
- `NCT\d+` maps to `registry_type=nct`, `status=pending_source_integration`.
- `not found` maps to `status=not_found`.
- Other non-empty registry IDs map to `status=pending_source_integration`.
- Invalid lines map to `status=invalid_input`.
- Keyword/title search maps to `keyword_search_not_enabled` and is intentionally disabled.

## Output Layout

Successful UMIN lookups write a new batch directory:

```text
outputs/<run_id>/
  <run_id>.csv
  manifest.json
```

The output root keeps a cumulative input index:

```text
outputs/index.csv
```

`index.csv` appends one row per input line with:

```text
run_id,created_at_utc,literature_file,registry_id,registry_type,status,source,query_value,query_type,match_count,saved_count,failure_count,result_csv,manifest_path,formats,message
```

`not found`, NCT, unknown registry IDs, and invalid input lines do not generate detail CSV files, but they are recorded in `index.csv`.

All CSV files use Excel-friendly UTF-8 with BOM (`utf-8-sig`) to prevent Chinese and Japanese text from displaying as mojibake when opened directly in Excel.

## Extension Design

- New inputs should implement `InputReader`; TXT is implemented now, CSV/JSON are reserved.
- New registry websites should be added by extending ID resolver rules and implementing `RegistrySource`.
- NCT fetching will be integrated with the external implementation later; the pending status keeps the adapter boundary stable.
- Keyword search is reserved for a later version and intentionally disabled in v1.

## Test Plan

- TXT parser handles UMIN, NCT, `not found`, unknown IDs, and invalid lines while preserving literature file names.
- Batch runner writes UMIN result CSVs and records all input rows in `index.csv`.
- NCT and unknown registry IDs are recorded as `pending_source_integration`.
- Plain keyword text does not trigger registry search.
- `UMIN000019339` still resolves to `R000022360` and exports valid UMIN fields.
- Query CSV and `index.csv` are written as `utf-8-sig`.
