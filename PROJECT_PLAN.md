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
  - `ISRCTN...`: direct ISRCTN detail-page fetch where available.
  - `ChiCTR...`, `ACTRN...`, `EudraCT...`: ID recognition, traceable status records, and explicit `search_required` statuses where automatic detail resolution depends on parseable search HTML. Source-specific JSON/CSV are written only after a detail page or API payload is fetched.
  - China CDE `CTR...`: pure HTTP WAF/JS challenge is recorded as `blocked_by_site`; when `TRIAL_REGISTRY_ENABLE_CHROME_CDP=1` is set, the source can try a local Chrome/CDP fallback to fetch browser-visible search/detail HTML and save outputs only after detail-page validation passes.
  - CTIS/EU CT IDs: public API search is implemented; live `number` lookup writes `CTIS_raw.json`, `CTIS_protocol.json`, and CSV when a unique match is returned.
  - `not found`: record in `output/index.csv` without network access.
- Keyword/title search remains disabled.
- Canonical cross-registry protocol JSON is not implemented yet. The current phase writes source-specific protocol JSON, preserves raw evidence where available, and records mapping notes for later discussion.

## Known v1 Gaps

The new non-NCT/UMIN sources are intentionally conservative. They should preserve traceable registry evidence, but they must not imply that a full registry detail page was fetched when only a search link is available.

## Detail URL Classification

| Category | Sources | Implementation status |
| --- | --- | --- |
| ID directly builds detail/API URL | NCT, ISRCTN | Fetch directly and emit source-specific outputs on success. |
| ID needs an intermediate search that is already implemented | UMIN | Search UMIN for `recptno`, then fetch detail URL. |
| ID needs search-page detail-link parsing | ChiCTR, ANZCTR, EUCTR | Static HTML parsers and fixture tests are implemented; live success depends on the registry returning parseable search HTML. |
| ID needs dynamic form/session/API discovery | China CDE | Default pure HTTP path stays blocked; optional Chrome/CDP fallback can resolve browser-visible search/detail pages and save outputs when detail fields validate. |
| ID needs public API search | CTIS | CTIS live public search API is implemented and saves source-specific outputs on unique matches. |

| Source | Current v1 behavior | Not implemented yet |
| --- | --- | --- |
| ChiCTR | Recognizes `ChiCTR2600126676`; fixture search parser resolves `showprojEN.html?proj=327816`; fetched detail pages emit `ChiCTR_protocol.json`, raw HTML/text, and CSV. | Live search validation and source-specific field-table parser refinement. |
| China CDE / CTR | Recognizes `CTR20223406`; WAF challenge pages are recorded as `blocked_by_site`; optional `TRIAL_REGISTRY_ENABLE_CHROME_CDP=1` fallback uses local Chrome/CDP to obtain browser-visible search/detail HTML, parse `getDetail(this.id)` form parameters, validate the detail page, then save `ChinaDrugTrials_protocol.json`, raw HTML/text, and CSV. | Depends on installed Chrome/Edge, Node, visible-browser access, and the site not requiring login/CAPTCHA at runtime. Field parsing is still generic table/heading extraction. |
| ACTRN / ANZCTR | Recognizes `ACTRN12626000671369`; fixture search parser resolves `TrialReview.aspx?id=391548&isReview=true`; fetched detail pages emit `ANZCTR_protocol.json`, raw HTML/text, and CSV. | Live ANZCTR search validation. |
| CTIS | Recognizes EU CT IDs such as `2025-523616-36-00`; live public API search is implemented and saves `CTIS_protocol.json`, `CTIS_raw.json`, and CSV on unique matches. | Deeper CTIS full-trial view extraction and more complete field mapping. |
| EUCTR | Recognizes EudraCT/EUCTR IDs and records `search_required`; can fetch `/ctr-search/trial/...` detail URLs when supplied directly. | Automatic country/detail-page selection, multiple-country match handling, results/protocol parsing, and structured EUCTR field mapping. |

Next implementation step: add per-source fixtures for saved HTML/API responses, then implement ID-to-detail resolution before adding field-level RoB2 mapping. This keeps tests deterministic and avoids treating network or anti-bot failures as registry absence.

## Output Policy

- Default output directory is `output`.
- Each successful query writes one independent folder under `output/<run_id>/`.
- CSV files use `utf-8-sig` so Excel can open Chinese/Japanese text without mojibake.
- JSON files use `utf-8`.
- UMIN successful runs write:
  - `<run_id>.csv`
  - `UMIN_protocol.json`
  - `UMIN_raw.html`
  - `manifest.json`
- NCT successful runs write:
  - `<run_id>.csv`
  - `NCT_protocol.json`
  - `NCT_raw.json`
  - `manifest.json`
- Other integrated registries write these files only after a detail page or API payload is fetched:
  - `<run_id>.csv`
  - source-specific `*_protocol.json`
  - raw HTML/text when a detail page is fetched
  - `manifest.json`
- ID-only runs that still require search-page resolution write `manifest.json` and `index.csv` status rows, but do not write CSV or source-specific protocol JSON.
- Source-specific protocol JSON files include `protocol_sections`, `results_sections`, `source_specific`, and `raw_evidence_files`.
- `index.csv` and `manifest.json` record detail URL, fetch status, whether detail was fetched, whether result sections were found, protocol JSON path, raw evidence paths, and failures.
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
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_multi_registry_ids_unittest -v
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
