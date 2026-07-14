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
