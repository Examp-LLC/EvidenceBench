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

    def test_aggregate_uses_overall_formula(self):
        question = sample_question()
        result = aggregate([score_item(question, ModelResponse("EB-T-001", "A", "", ["FRE 801(c)"]))], [question])
        self.assertEqual(result["overall"]["overall"], 1)
