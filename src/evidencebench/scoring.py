from __future__ import annotations

from collections import defaultdict

from .citations import citation_exists, normalize_many
from .models import ItemScore, ModelResponse, Question


def score_item(question: Question, response: ModelResponse) -> ItemScore:
    if response.status != "ok":
        return ItemScore(question.id, 0, 0, 0, 0, 0, [], [], response.status)
    citations = normalize_many(response.citations)
    existing = [citation for citation in citations if citation_exists(citation)]
    hallucinated = [citation for citation in citations if citation not in existing]
    accepted = set(normalize_many(question.citations.accepted))
    supported = [citation for citation in existing if citation in accepted]
    unsupported = [citation for citation in existing if citation not in accepted]
    precision = len(supported) / len(citations) if citations else 0.0
    groups = [set(normalize_many(group)) for group in question.citations.required_groups]
    recall = (
        sum(bool(group.intersection(supported)) for group in groups) / len(groups)
        if groups
        else 1.0
    )
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return ItemScore(
        question_id=question.id,
        answer_accuracy=float(response.choice_id == question.gold_choice_id),
        citation_precision=precision,
        citation_recall=recall,
        citation_f1=f1,
        citation_count=len(citations),
        hallucinated_citations=hallucinated,
        unsupported_citations=unsupported,
        status="ok",
    )


def aggregate(scores: list[ItemScore], questions: list[Question]) -> dict:
    by_category: dict[str, list[ItemScore]] = defaultdict(list)
    by_dimension: dict[str, dict[str, list[ItemScore]]] = defaultdict(lambda: defaultdict(list))
    category_by_id = {question.id: question.category for question in questions}
    question_by_id = {question.id: question for question in questions}
    for score in scores:
        category = category_by_id[score.question_id]
        by_category[category].append(score)
        if category.startswith("caselaw_"):
            by_dimension["domain"]["caselaw"].append(score)
            question = question_by_id[score.question_id]
            dimensions = question.dimensions or dict(
                zip(
                    ("jurisdiction", "proceeding", "familiarity"),
                    category.split("_")[1:],
                    strict=True,
                )
            )
            for dimension, value in dimensions.items():
                by_dimension[dimension][value].append(score)
        else:
            by_dimension["domain"]["fre"].append(score)

    def summarize(items: list[ItemScore]) -> dict:
        count = len(items) or 1
        accuracy = sum(item.answer_accuracy for item in items) / count
        citation_f1 = sum(item.citation_f1 for item in items) / count
        citations = [citation for item in items for citation in item.hallucinated_citations]
        cited_total = sum(item.citation_count for item in items)
        hallucination_rate = len(citations) / cited_total if cited_total else 0.0
        unsupported = sum(len(item.unsupported_citations) for item in items)
        return {
            "count": len(items),
            "answer_accuracy": round(accuracy, 4),
            "citation_f1": round(citation_f1, 4),
            "hallucination_rate": round(hallucination_rate, 4),
            "unsupported_citation_count": unsupported,
            "overall": round(0.70 * accuracy + 0.30 * citation_f1, 4),
        }

    return {
        "overall": summarize(scores),
        "categories": {key: summarize(value) for key, value in sorted(by_category.items())},
        "dimensions": {
            dimension: {key: summarize(value) for key, value in sorted(groups.items())}
            for dimension, groups in sorted(by_dimension.items())
        },
    }
