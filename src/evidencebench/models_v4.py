from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewRecord:
    status: str
    author_id: str | None = None
    reviewer_ids: list[str] = field(default_factory=list)
    adjudicator_id: str | None = None
    reviewed_at: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReviewRecord":
        return cls(
            status=payload["status"],
            author_id=payload.get("author_id"),
            reviewer_ids=list(payload.get("reviewer_ids", [])),
            adjudicator_id=payload.get("adjudicator_id"),
            reviewed_at=payload.get("reviewed_at"),
        )


@dataclass(frozen=True)
class Fact:
    id: str
    text: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Fact":
        return cls(id=payload["id"], text=payload["text"])


@dataclass(frozen=True)
class GroundingAnnotation:
    issue_code: str
    fact_ids: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GroundingAnnotation":
        return cls(
            issue_code=payload["issue_code"],
            fact_ids=list(payload["fact_ids"]),
        )


@dataclass(frozen=True)
class DoctrineGold:
    ruling: str
    issue_codes: list[str]
    required_authority_groups: list[list[str]]
    accepted_authorities: list[str]
    grounding: list[GroundingAnnotation]
    rationale: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DoctrineGold":
        return cls(
            ruling=payload["ruling"],
            issue_codes=list(payload["issue_codes"]),
            required_authority_groups=[
                list(group) for group in payload["required_authority_groups"]
            ],
            accepted_authorities=list(payload["accepted_authorities"]),
            grounding=[
                GroundingAnnotation.from_dict(item)
                for item in payload.get("grounding", [])
            ],
            rationale=payload["rationale"],
        )


