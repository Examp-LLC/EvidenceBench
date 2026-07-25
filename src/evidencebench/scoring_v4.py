from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from typing import Iterable

from .citations import citation_exists, normalize_citation
from .models_v4 import (
    DoctrineItem,
    DoctrineItemScore,
    DoctrineResponse,
    MatterCriterion,
    MatterCriterionScore,
    MatterFinding,
    MatterResponse,
    MatterTask,
    MatterTaskScore,
)


DOCTRINE_WEIGHTS = {
    "outcome_accuracy": 0.40,
    "issue_f1": 0.25,
    "authority_f1": 0.20,
    "grounding_f1": 0.10,
    "calibration": 0.05,
}

MATTER_WEIGHTS = {
    "legal": 0.50,
    "authority": 0.20,
    "fact": 0.15,
    "deliverable": 0.15,
}


def _normalized_codes(values: Iterable[str]) -> set[str]:
    return {value.strip().upper() for value in values if value.strip()}


def _precision_recall_f1(
    predicted: set[object], expected: set[object]
) -> tuple[float, float, float]:
    true_positive = len(predicted.intersection(expected))
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(expected) if expected else 1.0
    f1 = (
        0.0
        if precision + recall == 0
        else 2 * precision * recall / (precision + recall)
    )
    return precision, recall, f1


def _authority_score(
    submitted: Iterable[str],
    accepted_values: Iterable[str],
    required_groups: Iterable[Iterable[str]],
) -> tuple[float, float, float, list[str], list[str], list[str]]:
    canonical_submissions: dict[str, str] = {}
    invalid: list[str] = []
    for raw_value in submitted:
        raw = raw_value.strip()
        if not raw:
            continue
        normalized = normalize_citation(raw)
        if normalized is None:
            invalid.append(raw)
            canonical_submissions.setdefault(f"INVALID::{raw.casefold()}", raw)
        else:
            canonical_submissions.setdefault(normalized, raw)

    accepted = {
        normalized
        for value in accepted_values
        if (normalized := normalize_citation(value)) is not None
    }
    supported = {
        value for value in canonical_submissions if value in accepted
    }
    hallucinated = sorted(
        original
        for normalized, original in canonical_submissions.items()
        if not normalized.startswith("INVALID::")
        and normalized not in accepted
        and not citation_exists(normalized)
    )
    unsupported = sorted(
        original
        for normalized, original in canonical_submissions.items()
        if not normalized.startswith("INVALID::")
        and normalized not in accepted
        and citation_exists(normalized)
    )
    precision = (
        len(supported) / len(canonical_submissions)
        if canonical_submissions
        else 0.0
    )
    normalized_groups = [
        {
            normalized
            for value in group
            if (normalized := normalize_citation(value)) is not None
        }
        for group in required_groups
    ]
    recall = (
        sum(bool(group.intersection(supported)) for group in normalized_groups)
        / len(normalized_groups)
        if normalized_groups
        else 1.0
    )
    f1 = (
        0.0
        if precision + recall == 0
        else 2 * precision * recall / (precision + recall)
    )
    return precision, recall, f1, sorted(set(invalid)), hallucinated, unsupported


def score_doctrine_item(
    item: DoctrineItem, response: DoctrineResponse
) -> DoctrineItemScore:
    if response.status != "ok":
        return DoctrineItemScore(
            item_id=item.id,
            family_id=item.family_id,
            outcome_accuracy=0.0,
            issue_precision=0.0,
            issue_recall=0.0,
            issue_f1=0.0,
            authority_precision=0.0,
            authority_recall=0.0,
            authority_f1=0.0,
            grounding_precision=0.0,
            grounding_recall=0.0,
            grounding_f1=0.0,
            calibration=0.0,
            invalid_authorities=[],
            hallucinated_authorities=[],
            unsupported_authorities=[],
            doctrine_score=0.0,
            status=response.status,
        )

    outcome = float(response.ruling == item.gold.ruling)
    issue_precision, issue_recall, issue_f1 = _precision_recall_f1(
        _normalized_codes(response.issue_codes),
        _normalized_codes(item.gold.issue_codes),
    )
    (
        authority_precision,
        authority_recall,
        authority_f1,
        invalid,
        hallucinated,
        unsupported,
    ) = _authority_score(
        response.authorities,
        item.gold.accepted_authorities,
        item.gold.required_authority_groups,
    )
    predicted_grounding = {
        (entry.issue_code.strip().upper(), fact_id.strip().upper())
        for entry in response.grounding
        for fact_id in entry.fact_ids
        if entry.issue_code.strip() and fact_id.strip()
    }
    expected_grounding = {
        (entry.issue_code.strip().upper(), fact_id.strip().upper())
        for entry in item.gold.grounding
        for fact_id in entry.fact_ids
    }
    grounding_precision, grounding_recall, grounding_f1 = (
        _precision_recall_f1(predicted_grounding, expected_grounding)
    )
    confidence = (
        min(1.0, max(0.0, response.confidence))
        if isinstance(response.confidence, (int, float))
        else 0.0
    )
    calibration = 1.0 - (confidence - outcome) ** 2
    doctrine_score = sum(
        (
            DOCTRINE_WEIGHTS["outcome_accuracy"] * outcome,
            DOCTRINE_WEIGHTS["issue_f1"] * issue_f1,
            DOCTRINE_WEIGHTS["authority_f1"] * authority_f1,
            DOCTRINE_WEIGHTS["grounding_f1"] * grounding_f1,
            DOCTRINE_WEIGHTS["calibration"] * calibration,
        )
    )
    return DoctrineItemScore(
        item_id=item.id,
        family_id=item.family_id,
        outcome_accuracy=outcome,
        issue_precision=issue_precision,
        issue_recall=issue_recall,
        issue_f1=issue_f1,
        authority_precision=authority_precision,
        authority_recall=authority_recall,
        authority_f1=authority_f1,
        grounding_precision=grounding_precision,
        grounding_recall=grounding_recall,
        grounding_f1=grounding_f1,
        calibration=calibration,
        invalid_authorities=invalid,
        hallucinated_authorities=hallucinated,
        unsupported_authorities=unsupported,
        doctrine_score=doctrine_score,
        status="ok",
    )


