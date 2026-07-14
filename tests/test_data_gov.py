import json
import runpy
import unittest
from pathlib import Path

from evidencebench.citations import citation_exists
from evidencebench.data_gov import canonical_case_citation, parse_decision_date, recent_published_records


ROOT = Path(__file__).resolve().parents[1]


class DataGovCaselawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads((ROOT / "data/doj-nij-post-pcast-2024.json").read_text())
        cls.selected = recent_published_records(cls.snapshot)

    def test_frozen_snapshot_and_selection_counts(self):
        self.assertEqual(self.snapshot["record_count"], 124)
        self.assertEqual(
            self.snapshot["records_sha256"],
            "90990eb660d45be39515f9f08278abd4b080be3ce758eb1cf9e8854cc5ab95f1",
        )
        self.assertEqual(len(self.selected), 33)
        self.assertEqual(len({row["caption"] for row in self.selected}), 33)

    def test_selection_is_recent_published_and_citable(self):
        self.assertEqual({row["decision_date"][:4] for row in self.selected}, {"2020", "2021", "2022", "2023", "2024"})
        self.assertTrue(all(row["publication_status"].startswith("Pub") for row in self.selected))
        self.assertTrue(all(row["case_citation"] for row in self.selected))
        self.assertTrue(all(citation_exists(row["case_citation"]) for row in self.selected))

    def test_federal_state_and_discipline_coverage(self):
        jurisdictions = {
            "federal" if row["jurisdiction"].startswith("Federal") else "state"
            for row in self.selected
        }
        self.assertEqual(jurisdictions, {"federal", "state"})
        self.assertGreaterEqual(len({row["discipline"] for row in self.selected}), 6)

    def test_source_anomalies_are_not_selected(self):
        captions = {row["caption"] for row in self.selected}
        self.assertFalse(any("U.S. v. Abarca" in caption for caption in captions))
        self.assertEqual(sum("People v. Wakefield" in caption for caption in captions), 1)

    def test_excel_date_and_citation_normalization(self):
        self.assertEqual(parse_decision_date("44677").isoformat(), "2022-04-26")
        self.assertEqual(canonical_case_citation("People v. Prante, 223 N.E. 3d 160"), "223 N.E.3d 160")
        self.assertEqual(canonical_case_citation("U.S. v. Hunt, 63 F.4th 1229"), "63 F.4th 1229")
        self.assertEqual(
            canonical_case_citation("U.S. v. Briscoe, 2023 U.S. Dist. LEXIS 208806"),
            "2023 U.S. Dist. LEXIS 208806",
        )

    def test_sealed_questions_do_not_leak_required_citations(self):
        build_questions = runpy.run_path(ROOT / "scripts/build_holdout_v3.py")["build_questions"]
        questions = build_questions(self.snapshot)
        self.assertEqual(len(questions), 33)
        self.assertTrue(all(len(question["options"]) == 4 for question in questions))
        self.assertTrue(all(question["attorney_review_status"] == "APPROVED" for question in questions))
        self.assertTrue(
            all(question["citations"]["accepted"][0] not in question["stem"] for question in questions)
        )

    def test_recent_2026_source_is_official_and_multidimensional(self):
        source = json.loads((ROOT / "data/recent-caselaw-2026.json").read_text())
        self.assertEqual(len(source["records"]), 6)
        self.assertEqual({row["decision_date"][:4] for row in source["records"]}, {"2026"})
        self.assertEqual({row["jurisdiction"] for row in source["records"]}, {"federal", "state"})
        self.assertEqual({row["proceeding"] for row in source["records"]}, {"civil", "criminal"})
        self.assertTrue(all(citation_exists(row["citation"]) for row in source["records"]))
        self.assertTrue(
            all(
                any(host in row["source_url"] for host in ("uscourts.gov", "govinfo.gov", "nycourts.gov"))
                for row in source["records"]
            )
        )
