# Engineering Plan

## Current Branch Model

- `main`: user-facing branch. Keep code, README, examples, scripts, requirements, and `output/.gitkeep`.
- `dev`: development branch. Keep everything from `main`, plus tests and agent/development planning documents.

## Output Policy

- Default output directory is `output`.
- Generated files under `output/` are ignored by git.
- `output/.gitkeep` is tracked only to keep the folder visible.
- Historical generated output directories `outputs/` and `outputs_id_only/` are ignored.

## Dependency Policy

The runtime dependency file is `requirements.txt`.

Current dependencies:

```text
beautifulsoup4>=4.12
lxml>=4.9
```

`beautifulsoup4` is required for HTML parsing. `lxml` is required because the parser uses the `lxml` backend.

## Development Validation

Run local tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_umin_ctr_unittest -v
```

Run the example:

```bash
bash scripts/run_example.sh
```

Expected example result:

- `output/index.csv` exists.
- 11 input rows are indexed.
- 3 UMIN rows are `saved`.
- 4 NCT rows are `pending_source_integration`.
- 4 not-found rows are `not_found`.
