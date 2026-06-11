from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from trial_registry.exporters import EXPORTER_REGISTRY, get_exporter
from trial_registry.input_readers import parse_txt_line
from trial_registry.query import resolve_query
from trial_registry.registry_ids import resolve_registry_id
from trial_registry.runner import run_batch, run_query
from trial_registry.sources import SOURCE_REGISTRY
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


class UminCtrTests(unittest.TestCase):
    def test_query_resolution(self):
        self.assertEqual(resolve_query("R000022360").query_type, "receipt_number")
        self.assertEqual(resolve_query("UMIN000019339").query_type, "umin_id")
        self.assertEqual(resolve_query("oral antimicrobial prophylaxis").query_type, "keyword_search_not_enabled")
        url = "https://center6.umin.ac.jp/cgi-open-bin/ctr_e/ctr_view.cgi?recptno=R000022360"
        self.assertEqual(resolve_query(url).query_type, "detail_url")

    def test_txt_reader_and_registry_id_resolution(self):
        umin = parse_txt_line("- 11 Ikeda 2016.pdf: UMIN000019339", "- 11 Ikeda 2016.pdf: UMIN000019339")
        nct = parse_txt_line("- 11 Arezzo 2021.pdf: NCT04438655", "- 11 Arezzo 2021.pdf: NCT04438655")
        not_found = parse_txt_line("- 11 Horie 2007.pdf: not found", "- 11 Horie 2007.pdf: not found")
        invalid = parse_txt_line("broken line", "broken line")
        unknown = resolve_registry_id("paper.pdf", "JPRN12345", "paper.pdf: JPRN12345")

        self.assertEqual(umin.literature_file, "11 Ikeda 2016.pdf")
        self.assertEqual(umin.registry_type, "umin")
        self.assertEqual(umin.status, "ready")
        self.assertEqual(umin.source_hint, "umin_ctr")
        self.assertEqual(nct.registry_type, "nct")
        self.assertEqual(nct.status, "pending_source_integration")
        self.assertEqual(not_found.status, "not_found")
        self.assertEqual(invalid.status, "invalid_input")
        self.assertEqual(unknown.status, "pending_source_integration")

    def test_keyword_search_is_disabled(self):
        with self.assertRaisesRegex(ValueError, "Keyword search is not enabled"):
            run_query(
                "oral antimicrobial prophylaxis",
                output_root=tempfile.mkdtemp(),
                run_id="keyword-disabled",
            )

    def test_parse_detail_page_regression_fields(self):
        record = parse_detail_page(
            DETAIL_HTML,
            detail_url="https://center6.umin.ac.jp/cgi-open-bin/ctr_e/ctr_view.cgi?recptno=R000022360",
        )
        self.assertEqual(record.sections["Basic information"]["Region"], "Japan")
        self.assertEqual(record.sections["Intervention"]["Type of intervention"], "Medicine")
        self.assertEqual(record.sections["Progress"]["Recruitment status"], "Completed")

    def test_parse_search_results(self):
        matches = parse_search_results(SEARCH_HTML, matched_by="umin_id")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].match_key, "R000022360")
        self.assertTrue(matches[0].detail_url.endswith("recptno=R000022360"))
        self.assertEqual(matches[0].match_rank, 1)

    def test_exporter_registry_can_be_extended(self):
        class DummyExporter:
            name = "dummy"

            def export(self, *, output_dir, rows, records, run_id):
                path = output_dir / "dummy.txt"
                path.write_text("dummy", encoding="utf-8")
                return path

        EXPORTER_REGISTRY["dummy"] = DummyExporter
        try:
            self.assertEqual(get_exporter("dummy").name, "dummy")
        finally:
            EXPORTER_REGISTRY.pop("dummy", None)

    def test_run_query_writes_csv_and_manifest_with_fake_source(self):
        class FakeSource(UminCtrSource):
            name = "fake_umin"

            def search(self, query):
                return parse_search_results(SEARCH_HTML, matched_by=query.query_type)

            def fetch_detail(self, match):
                return parse_detail_page(DETAIL_HTML, detail_url=match.detail_url, match=match)

        SOURCE_REGISTRY["fake_umin"] = FakeSource
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = run_query(
                    "UMIN000019339",
                    source="fake_umin",
                    formats=["csv"],
                    output_root=tmpdir,
                    run_id="test-run",
                )
                self.assertEqual(result.match_count, 1)
                self.assertEqual(result.failure_count, 0)
                self.assertTrue(result.files["csv"].exists())
                self.assertTrue(result.manifest_path.exists())
                self.assertEqual(result.files["csv"].name, "test-run.csv")

                self.assertEqual(result.files["csv"].read_bytes()[:3], b"\xef\xbb\xbf")
                index_path = result.output_dir.parent / "index.csv"
                self.assertTrue(index_path.exists())
                self.assertEqual(index_path.read_bytes()[:3], b"\xef\xbb\xbf")

                with result.files["csv"].open(encoding="utf-8-sig", newline="") as handle:
                    row = next(csv.DictReader(handle))

                self.assertEqual(row["run_id"], "test-run")
                self.assertEqual(row["recptno"], "R000022360")
                self.assertEqual(row["region"], "Japan")
                self.assertEqual(row["type_of_intervention"], "Medicine")
                self.assertEqual(row["recruitment_status"], "Completed")

                with index_path.open(encoding="utf-8-sig", newline="") as handle:
                    index_rows = list(csv.DictReader(handle))
                self.assertEqual(len(index_rows), 1)
                self.assertEqual(index_rows[0]["run_id"], "test-run")
                self.assertEqual(index_rows[0]["result_csv"], str(result.files["csv"]))

                manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
                self.assertEqual(manifest["index_path"], str(index_path))
                self.assertEqual(manifest["files"]["csv"], str(result.files["csv"]))
        finally:
            SOURCE_REGISTRY.pop("fake_umin", None)

    def test_index_csv_appends_across_runs(self):
        class FakeSource(UminCtrSource):
            name = "fake_umin_append"

            def search(self, query):
                return parse_search_results(SEARCH_HTML, matched_by=query.query_type)

            def fetch_detail(self, match):
                return parse_detail_page(DETAIL_HTML, detail_url=match.detail_url, match=match)

        SOURCE_REGISTRY["fake_umin_append"] = FakeSource
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                run_query(
                    "UMIN000019339",
                    source="fake_umin_append",
                    formats=["csv"],
                    output_root=tmpdir,
                    run_id="test-run-1",
                )
                run_query(
                    "R000022360",
                    source="fake_umin_append",
                    formats=["csv"],
                    output_root=tmpdir,
                    run_id="test-run-2",
                )

                index_path = Path(tmpdir) / "index.csv"
                with index_path.open(encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.DictReader(handle))

                self.assertEqual([row["run_id"] for row in rows], ["test-run-1", "test-run-2"])
                self.assertEqual(rows[0]["query_type"], "umin_id")
                self.assertEqual(rows[1]["query_type"], "receipt_number")
        finally:
            SOURCE_REGISTRY.pop("fake_umin_append", None)

    def test_run_batch_records_ready_pending_not_found_and_invalid(self):
        class FakeSource(UminCtrSource):
            name = "fake_umin_batch"

            def search(self, query):
                return parse_search_results(SEARCH_HTML, matched_by=query.query_type)

            def fetch_detail(self, match):
                return parse_detail_page(DETAIL_HTML, detail_url=match.detail_url, match=match)

        SOURCE_REGISTRY["fake_umin_batch"] = FakeSource
        original_umin = SOURCE_REGISTRY.get("umin_ctr")
        SOURCE_REGISTRY["umin_ctr"] = FakeSource
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = Path(tmpdir) / "literature_ids.txt"
                input_path.write_text(
                    "\n".join(
                        [
                            "- 11 Ikeda 2016.pdf: UMIN000019339",
                            "- 11 Arezzo 2021.pdf: NCT04438655",
                            "- 11 Horie 2007.pdf: not found",
                            "- 11 Future 2025.pdf: JPRN12345",
                            "bad line",
                        ]
                    ),
                    encoding="utf-8",
                )
                result = run_batch(
                    str(input_path),
                    input_format="txt",
                    formats=["csv"],
                    output_root=tmpdir,
                )

                self.assertEqual(result.total_count, 5)
                self.assertEqual(result.saved_count, 1)
                self.assertEqual(result.pending_count, 4)
                self.assertEqual(result.failure_count, 0)
                self.assertEqual(len(result.results), 1)
                self.assertTrue(result.results[0].files["csv"].exists())

                with result.index_path.open(encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.DictReader(handle))

                self.assertEqual(len(rows), 5)
                statuses = {row["literature_file"]: row["status"] for row in rows}
                self.assertEqual(statuses["11 Ikeda 2016.pdf"], "saved")
                self.assertEqual(statuses["11 Arezzo 2021.pdf"], "pending_source_integration")
                self.assertEqual(statuses["11 Horie 2007.pdf"], "not_found")
                self.assertEqual(statuses["11 Future 2025.pdf"], "pending_source_integration")
                self.assertIn("invalid_input", [row["status"] for row in rows])
                self.assertEqual(rows[0]["registry_id"], "UMIN000019339")
                self.assertEqual(rows[0]["registry_type"], "umin")
        finally:
            if original_umin is not None:
                SOURCE_REGISTRY["umin_ctr"] = original_umin
            SOURCE_REGISTRY.pop("fake_umin_batch", None)


if __name__ == "__main__":
    unittest.main()
