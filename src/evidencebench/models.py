from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CitationAnnotation:
    required_groups: list[list[str]]
    accepted: list[str]


@dataclass(frozen=True)
class Question:
    id: str
    category: str
    difficulty: str
    stem: str
    options: list[dict[str, str]]
    gold_choice_id: str
    rationale: str
    citations: CitationAnnotation
    corpus_version: str
    attorney_review_status: str
    dimensions: dict[str, str] | None = None

    @classmethod
    def from_dict(cls, payload: dict) -> "Question":
        citation_payload = payload["citations"]
        return cls(
            id=payload["id"],
            category=payload["category"],
            difficulty=payload["difficulty"],
            stem=payload["stem"],
            options=payload["options"],
            gold_choice_id=payload["gold_choice_id"],
            rationale=payload["rationale"],
            citations=CitationAnnotation(
                required_groups=citation_payload["required_groups"],
                accepted=citation_payload["accepted"],
            ),
            corpus_version=payload["corpus_version"],
            attorney_review_status=payload["attorney_review_status"],
            dimensions=payload.get("dimensions"),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ModelResponse:
    question_id: str
    choice_id: str | None
    explanation: str
    citations: list[str]
    status: str = "ok"

    @classmethod
    def from_dict(cls, payload: dict) -> "ModelResponse":
        return cls(
            question_id=payload["question_id"],
            choice_id=payload.get("choice_id"),
            explanation=payload.get("explanation", ""),
            citations=payload.get("citations", []),
            status=payload.get("status", "ok"),
        )


@dataclass(frozen=True)
class ItemScore:
    question_id: str
    answer_accuracy: float
    citation_precision: float
    citation_recall: float
    citation_f1: float
    citation_count: int
    hallucinated_citations: list[str]
    unsupported_citations: list[str]
    status: str
