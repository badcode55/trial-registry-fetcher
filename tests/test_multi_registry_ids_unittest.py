from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from trial_registry.runner import run_batch, run_query
from trial_registry.input_readers import parse_txt_line
from trial_registry.query import resolve_query
from trial_registry.registry_ids import resolve_registry_id
from trial_registry.sources import SOURCE_REGISTRY
from trial_registry.sources.anzctr import AnzctrSource, parse_anzctr_search_results
from trial_registry.sources.chictr import ChictrSource, parse_chictr_search_results
from trial_registry.sources.china_drug_trials import (
    ChinaDrugTrialsSource,
    is_china_drug_trials_blocked_page,
    is_china_drug_trials_detail_page,
    parse_china_drug_trials_search_results,
)
from trial_registry.sources.ctis import (
    CtisSource,
    ctis_page_has_trial_content,
    parse_ctis_search_response,
)
from trial_registry.sources.euctr import EuCtrSource, parse_euctr_search_results
from trial_registry.sources.isrctn import IsrctnSource


FIXTURE_DIR = Path(__file__).parent / "fixtures"


class MultiRegistryIdTests(unittest.TestCase):
    def setUp(self):
        self._previous_live_search = os.environ.get("TRIAL_REGISTRY_DISABLE_LIVE_SEARCH")
        os.environ["TRIAL_REGISTRY_DISABLE_LIVE_SEARCH"] = "1"

    def tearDown(self):
        if self._previous_live_search is None:
            os.environ.pop("TRIAL_REGISTRY_DISABLE_LIVE_SEARCH", None)
        else:
            os.environ["TRIAL_REGISTRY_DISABLE_LIVE_SEARCH"] = self._previous_live_search

    def test_resolve_registry_ids_for_new_sources(self):
        cases = [
            ("paper.pdf", "CTR20223406", "china_drug_trials", "china_drug_trials"),
            ("paper.pdf", "ChiCTR2600126676", "chictr", "chictr"),
            ("paper.pdf", "ACTRN12626000671369", "anzctr", "anzctr"),
            ("paper.pdf", "ISRCTN12345678", "isrctn", "isrctn"),
            ("paper.pdf", "EudraCT 2015-005614-30", "euctr", "euctr"),
            ("paper.pdf", "EUCTR2015-005614-30", "euctr", "euctr"),
            ("paper.pdf", "2025-523616-36-00", "ctis", "ctis"),
        ]
        for literature_file, registry_id, registry_type, source_hint in cases:
            with self.subTest(registry_id=registry_id):
                item = resolve_registry_id(literature_file, registry_id, f"{literature_file}: {registry_id}")
                self.assertEqual(item.status, "ready")
                self.assertEqual(item.registry_type, registry_type)
                self.assertEqual(item.source_hint, source_hint)

    def test_chictr_record_word_is_not_a_valid_id(self):
        item = resolve_registry_id("paper.pdf", "CHICTRRECORD", "paper.pdf: CHICTRRECORD")
        self.assertEqual(item.status, "pending_source_integration")
        self.assertEqual(item.registry_type, "unknown")

    def test_query_resolution_for_new_ids_and_urls(self):
        self.assertEqual(resolve_query("ISRCTN12345678").query_type, "isrctn_id")
        self.assertEqual(resolve_query("ChiCTR2600126676").query_type, "chictr_id")
        self.assertEqual(resolve_query("CTR20223406").query_type, "china_drug_trial_id")
        self.assertEqual(resolve_query("ACTRN12626000671369").query_type, "actrn_id")
        self.assertEqual(resolve_query("EudraCT 2015-005614-30").query_type, "eudract_id")
        self.assertEqual(resolve_query("2025-523616-36-00").query_type, "ctis_id")
        self.assertEqual(
            resolve_query("https://www.chictr.org.cn/showprojEN.html?proj=327816").source_hint,
            "chictr",
        )
        self.assertEqual(
            resolve_query("https://www.anzctr.org.au/Trial/Registration/TrialReview.aspx?id=391548").source_hint,
            "anzctr",
        )

    def test_sources_return_stable_matches_without_network_for_ids(self):
        source_cases = [
            (IsrctnSource(), "ISRCTN12345678", "isrctn_id", "https://www.isrctn.com/ISRCTN12345678"),
            (ChictrSource(), "CHICTR2600126676", "chictr_id", "https://www.chictr.org.cn/searchproj.html"),
            (ChinaDrugTrialsSource(), "CTR20223406", "china_drug_trial_id", "https://www.chinadrugtrials.org.cn/clinicaltrials.searchlist.dhtml"),
            (AnzctrSource(), "ACTRN12626000671369", "actrn_id", "https://www.anzctr.org.au/TrialSearch.aspx"),
            (EuCtrSource(), "2015-005614-30", "eudract_id", "https://www.clinicaltrialsregister.eu/ctr-search/search"),
            (CtisSource(), "2025-523616-36-00", "ctis_id", "https://euclinicaltrials.eu/search-for-clinical-trials/"),
        ]
        for source, raw_input, query_type, expected_prefix in source_cases:
            with self.subTest(source=source.name):
                match = source.search(resolve_query(raw_input, source_hint=source.name))[0]
                self.assertEqual(match.source, source.name)
                self.assertEqual(match.matched_by, query_type)
                self.assertTrue(match.detail_url.startswith(expected_prefix))

    def test_link_only_sources_write_protocol_json_without_network(self):
        source_cases = [
            (ChictrSource(), "ChiCTR2600126676", "ChiCTR_protocol.json", "chictr_protocol"),
            (ChinaDrugTrialsSource(), "CTR20223406", "ChinaDrugTrials_protocol.json", "china_drug_trials_protocol"),
            (AnzctrSource(), "ACTRN12626000671369", "ANZCTR_protocol.json", "anzctr_protocol"),
            (EuCtrSource(), "EudraCT 2015-005614-30", "EUCTR_protocol.json", "euctr_protocol"),
            (CtisSource(), "2025-523616-36-00", "CTIS_protocol.json", "ctis_protocol"),
        ]
        for source, raw_input, protocol_name, file_key in source_cases:
            with self.subTest(source=source.name):
                query = resolve_query(raw_input, source_hint=source.name)
                match = source.search(query)[0]
                record = source.fetch_detail(match)
                row = source.normalize(record, run_id="test", query=query, match_count=1)
                with tempfile.TemporaryDirectory() as tmpdir:
                    files = source.write_sidecar_files(record, output_dir=Path(tmpdir))
                    protocol = json.loads((Path(tmpdir) / protocol_name).read_text(encoding="utf-8"))
                self.assertEqual(files[file_key].name, protocol_name)
                self.assertIn(row["fetch_status"], {"search_required", "blocked_by_site", "fetched"})
                self.assertEqual(protocol["source_registry"], source.registry_label)
                self.assertIn("fetch_status", protocol)
                self.assertIn("protocol_sections", protocol)
                self.assertIn("results_sections", protocol)
                self.assertIn("source_specific", protocol)
                self.assertIn("raw_evidence_files", protocol)

    def test_run_query_does_not_write_result_files_for_search_required_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_query(
                "ChiCTR2400090000",
                source="chictr",
                formats=["csv"],
                output_root=tmpdir,
                run_id="chictr-run",
            )

            self.assertEqual(result.status, "search_required")
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

            self.assertNotIn("csv", result.files)
            self.assertNotIn("chictr_protocol", result.files)
            self.assertFalse((result.output_dir / "chictr-run.csv").exists())
            self.assertFalse((result.output_dir / "ChiCTR_protocol.json").exists())
            self.assertEqual(manifest["status"], "search_required")
            self.assertEqual(manifest["saved_count"], 0)
            self.assertEqual(manifest["detail_fetched"], False)
            self.assertEqual(manifest["source_protocol_files"], {})

    def test_run_batch_does_not_count_search_required_as_saved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "literature_ids.txt"
            input_path.write_text(
                "- example.pdf: ChiCTR2400090000\n",
                encoding="utf-8",
            )

            result = run_batch(
                str(input_path),
                input_format="txt",
                formats=["csv"],
                output_root=tmpdir,
            )

            self.assertEqual(result.total_count, 1)
            self.assertEqual(result.saved_count, 0)
            self.assertEqual(result.pending_count, 1)
            self.assertEqual(result.failure_count, 0)

    def test_parse_chictr_search_result_to_detail_url(self):
        html = (FIXTURE_DIR / "chictr_search_ChiCTR2600126676.html").read_text(encoding="utf-8")
        query = resolve_query("ChiCTR2600126676", source_hint="chictr")
        matches = parse_chictr_search_results(html, query=query, source=ChictrSource())

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].match_key, "CHICTR2600126676")
        self.assertEqual(matches[0].raw_summary["fetch_status"], "fetched")
        self.assertEqual(matches[0].detail_url, "https://www.chictr.org.cn/showprojEN.html?proj=327816")

    def test_parse_anzctr_search_result_to_detail_url(self):
        html = (FIXTURE_DIR / "anzctr_search_ACTRN12626000671369.html").read_text(encoding="utf-8")
        query = resolve_query("ACTRN12626000671369", source_hint="anzctr")
        matches = parse_anzctr_search_results(html, query=query, source=AnzctrSource())

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].match_key, "ACTRN12626000671369")
        self.assertEqual(matches[0].raw_summary["fetch_status"], "fetched")
        self.assertEqual(
            matches[0].detail_url,
            "https://www.anzctr.org.au/Trial/Registration/TrialReview.aspx?id=391548&isReview=true",
        )

    def test_parse_cde_search_result_to_detail_url_when_available(self):
        html = """
        <html><body><table>
        <tr><td>CTR20223406</td><td><a href="/clinicaltrials.searchlistdetail.dhtml?id=fixture">Detail</a></td></tr>
        </table></body></html>
        """
        query = resolve_query("CTR20223406", source_hint="china_drug_trials")
        matches = parse_china_drug_trials_search_results(
            html,
            query=query,
            source=ChinaDrugTrialsSource(),
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].match_key, "CTR20223406")
        self.assertIn("clinicaltrials.searchlistdetail.dhtml", matches[0].detail_url)

    def test_parse_cde_browser_visible_search_result_to_form_payload(self):
        html = (FIXTURE_DIR / "cde_search_CTR20223406.html").read_text(encoding="utf-8")
        query = resolve_query("CTR20223406", source_hint="china_drug_trials")
        matches = parse_china_drug_trials_search_results(
            html,
            query=query,
            source=ChinaDrugTrialsSource(),
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].match_key, "CTR20223406")
        self.assertEqual(matches[0].raw_summary["fetch_status"], "search_required")
        self.assertEqual(matches[0].raw_summary["fetch_mode"], "cde_detail_form_post_required")
        self.assertTrue(matches[0].detail_url.startswith("https://www.chinadrugtrials.org.cn/clinicaltrials.searchlistdetail.dhtml?"))
        self.assertIn("id=fd31f9f296eb4ca5a7aad3230c25abf9", matches[0].detail_url)
        self.assertIn("ckm_index=1", matches[0].detail_url)
        self.assertIn("keywords=CTR20223406", matches[0].detail_url)
        payload = json.loads(matches[0].raw_summary["detail_form_payload_json"])
        self.assertEqual(payload["id"], "fd31f9f296eb4ca5a7aad3230c25abf9")
        self.assertEqual(payload["ckm_index"], "1")
        self.assertEqual(payload["keywords"], "CTR20223406")

    def test_detect_cde_waf_challenge_page(self):
        html = """
        <html><head>
        <meta id="9DhefwqGPrzGxEp9hPaoag" content="LM&lt;challenge" />
        <script src="/4QbVtADbnLVIc/c.FxJzG50F.6152bb9.js?D9PVtGL=6152bb"></script>
        </head><body></body></html>
        """
        self.assertTrue(is_china_drug_trials_blocked_page(html))

    def test_cde_detail_page_detection_requires_registry_and_fields(self):
        html = """
        <html><body>
        <h1>CTR20223406详细信息</h1>
        <h2>基本信息</h2>
        <table><tr><td>登记号</td><td>CTR20223406</td><td>试验状态</td><td>进行中</td></tr></table>
        </body></html>
        """
        self.assertTrue(is_china_drug_trials_detail_page(html, "CTR20223406"))
        self.assertFalse(is_china_drug_trials_detail_page("<html>CTR20223406</html>", "CTR20223406"))

    def test_cde_waf_detail_html_is_not_saved_as_fetched(self):
        source = ChinaDrugTrialsSource()
        query = resolve_query("CTR20223406", source_hint="china_drug_trials")
        match = source.detail_match_from_url(
            query=query,
            detail_url="https://www.chinadrugtrials.org.cn/clinicaltrials.searchlistdetail.dhtml?id=fixture",
            match_key="CTR20223406",
        )
        html = """
        <html><head>
        <meta id="9DhefwqGPrzGxEp9hPaoag" content="LM&lt;challenge" />
        <script src="/4QbVtADbnLVIc/c.FxJzG50F.6152bb9.js?D9PVtGL=6152bb"></script>
        </head><body></body></html>
        """
        record = source.record_from_html(match, html)

        self.assertEqual(record.fetch_status, "blocked_by_site")
        self.assertEqual(record.fetch_note, "cde_waf_javascript_challenge")

    def test_cde_detail_fixture_can_be_saved_once_html_is_available(self):
        class FixtureChinaDrugTrialsSource(ChinaDrugTrialsSource):
            def search(self, query):
                html = (FIXTURE_DIR / "cde_search_CTR20223406.html").read_text(encoding="utf-8")
                matches = parse_china_drug_trials_search_results(html, query=query, source=self)
                for match in matches:
                    match.raw_summary["fetch_mode"] = "html"
                    match.raw_summary["fetch_status"] = "fetched"
                    match.raw_summary["fetch_note"] = ""
                return matches

            def fetch_html_for_match(self, match):
                return (FIXTURE_DIR / "cde_detail_CTR20223406.html").read_text(encoding="utf-8")

        original_cde = SOURCE_REGISTRY.get("china_drug_trials")
        SOURCE_REGISTRY["china_drug_trials"] = FixtureChinaDrugTrialsSource
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = run_query(
                    "CTR20223406",
                    source="china_drug_trials",
                    formats=["csv"],
                    output_root=tmpdir,
                    run_id="cde-fixture",
                )

                self.assertEqual(result.status, "saved")
                self.assertIn("csv", result.files)
                self.assertTrue((result.output_dir / "ChinaDrugTrials_protocol.json").exists())
                self.assertTrue((result.output_dir / "ChinaDrugTrials_raw.html").exists())
                protocol = json.loads((result.output_dir / "ChinaDrugTrials_protocol.json").read_text(encoding="utf-8"))
                self.assertEqual(protocol["fetch_status"], "fetched")
                self.assertEqual(protocol["registration_number"], "CTR20223406")
                self.assertIn("基本信息", protocol["protocol_sections"])
                self.assertIn("公示的试验信息", protocol["protocol_sections"])
        finally:
            if original_cde is not None:
                SOURCE_REGISTRY["china_drug_trials"] = original_cde

    def test_cde_browser_fallback_can_resolve_search_and_save_detail(self):
        class BrowserFallbackChinaDrugTrialsSource(ChinaDrugTrialsSource):
            def fetch_http_html(self, url):
                return (FIXTURE_DIR / "cde_blocked_CTR20223406.html").read_text(encoding="utf-8")

            def fetch_browser_html(self, url):
                if "searchlistdetail" in url:
                    return (FIXTURE_DIR / "cde_detail_CTR20223406.html").read_text(encoding="utf-8")
                return (FIXTURE_DIR / "cde_search_CTR20223406.html").read_text(encoding="utf-8")

        original_cde = SOURCE_REGISTRY.get("china_drug_trials")
        previous_live_search = os.environ.get("TRIAL_REGISTRY_DISABLE_LIVE_SEARCH")
        previous_cdp = os.environ.get("TRIAL_REGISTRY_ENABLE_CHROME_CDP")
        SOURCE_REGISTRY["china_drug_trials"] = BrowserFallbackChinaDrugTrialsSource
        os.environ["TRIAL_REGISTRY_DISABLE_LIVE_SEARCH"] = "0"
        os.environ["TRIAL_REGISTRY_ENABLE_CHROME_CDP"] = "1"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = run_query(
                    "CTR20223406",
                    source="china_drug_trials",
                    formats=["csv"],
                    output_root=tmpdir,
                    run_id="cde-browser-fixture",
                )

                self.assertEqual(result.status, "saved")
                self.assertIn("csv", result.files)
                self.assertTrue((result.output_dir / "ChinaDrugTrials_protocol.json").exists())
                self.assertTrue((result.output_dir / "ChinaDrugTrials_raw.html").exists())
                protocol = json.loads((result.output_dir / "ChinaDrugTrials_protocol.json").read_text(encoding="utf-8"))
                self.assertEqual(protocol["fetch_status"], "fetched")
                self.assertEqual(protocol["source_specific"]["urls"]["browser_fetch"], "chrome_cdp")
        finally:
            if previous_live_search is None:
                os.environ.pop("TRIAL_REGISTRY_DISABLE_LIVE_SEARCH", None)
            else:
                os.environ["TRIAL_REGISTRY_DISABLE_LIVE_SEARCH"] = previous_live_search
            if previous_cdp is None:
                os.environ.pop("TRIAL_REGISTRY_ENABLE_CHROME_CDP", None)
            else:
                os.environ["TRIAL_REGISTRY_ENABLE_CHROME_CDP"] = previous_cdp
            if original_cde is not None:
                SOURCE_REGISTRY["china_drug_trials"] = original_cde

    def test_registry_lookup_cases_fixture_matches_expected_urls(self):
        cases = json.loads((FIXTURE_DIR / "registry_lookup_cases.json").read_text(encoding="utf-8"))
        by_source = {case["source"]: case for case in cases}

        chictr_html = (FIXTURE_DIR / "chictr_search_ChiCTR2600126676.html").read_text(encoding="utf-8")
        chictr_query = resolve_query(by_source["chictr"]["registry_id"], source_hint="chictr")
        chictr_match = parse_chictr_search_results(chictr_html, query=chictr_query, source=ChictrSource())[0]
        self.assertEqual(chictr_match.detail_url, by_source["chictr"]["expected_url"])

        anzctr_html = (FIXTURE_DIR / "anzctr_search_ACTRN12626000671369.html").read_text(encoding="utf-8")
        anzctr_query = resolve_query(by_source["anzctr"]["registry_id"], source_hint="anzctr")
        anzctr_match = parse_anzctr_search_results(anzctr_html, query=anzctr_query, source=AnzctrSource())[0]
        self.assertEqual(anzctr_match.detail_url, by_source["anzctr"]["expected_url"])

        ctis_case = by_source["ctis"]
        self.assertEqual(CtisSource().urls_for_id(ctis_case["registry_id"])["search"], ctis_case["expected_url"])

        cde_case = by_source["china_drug_trials"]
        self.assertEqual(cde_case["expected_status"], "blocked_by_site")

    def test_fixture_detail_pages_are_saved_for_successful_sources(self):
        class FixtureChictrSource(ChictrSource):
            def search(self, query):
                html = (FIXTURE_DIR / "chictr_search_ChiCTR2600126676.html").read_text(encoding="utf-8")
                return parse_chictr_search_results(html, query=query, source=self)

            def fetch_html_for_match(self, match):
                return (FIXTURE_DIR / "chictr_detail_327816.html").read_text(encoding="utf-8")

        class FixtureAnzctrSource(AnzctrSource):
            def search(self, query):
                html = (FIXTURE_DIR / "anzctr_search_ACTRN12626000671369.html").read_text(encoding="utf-8")
                return parse_anzctr_search_results(html, query=query, source=self)

            def fetch_html_for_match(self, match):
                return (FIXTURE_DIR / "anzctr_detail_391548.html").read_text(encoding="utf-8")

        original_chictr = SOURCE_REGISTRY.get("chictr")
        original_anzctr = SOURCE_REGISTRY.get("anzctr")
        SOURCE_REGISTRY["chictr"] = FixtureChictrSource
        SOURCE_REGISTRY["anzctr"] = FixtureAnzctrSource
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                chictr_result = run_query(
                    "ChiCTR2600126676",
                    source="chictr",
                    formats=["csv"],
                    output_root=tmpdir,
                    run_id="chictr-fixture",
                )
                anzctr_result = run_query(
                    "ACTRN12626000671369",
                    source="anzctr",
                    formats=["csv"],
                    output_root=tmpdir,
                    run_id="anzctr-fixture",
                )

                self.assertEqual(chictr_result.status, "saved")
                self.assertIn("csv", chictr_result.files)
                self.assertTrue((chictr_result.output_dir / "ChiCTR_protocol.json").exists())
                self.assertTrue((chictr_result.output_dir / "ChiCTR_raw.html").exists())

                self.assertEqual(anzctr_result.status, "saved")
                self.assertIn("csv", anzctr_result.files)
                self.assertTrue((anzctr_result.output_dir / "ANZCTR_protocol.json").exists())
                self.assertTrue((anzctr_result.output_dir / "ANZCTR_raw.html").exists())
        finally:
            if original_chictr is not None:
                SOURCE_REGISTRY["chictr"] = original_chictr
            if original_anzctr is not None:
                SOURCE_REGISTRY["anzctr"] = original_anzctr

    def test_ctis_frontend_shell_does_not_generate_result_files(self):
        html = (FIXTURE_DIR / "ctis_search_2025-523616-36-00.html").read_text(encoding="utf-8")
        self.assertFalse(ctis_page_has_trial_content(html, "2025-523616-36-00"))

    def test_parse_ctis_api_response_to_api_match(self):
        raw = json.loads((FIXTURE_DIR / "ctis_api_2025-523616-36-00.json").read_text(encoding="utf-8"))
        query = resolve_query("2025-523616-36-00", source_hint="ctis")
        matches = parse_ctis_search_response(raw, query=query, source=CtisSource())

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].match_key, "2025-523616-36-00")
        self.assertEqual(matches[0].raw_summary["fetch_mode"], "ctis_api")
        self.assertEqual(matches[0].raw_summary["fetch_status"], "fetched")
        self.assertEqual(
            matches[0].detail_url,
            "https://euclinicaltrials.eu/ctis-public/view/2025-523616-36-00?lang=en",
        )

    def test_ctis_api_fixture_can_be_saved(self):
        class FixtureCtisSource(CtisSource):
            def search(self, query):
                raw = json.loads((FIXTURE_DIR / "ctis_api_2025-523616-36-00.json").read_text(encoding="utf-8"))
                return parse_ctis_search_response(raw, query=query, source=self)

        original_ctis = SOURCE_REGISTRY.get("ctis")
        SOURCE_REGISTRY["ctis"] = FixtureCtisSource
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = run_query(
                    "2025-523616-36-00",
                    source="ctis",
                    formats=["csv"],
                    output_root=tmpdir,
                    run_id="ctis-api-fixture",
                )

                self.assertEqual(result.status, "saved")
                self.assertIn("csv", result.files)
                self.assertTrue((result.output_dir / "CTIS_protocol.json").exists())
                self.assertTrue((result.output_dir / "CTIS_raw.json").exists())

                protocol = json.loads((result.output_dir / "CTIS_protocol.json").read_text(encoding="utf-8"))
                self.assertEqual(protocol["fetch_status"], "fetched")
                self.assertEqual(protocol["registration_number"], "2025-523616-36-00")
                self.assertIn("search_result_summary", protocol["protocol_sections"])
                self.assertIn("outcomes_and_results", protocol["results_sections"])
                self.assertIn("raw_json", protocol["raw_evidence_files"])
        finally:
            if original_ctis is not None:
                SOURCE_REGISTRY["ctis"] = original_ctis

    def test_ctis_visible_trial_page_can_be_saved(self):
        class FixtureCtisSource(CtisSource):
            def search(self, query):
                return [
                    self.detail_match_from_url(
                        query=query,
                        detail_url=self.urls_for_id(query.raw_input)["search"],
                        match_key=query.raw_input,
                        raw_summary={"search": self.urls_for_id(query.raw_input)["search"]},
                    )
                ]

            def fetch_html_for_match(self, match):
                return (FIXTURE_DIR / "ctis_visible_2025-523616-36-00.html").read_text(encoding="utf-8")

        original_ctis = SOURCE_REGISTRY.get("ctis")
        SOURCE_REGISTRY["ctis"] = FixtureCtisSource
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = run_query(
                    "2025-523616-36-00",
                    source="ctis",
                    formats=["csv"],
                    output_root=tmpdir,
                    run_id="ctis-fixture",
                )

                self.assertEqual(result.status, "saved")
                self.assertIn("csv", result.files)
                self.assertTrue((result.output_dir / "CTIS_protocol.json").exists())
                self.assertTrue((result.output_dir / "CTIS_raw.html").exists())
        finally:
            if original_ctis is not None:
                SOURCE_REGISTRY["ctis"] = original_ctis

    def test_cde_blocked_status_does_not_write_result_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_query(
                "CTR20223406",
                source="china_drug_trials",
                formats=["csv"],
                output_root=tmpdir,
                run_id="cde-blocked",
            )
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(result.status, "blocked_by_site")
            self.assertEqual(result.files, {})
            self.assertFalse((result.output_dir / "cde-blocked.csv").exists())
            self.assertFalse((result.output_dir / "ChinaDrugTrials_protocol.json").exists())
            self.assertEqual(manifest["saved_count"], 0)

    def test_parse_euctr_search_result_to_multiple_detail_urls(self):
        html = """
        <html><body><table>
        <tr><td>2015-005614-30</td><td><a href="/ctr-search/trial/2015-005614-30/ES">Spain</a></td></tr>
        <tr><td>2015-005614-30</td><td><a href="/ctr-search/trial/2015-005614-30/DE">Germany</a></td></tr>
        </table></body></html>
        """
        query = resolve_query("EudraCT 2015-005614-30", source_hint="euctr")
        matches = parse_euctr_search_results(html, query=query, source=EuCtrSource())

        self.assertEqual(len(matches), 2)
        self.assertEqual([match.match_rank for match in matches], [1, 2])
        self.assertTrue(matches[0].detail_url.endswith("/ctr-search/trial/2015-005614-30/ES"))
        self.assertTrue(matches[1].detail_url.endswith("/ctr-search/trial/2015-005614-30/DE"))

    def test_link_based_detail_html_writes_raw_evidence_and_result_sections(self):
        html = """
        <html><head><title>ISRCTN Test Trial</title></head><body>
        <h1>Trial summary</h1>
        <table><tr><th>Condition</th><td>Colorectal cancer</td></tr></table>
        <h2>Results and publications</h2>
        <p>Results were posted on the registry.</p>
        </body></html>
        """
        source = IsrctnSource()
        query = resolve_query("https://www.isrctn.com/ISRCTN12345678", source_hint=source.name)
        match = source.search(query)[0]
        record = source.record_from_html(match, html)

        with tempfile.TemporaryDirectory() as tmpdir:
            files = source.write_sidecar_files(record, output_dir=Path(tmpdir))
            protocol = json.loads(files["isrctn_protocol"].read_text(encoding="utf-8"))

        self.assertEqual(protocol["fetch_status"], "fetched")
        self.assertIn("raw_html", protocol["raw_evidence_files"])
        self.assertIn("raw_text", protocol["raw_evidence_files"])
        self.assertIn("Results and publications", protocol["results_sections"])
        self.assertIn("Trial summary", protocol["protocol_sections"])

    def test_detail_urls_can_be_used_as_batch_input(self):
        item = parse_txt_line(
            "- paper.pdf: https://www.anzctr.org.au/Trial/Registration/TrialReview.aspx?id=391548",
            "- paper.pdf: https://www.anzctr.org.au/Trial/Registration/TrialReview.aspx?id=391548",
        )
        self.assertEqual(item.status, "ready")
        self.assertEqual(item.registry_type, "anzctr")
        self.assertEqual(item.source_hint, "anzctr")

    def test_sources_are_registered(self):
        for name in ["isrctn", "chictr", "china_drug_trials", "anzctr", "euctr", "ctis"]:
            self.assertIn(name, SOURCE_REGISTRY)


if __name__ == "__main__":
    unittest.main()
