import unittest

from evidencebench.models import CitationAnnotation, ModelResponse, Question
from evidencebench.scoring import aggregate, score_item


def sample_question():
    return Question(
        id="EB-T-001",
        category="hearsay",
        difficulty="easy",
        stem="test",
        options=[{"id": "A", "text": "A"}, {"id": "B", "text": "B"}],
        gold_choice_id="A",
        rationale="test",
        citations=CitationAnnotation([["FRE 801(c)"]], ["FRE 801(c)", "FRE 802"]),
        corpus_version="FRE-2025-12-01",
        attorney_review_status="APPROVED",
    )


class ScoringTests(unittest.TestCase):
    def test_correct_supported_answer(self):
        score = score_item(sample_question(), ModelResponse("EB-T-001", "A", "", ["Rule 801(c)"]))
        self.assertEqual(score.answer_accuracy, 1)
        self.assertEqual(score.citation_f1, 1)

    def test_extra_and_hallucinated_citations_reduce_precision(self):
        score = score_item(sample_question(), ModelResponse("EB-T-001", "A", "", ["FRE 801(c)", "FRE 403", "FRE 999"]))
        self.assertAlmostEqual(score.citation_precision, 1 / 3)
        self.assertEqual(score.hallucinated_citations, ["FRE 999"])
        self.assertEqual(score.unsupported_citations, ["FRE 403"])

    def test_missing_and_invalid_output_score_zero(self):
        score = score_item(sample_question(), ModelResponse("EB-T-001", None, "", [], "invalid_json"))
        self.assertEqual(score.answer_accuracy, 0)
        self.assertEqual(score.citation_f1, 0)

    def test_case_reporter_citation_scores_as_supported_authority(self):
        question = Question(
            **{
                **sample_question().__dict__,
                "id": "EB-CASE-CITE",
                "category": "caselaw_federal_civil_popular",
                "citations": CitationAnnotation([["509 U.S. 579"]], ["509 U.S. 579", "FRE 702"]),
            }
        )
        score = score_item(
            question,
            ModelResponse(question.id, "A", "", ["Daubert, 509 US 579 (1993)"]),
        )
        self.assertEqual(score.citation_f1, 1)
        self.assertEqual(score.hallucinated_citations, [])

    def test_aggregate_uses_overall_formula(self):
        question = sample_question()
        result = aggregate([score_item(question, ModelResponse("EB-T-001", "A", "", ["FRE 801(c)"]))], [question])
        self.assertEqual(result["overall"]["overall"], 1)
        self.assertEqual(result["dimensions"]["domain"]["fre"]["count"], 1)

    def test_aggregate_exposes_caselaw_dimensions(self):
        question = Question(
            **{**sample_question().__dict__, "id": "EB-CASE-T", "category": "caselaw_state_criminal_obscure"}
        )
        score = score_item(question, ModelResponse(question.id, "A", "", ["FRE 801(c)"]))
        result = aggregate([score], [question])
        self.assertEqual(result["dimensions"]["domain"]["caselaw"]["count"], 1)
        self.assertEqual(result["dimensions"]["jurisdiction"]["state"]["count"], 1)
        self.assertEqual(result["dimensions"]["proceeding"]["criminal"]["count"], 1)
        self.assertEqual(result["dimensions"]["familiarity"]["obscure"]["count"], 1)

    def test_aggregate_exposes_explicit_data_gov_dimensions(self):
        question = Question(
            **{
                **sample_question().__dict__,
                "id": "EB-DG-T",
                "category": "caselaw_state_criminal_obscure",
                "dimensions": {
                    "jurisdiction": "state",
                    "proceeding": "criminal",
                    "familiarity": "obscure",
                    "decision_year": "2024",
                    "source": "data_gov_doj_nij",
                },
            }
        )
        score = score_item(question, ModelResponse(question.id, "A", "", ["FRE 801(c)"]))
        result = aggregate([score], [question])
        self.assertEqual(result["dimensions"]["decision_year"]["2024"]["count"], 1)
        self.assertEqual(result["dimensions"]["source"]["data_gov_doj_nij"]["count"], 1)
