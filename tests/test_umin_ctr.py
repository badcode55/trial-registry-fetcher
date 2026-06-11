from __future__ import annotations

import csv
import json
from pathlib import Path

from trial_registry.exporters import EXPORTER_REGISTRY, get_exporter
from trial_registry.query import resolve_query
from trial_registry.runner import run_query
from trial_registry.sources.umin_ctr import UminCtrSource, parse_detail_page, parse_search_results


DETAIL_HTML = """
<html><body><div class="wrap">
<table class="explain_table"><tbody>
<tr><th>Unique ID issued by UMIN</th><td>UMIN000019339</td></tr>
<tr><th>Receipt number</th><td>R000022360</td></tr>
<tr><th>Scientific Title</th><td>Randomized controlled trial about the impact of oral antimicrobial prophylaxis on surgical site infection in laparoscopic colorectal surgery</td></tr>
</tbody></table>
<h2>Basic information</h2>
<div id="Input_vew_Mandatory"><h3>Public title</h3><tr><p>Randomized controlled trial about the impact of oral antimicrobial prophylaxis on surgical site infection in laparoscopic colorectal surgery</p></div>
<div id="Input_vew_Mandatory"><h3>Region</h3><tr><p><table><tr><td>Japan</td></tr></table></p></div>
<h2>Intervention</h2>
<div id="Input_vew_Mandatory"><h3>Type of intervention</h3><tr><p><table><tr><td>Medicine</td></tr></table></p></div>
<h2>Progress</h2>
<div id="Input_vew_Mandatory"><h3>Recruitment status</h3><tr><p>Completed</p></div>
</div></body></html>
"""

SEARCH_HTML = """
<html><body><table class="index_vew_table">
<tr><th>category</th><th>Unique ID issued by UMIN <hr /> Date of disclosure of the study information</th><th>Scientific Title:Acronym</th><th>Condition</th><th>Name of primary person or sponsor <hr /> Recruitment status</th><th>Detail <hr /> History</th></tr>
<tr><td>CTR</td><td>UMIN000019339<hr />2015/10/14</td><td>RCT of oral antimicrobial prophylaxis in laparoscopic colorectal surgery</td><td>Patients undergoing elective laparoscopic colorectal surgery</td><td><hr />Completed</td><td><span><a href="./ctr_view.cgi?recptno=R000022360">Detail</a></span></td></tr>
</table></body></html>
"""


def test_query_resolution():
    assert resolve_query("R000022360").query_type == "receipt_number"
    assert resolve_query("UMIN000019339").query_type == "umin_id"
    assert resolve_query("oral antimicrobial prophylaxis").query_type == "title"
    assert resolve_query("https://center6.umin.ac.jp/cgi-open-bin/ctr_e/ctr_view.cgi?recptno=R000022360").query_type == "detail_url"


def test_parse_detail_page_regression_fields():
    record = parse_detail_page(
        DETAIL_HTML,
        detail_url="https://center6.umin.ac.jp/cgi-open-bin/ctr_e/ctr_view.cgi?recptno=R000022360",
    )
    assert record.sections["Basic information"]["Region"] == "Japan"
    assert record.sections["Intervention"]["Type of intervention"] == "Medicine"
    assert record.sections["Progress"]["Recruitment status"] == "Completed"


def test_parse_search_results():
    matches = parse_search_results(SEARCH_HTML, matched_by="umin_id")
    assert len(matches) == 1
    assert matches[0].match_key == "R000022360"
    assert matches[0].detail_url.endswith("recptno=R000022360")
    assert matches[0].match_rank == 1


def test_exporter_registry_can_be_extended():
    class DummyExporter:
        name = "dummy"

        def export(self, *, output_dir, rows, records, run_id):
            path = output_dir / "dummy.txt"
            path.write_text("dummy", encoding="utf-8")
            return path

    EXPORTER_REGISTRY["dummy"] = DummyExporter
    try:
        assert get_exporter("dummy").name == "dummy"
    finally:
        EXPORTER_REGISTRY.pop("dummy", None)


def test_run_query_writes_csv_and_manifest_with_fake_source(tmp_path, monkeypatch):
    class FakeSource(UminCtrSource):
        name = "fake_umin"

        def search(self, query):
            return parse_search_results(SEARCH_HTML, matched_by=query.query_type)

        def fetch_detail(self, match):
            return parse_detail_page(DETAIL_HTML, detail_url=match.detail_url, match=match)

    from trial_registry import sources

    monkeypatch.setitem(sources.SOURCE_REGISTRY, "fake_umin", FakeSource)
    result = run_query(
        "UMIN000019339",
        source="fake_umin",
        formats=["csv"],
        output_root=str(tmp_path),
        run_id="test-run",
    )

    assert result.match_count == 1
    assert result.failure_count == 0
    assert result.files["csv"].exists()
    assert result.manifest_path.exists()
    assert result.files["csv"].name == "test-run.csv"
    assert result.files["csv"].read_bytes()[:3] == b"\xef\xbb\xbf"

    index_path = result.output_dir.parent / "index.csv"
    assert index_path.exists()
    assert index_path.read_bytes()[:3] == b"\xef\xbb\xbf"

    with result.files["csv"].open(encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))

    assert row["run_id"] == "test-run"
    assert row["recptno"] == "R000022360"
    assert row["region"] == "Japan"
    assert row["type_of_intervention"] == "Medicine"
    assert row["recruitment_status"] == "Completed"

    with index_path.open(encoding="utf-8-sig", newline="") as handle:
        index_rows = list(csv.DictReader(handle))
    assert len(index_rows) == 1
    assert index_rows[0]["run_id"] == "test-run"
    assert index_rows[0]["result_csv"] == str(result.files["csv"])

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["index_path"] == str(index_path)
    assert manifest["files"]["csv"] == str(result.files["csv"])


def test_index_csv_appends_across_runs(tmp_path, monkeypatch):
    class FakeSource(UminCtrSource):
        name = "fake_umin_append"

        def search(self, query):
            return parse_search_results(SEARCH_HTML, matched_by=query.query_type)

        def fetch_detail(self, match):
            return parse_detail_page(DETAIL_HTML, detail_url=match.detail_url, match=match)

    from trial_registry import sources

    monkeypatch.setitem(sources.SOURCE_REGISTRY, "fake_umin_append", FakeSource)
    run_query(
        "UMIN000019339",
        source="fake_umin_append",
        formats=["csv"],
        output_root=str(tmp_path),
        run_id="test-run-1",
    )
    run_query(
        "R000022360",
        source="fake_umin_append",
        formats=["csv"],
        output_root=str(tmp_path),
        run_id="test-run-2",
    )

    with (Path(tmp_path) / "index.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert [row["run_id"] for row in rows] == ["test-run-1", "test-run-2"]
    assert rows[0]["query_type"] == "umin_id"
    assert rows[1]["query_type"] == "receipt_number"
