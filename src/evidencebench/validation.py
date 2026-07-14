from __future__ import annotations

from collections import Counter

from .citations import citation_exists, normalize_many
from .datasets import load_questions


def validate_questions(path: str) -> list[str]:
    questions = load_questions(path)
    errors: list[str] = []
    ids = [question.id for question in questions]
    duplicates = [item for item, count in Counter(ids).items() if count > 1]
    if duplicates:
        errors.append(f"duplicate IDs: {', '.join(sorted(duplicates))}")
    for question in questions:
        option_ids = {option["id"] for option in question.options}
        if question.gold_choice_id not in option_ids:
            errors.append(f"{question.id}: gold choice is not an option")
        if question.corpus_version != "FRE-2025-12-01":
            errors.append(f"{question.id}: unexpected corpus version")
        if question.attorney_review_status not in {"APPROVED", "PENDING"}:
            errors.append(f"{question.id}: invalid review status")
        accepted = set(normalize_many(question.citations.accepted))
        if not accepted:
            errors.append(f"{question.id}: no accepted citations")
        for citation in accepted:
            if not citation_exists(citation):
                errors.append(f"{question.id}: nonexistent citation {citation}")
        for group in question.citations.required_groups:
            normalized_group = normalize_many(group)
            if not normalized_group or not set(normalized_group).issubset(accepted):
                errors.append(f"{question.id}: required group is not accepted")
    return errors