@dataclass(frozen=True)
class DoctrineItem:
    schema_version: str
    track: str
    id: str
    family_id: str
    category: str
    difficulty: str
    jurisdiction: str
    stem: str
    facts: list[Fact]
    allowed_rulings: list[str]
    gold: DoctrineGold
    corpus_version: str
    review: ReviewRecord
    domain: str = ""
    legacy_source_id: str | None = None
    coverage_cell: str | None = None
    dimensions: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DoctrineItem":
        return cls(
            schema_version=payload["schema_version"],
            track=payload["track"],
            id=payload["id"],
            family_id=payload["family_id"],
            category=payload["category"],
            difficulty=payload["difficulty"],
            jurisdiction=payload["jurisdiction"],
            stem=payload["stem"],
            facts=[Fact.from_dict(item) for item in payload["facts"]],
            allowed_rulings=list(payload["allowed_rulings"]),
            gold=DoctrineGold.from_dict(payload["gold"]),
            corpus_version=payload["corpus_version"],
            review=ReviewRecord.from_dict(payload["review"]),
            domain=payload.get(
                "domain", payload.get("dimensions", {}).get("domain", payload["category"])
            ),
            legacy_source_id=payload.get("legacy_source_id"),
            coverage_cell=payload.get("coverage_cell"),
            dimensions=dict(payload.get("dimensions", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DoctrineGrounding:
    issue_code: str
    fact_ids: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DoctrineGrounding":
        return cls(
            issue_code=payload["issue_code"],
            fact_ids=list(payload.get("fact_ids", [])),
        )


@dataclass(frozen=True)
class DoctrineResponse:
    item_id: str
    ruling: str | None
    issue_codes: list[str]
    authorities: list[str]
    grounding: list[DoctrineGrounding]
    confidence: float | None
    status: str = "ok"
    explanation: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DoctrineResponse":
        return cls(
            item_id=payload["item_id"],
            ruling=payload.get("ruling"),
            issue_codes=list(payload.get("issue_codes", [])),
            authorities=list(payload.get("authorities", [])),
            grounding=[
                DoctrineGrounding.from_dict(item)
                for item in payload.get("grounding", [])
            ],
            confidence=payload.get("confidence"),
            status=payload.get("status", "ok"),
            explanation=payload.get("explanation", ""),
        )


@dataclass(frozen=True)
class DoctrineItemScore:
    item_id: str
    family_id: str
    domain: str
    outcome_accuracy: float
    issue_precision: float
    issue_recall: float
    issue_f1: float
    authority_precision: float
    authority_recall: float
    authority_f1: float
    grounding_precision: float
    grounding_recall: float
    grounding_f1: float
    calibration: float
    invalid_authorities: list[str]
    hallucinated_authorities: list[str]
    unsupported_authorities: list[str]
    doctrine_score: float
    status: str


@dataclass(frozen=True)
class MatterDocument:
    path: str
    sha256: str
    canonical_text_path: str | None = None
    canonical_text_sha256: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MatterDocument":
        return cls(
            path=payload["path"],
            sha256=payload["sha256"],
            canonical_text_path=payload.get("canonical_text_path"),
            canonical_text_sha256=payload.get("canonical_text_sha256"),
        )


@dataclass(frozen=True)
class MatterGoldFinding:
    issue_code: str
    accepted_dispositions: list[str]
    required_fact_ids: list[str]
    accepted_fact_ids: list[str]
    required_record_refs: list[str]
    accepted_record_refs: list[str]
    required_authority_groups: list[list[str]]
    accepted_authorities: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MatterGoldFinding":
        return cls(
            issue_code=payload["issue_code"],
            accepted_dispositions=list(payload["accepted_dispositions"]),
            required_fact_ids=list(payload.get("required_fact_ids", [])),
            accepted_fact_ids=list(payload.get("accepted_fact_ids", [])),
            required_record_refs=list(payload.get("required_record_refs", [])),
            accepted_record_refs=list(payload.get("accepted_record_refs", [])),
            required_authority_groups=[
                list(group)
                for group in payload.get("required_authority_groups", [])
            ],
            accepted_authorities=list(payload.get("accepted_authorities", [])),
        )


@dataclass(frozen=True)
class MatterCriterion:
    id: str
    dimension: str
    title: str
    issue_code: str | None = None
    expected_disposition: str | None = None
    required_fact_ids: list[str] = field(default_factory=list)
    required_record_refs: list[str] = field(default_factory=list)
    required_authority_groups: list[list[str]] = field(default_factory=list)
    accepted_authorities: list[str] = field(default_factory=list)
    deliverable: str | None = None
    min_bytes: int = 1
    required_sections: list[str] = field(default_factory=list)
    critical: bool = True
    review_only: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MatterCriterion":
        return cls(
            id=payload["id"],
            dimension=payload["dimension"],
            title=payload["title"],
            issue_code=payload.get("issue_code"),
            expected_disposition=payload.get("expected_disposition"),
            required_fact_ids=list(payload.get("required_fact_ids", [])),
            required_record_refs=list(payload.get("required_record_refs", [])),
            required_authority_groups=[
                list(group)
                for group in payload.get("required_authority_groups", [])
            ],
            accepted_authorities=list(payload.get("accepted_authorities", [])),
            deliverable=payload.get("deliverable"),
            min_bytes=payload.get("min_bytes", 1),
            required_sections=list(payload.get("required_sections", [])),
            critical=payload.get("critical", True),
            review_only=payload.get("review_only", False),
        )


@dataclass(frozen=True)
class MatterTask:
    schema_version: str
    track: str
    id: str
    family_id: str
    title: str
    task_type: str
    instructions: str
    documents: list[MatterDocument]
    deliverables: list[str]
    criteria: list[MatterCriterion]
    corpus_version: str
    review: ReviewRecord
    domain: str = ""
    jurisdiction: str = "federal"
    gold_findings: list[MatterGoldFinding] = field(default_factory=list)
    legacy_source_id: str | None = None
    coverage_cell: str | None = None
    dimensions: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MatterTask":
        return cls(
            schema_version=payload["schema_version"],
            track=payload["track"],
            id=payload["id"],
            family_id=payload["family_id"],
            title=payload["title"],
            task_type=payload["task_type"],
            instructions=payload["instructions"],
            documents=[
                MatterDocument.from_dict(item) for item in payload["documents"]
            ],
            deliverables=list(payload["deliverables"]),
            criteria=[
                MatterCriterion.from_dict(item) for item in payload["criteria"]
            ],
            corpus_version=payload["corpus_version"],
            review=ReviewRecord.from_dict(payload["review"]),
            domain=payload.get(
                "domain",
                payload.get("dimensions", {}).get("domain", payload["task_type"]),
            ),
            jurisdiction=payload.get(
                "jurisdiction",
                payload.get("dimensions", {}).get("jurisdiction", "federal"),
            ),
            gold_findings=[
                MatterGoldFinding.from_dict(item)
                for item in payload.get("gold_findings", [])
            ],
            legacy_source_id=payload.get("legacy_source_id"),
            coverage_cell=payload.get("coverage_cell"),
            dimensions=dict(payload.get("dimensions", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MatterFinding:
    issue_code: str
    disposition: str | None
    fact_ids: list[str]
    record_refs: list[str]
    authorities: list[str]
    explanation: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MatterFinding":
        return cls(
            issue_code=payload["issue_code"],
            disposition=payload.get("disposition"),
            fact_ids=list(payload.get("fact_ids", [])),
            record_refs=list(payload.get("record_refs", [])),
            authorities=list(payload.get("authorities", [])),
            explanation=payload.get("explanation", ""),
        )


@dataclass(frozen=True)
class MatterResponse:
    task_id: str
    findings: list[MatterFinding]
    deliverables: list[str]
    status: str = "ok"
    deliverable_metadata: list["MatterDeliverableMetadata"] = field(
        default_factory=list
    )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MatterResponse":
        return cls(
            task_id=payload["task_id"],
            findings=[
                MatterFinding.from_dict(item)
                for item in payload.get("findings", [])
            ],
            deliverables=list(payload.get("deliverables", [])),
            deliverable_metadata=[
                MatterDeliverableMetadata.from_dict(item)
                for item in payload.get("deliverable_metadata", [])
            ],
            status=payload.get("status", "ok"),
        )


@dataclass(frozen=True)
class MatterDeliverableMetadata:
    path: str
    bytes: int
    sha256: str
    sections: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MatterDeliverableMetadata":
        return cls(
            path=payload["path"],
            bytes=int(payload["bytes"]),
            sha256=payload["sha256"],
            sections=list(payload.get("sections", [])),
        )


@dataclass(frozen=True)
class MatterCriterionScore:
    criterion_id: str
    dimension: str
    passed: bool
    critical: bool
    review_only: bool


@dataclass(frozen=True)
class MatterTaskScore:
    task_id: str
    family_id: str
    domain: str
    legal_criteria_rate: float
    legal_precision: float
    legal_recall: float
    authority_grounding_rate: float
    authority_precision: float
    authority_recall: float
    factual_accuracy_rate: float
    factual_precision: float
    factual_recall: float
    deliverable_completeness_rate: float
    matter_score: float
    complete_task: bool
    criteria: list[MatterCriterionScore]
    invalid_authorities: list[str]
    hallucinated_authorities: list[str]
    status: str
