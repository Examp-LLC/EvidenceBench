import unittest

from evidencebench.citations import citation_exists, normalize_citation


class CitationTests(unittest.TestCase):
    def test_normalizes_common_forms(self):
        self.assertEqual(normalize_citation("Fed. R. Evid. 801(C)"), "FRE 801(c)")
        self.assertEqual(normalize_citation("Rule 901(b)(5)"), "FRE 901(b)(5)")

    def test_rejects_nonexistent_rules_and_subsections(self):
        self.assertTrue(citation_exists("FRE 801(c)"))
        self.assertFalse(citation_exists("FRE 801(z)"))
        self.assertFalse(citation_exists("FRE 999"))

    def test_normalizes_case_reporter_citations(self):
        self.assertEqual(normalize_citation("Daubert, 509 U.S. 579 (1993)"), "509 U.S. 579")
        self.assertEqual(normalize_citation("55 Cal.4th 747"), "55 Cal. 4th 747")
        self.assertEqual(normalize_citation("Parker, 7 NY3d 434"), "7 N.Y.3d 434")
        self.assertTrue(citation_exists("208 N.J. 208"))
        self.assertFalse(citation_exists("999 U.S. 999"))

    def test_normalizes_recent_data_gov_case_citations(self):
        self.assertEqual(normalize_citation("People v. Prante, 223 N.E. 3d 160"), "223 N.E.3d 160")
        self.assertEqual(normalize_citation("Hunt, 63 F.4th 1229"), "63 F.4th 1229")
        self.assertEqual(normalize_citation("2022-Ohio-1739"), "2022-Ohio-1739")
        self.assertEqual(
            normalize_citation("Briscoe, 2023 U.S. Dist. LEXIS 208806"),
            "2023 U.S. Dist. LEXIS 208806",
        )
        self.assertTrue(citation_exists("2024 Cal. App. LEXIS 532"))

    def test_normalizes_current_slip_and_docket_citations(self):
        self.assertEqual(normalize_citation("Ruffin, No. 23-30854 (5th Cir. 2026)"), "No. 23-30854")
        self.assertEqual(normalize_citation("2026 NY Slip Op 26043"), "2026 NY Slip Op 26043")
        self.assertTrue(citation_exists("No. 24-1907"))
        self.assertTrue(citation_exists("2026 NY Slip Op 26081"))