def _matching_finding(
    criterion: MatterCriterion, findings: list[MatterFinding]
) -> MatterFinding | None:
    if criterion.issue_code is None:
        return None
    expected = criterion.issue_code.strip().upper()
    for finding in findings:
        if finding.issue_code.strip().upper() != expected:
            continue
        if (
            criterion.expected_disposition is not None
            and finding.disposition != criterion.expected_disposition
        ):
            continue
        return finding
    return None


def _criterion_passes(
    criterion: MatterCriterion,
    response: MatterResponse,
) -> bool:
    if criterion.review_only:
        return False
    if criterion.dimension == "deliverable":
        return bool(
            criterion.deliverable
            and criterion.deliverable in set(response.deliverables)
        )

    finding = _matching_finding(criterion, response.findings)
    if finding is None:
        return False
    if criterion.dimension == "legal":
        return True
    if criterion.dimension == "authority":
        _, recall, _, _, _, _ = _authority_score(
            finding.authorities,
            criterion.accepted_authorities,
            criterion.required_authority_groups,
        )
        return recall == 1.0
    if criterion.dimension == "fact":
        required_facts = _normalized_codes(criterion.required_fact_ids)
        submitted_refs = {value.strip() for value in finding.record_refs}
        required_refs_pass = all(
            any(
                submitted == required
                or submitted.startswith(f"{required}:")
                or submitted.startswith(f"{required}#")
                for submitted in submitted_refs
            )
            for required in criterion.required_record_refs
        )
        return required_facts.issubset(_normalized_codes(finding.fact_ids)) and (
            required_refs_pass
        )
    raise ValueError(f"unsupported matter criterion dimension: {criterion.dimension}")


def score_matter_task(
    task: MatterTask, response: MatterResponse
) -> MatterTaskScore:
    if response.status != "ok":
        return MatterTaskScore(
            task_id=task.id,
            family_id=task.family_id,
            legal_criteria_rate=0.0,
            authority_grounding_rate=0.0,
            factual_accuracy_rate=0.0,
            deliverable_completeness_rate=0.0,
            matter_score=0.0,
            complete_task=False,
            criteria=[],
            invalid_authorities=[],
            hallucinated_authorities=[],
            status=response.status,
        )

    criterion_scores = [
        MatterCriterionScore(
            criterion_id=criterion.id,
            dimension=criterion.dimension,
            passed=_criterion_passes(criterion, response),
            critical=criterion.critical,
            review_only=criterion.review_only,
        )
        for criterion in task.criteria
    ]
    by_dimension: dict[str, list[MatterCriterionScore]] = defaultdict(list)
    for score in criterion_scores:
        if not score.review_only:
            by_dimension[score.dimension].append(score)

    def rate(dimension: str) -> float:
        values = by_dimension[dimension]
        return sum(score.passed for score in values) / len(values) if values else 0.0

    legal = rate("legal")
    authority = rate("authority")
    fact = rate("fact")
    deliverable = rate("deliverable")
    matter_score = (
        MATTER_WEIGHTS["legal"] * legal
        + MATTER_WEIGHTS["authority"] * authority
        + MATTER_WEIGHTS["fact"] * fact
        + MATTER_WEIGHTS["deliverable"] * deliverable
    )
    critical_scores = [
        score
        for score in criterion_scores
        if score.critical and not score.review_only
    ]
    all_authorities = [
        authority_value
        for finding in response.findings
        for authority_value in finding.authorities
    ]
    accepted = [
        authority_value
        for criterion in task.criteria
        for authority_value in criterion.accepted_authorities
    ]
    _, _, _, invalid, hallucinated, _ = _authority_score(
        all_authorities, accepted, []
    )
    return MatterTaskScore(
        task_id=task.id,
        family_id=task.family_id,
        legal_criteria_rate=legal,
        authority_grounding_rate=authority,
        factual_accuracy_rate=fact,
        deliverable_completeness_rate=deliverable,
        matter_score=matter_score,
        complete_task=bool(critical_scores)
        and all(score.passed for score in critical_scores),
        criteria=criterion_scores,
        invalid_authorities=invalid,
        hallucinated_authorities=hallucinated,
        status="ok",
    )


def score_as_dict(score: DoctrineItemScore | MatterTaskScore) -> dict:
    return asdict(score)
