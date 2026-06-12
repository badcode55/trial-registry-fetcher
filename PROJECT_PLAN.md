# Engineering Plan

## Current Branch Model

- `main`: user-facing branch. Keep code, README, examples, scripts, requirements, and `output/.gitkeep`.
- `dev`: development branch. Keep everything from `main`, plus tests and development planning documents.
- `跨注册库JSON canonical protocol JSON 设计.md` is dev-only and must not be synced to `main`.
- `dev_tools/` is dev-only and must not be synced to `main`.

## Current Feature Scope

- Supported registry IDs:
  - `UMIN...`: fetch from UMIN-CTR.
  - `NCT...`: fetch from ClinicalTrials.gov.
  - `not found`: record in `output/index.csv` without network access.
- Keyword/title search remains disabled.
- Canonical cross-registry protocol JSON is not implemented yet. The current phase only writes source-specific protocol JSON and records mapping notes for later discussion.

## Output Policy

- Default output directory is `output`.
- Each successful query writes one independent folder under `output/<run_id>/`.
- CSV files use `utf-8-sig` so Excel can open Chinese/Japanese text without mojibake.
- JSON files use `utf-8`.
- UMIN successful runs write:
  - `<run_id>.csv`
  - `UMIN_protocol.json`
  - `manifest.json`
- NCT successful runs write:
  - `<run_id>.csv`
  - `NCT_protocol.json`
  - `NCT_raw.json`
  - `manifest.json`
- Generated files under `output/` are ignored by git.
- `output/.gitkeep` is tracked only to keep the folder visible.

## Source Adapter Policy

- Registry-specific network and parsing code belongs in `trial_registry/sources/`.
- Source-specific JSON files are emitted through `RegistrySource.write_sidecar_files`.
- The runner should not contain `if source == ...` output logic except minimal auto-routing for user convenience.
- UMIN protocol JSON keeps UMIN section/field structure and must not pretend to be an NCT `protocolSection`.
- NCT protocol JSON follows the senior collaborator's `_protocol.json` structure for compatibility.

## dev to main Sync Policy

- Use `dev_tools/sync_dev_to_main.py` or `bash dev_tools/sync_dev_to_main.sh`.
- The sync script copies only user-facing files from `dev` to `main`.
- Do not sync:
  - `dev_tools/`
  - `PROJECT_PLAN.md`
  - `tests/`
  - `跨注册库JSON canonical protocol JSON 设计.md`
  - generated output files
- Default behavior is local-only. Use `--push` only when ready to publish `main` to GitHub.

## Dependency Policy

The runtime dependency file is `requirements.txt`.

Current dependencies:

```text
beautifulsoup4>=4.12
lxml>=4.9
```

`beautifulsoup4` is required for UMIN HTML parsing. `lxml` is required because the UMIN parser uses the `lxml` backend. NCT uses Python standard-library JSON and HTTP modules.

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
- 4 NCT rows are `saved`.
- 4 not-found rows are `not_found`.
- UMIN result folders contain `UMIN_protocol.json`.
- NCT result folders contain `NCT_protocol.json` and `NCT_raw.json`.
