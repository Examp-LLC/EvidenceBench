from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

from .citations import citation_exists, normalize_citation
from .datasets_v4 import load_doctrine_items, load_matter_tasks
from .models_v4 import MatterTask, ReviewRecord


SCHEMA_VERSION = "4.0"
REVIEW_STATUSES = {"DRAFT", "IN_REVIEW", "APPROVED"}
RULINGS = {"admit", "exclude", "limit", "defer"}
MATTER_DIMENSIONS = {"legal", "authority", "fact", "deliverable"}
DOMAINS = {
    "D01_JUDICIAL_ADMINISTRATION",
    "D02_RELEVANCE_403",
    "D03_CHARACTER_PROPENSITY_HABIT",
    "D04_POLICY_EXCLUSIONS",
    "D05_WITNESS_EXAMINATION",
    "D06_IMPEACHMENT_REHABILITATION",
    "D07_OPINION_EXPERTS",
    "D08_HEARSAY_DEFINITIONS",
    "D09_HEARSAY_EXCEPTIONS",
    "D10_AUTHENTICATION_IDENTIFICATION",
    "D11_CONTENTS_ORIGINALS_SUMMARIES",
    "D12_PRIVILEGE_CONSTITUTIONAL",
}


def _review_errors(review: ReviewRecord, label: str, official: bool) -> list[str]:
    errors: list[str] = []
    if review.status not in REVIEW_STATUSES:
        errors.append(f"{label}: invalid review status {review.status!r}")
    if official:
        if review.status != "APPROVED":
            errors.append(f"{label}: official data must be APPROVED")
        if not review.author_id:
            errors.append(f"{label}: official data requires author_id")
        if not review.reviewer_ids:
            errors.append(f"{label}: official data requires at least one reviewer")
        if review.author_id and review.author_id in review.reviewer_ids:
            errors.append(f"{label}: author cannot be the sole independent reviewer")
        if not review.reviewed_at:
            errors.append(f"{label}: official data requires reviewed_at")
    return errors


def _authority_errors(values: list[str], label: str) -> list[str]:
    errors: list[str] = []
    for value in values:
        normalized = normalize_citation(value)
        if normalized is None:
            errors.append(f"{label}: unparseable authority {value!r}")
        elif not citation_exists(normalized):
            errors.append(f"{label}: authority absent from pinned corpus {value!r}")
    return errors


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", value.casefold())).strip()


def validate_doctrine_items(
    path: str | Path, official: bool = False, candidate: bool = False
) -> list[str]:
    errors: list[str] = []
    try:
        items = load_doctrine_items(path)
    except (KeyError, TypeError, ValueError) as exc:
        return [f"{path}: could not parse doctrine data: {exc}"]
    ids: Counter[str] = Counter(item.id for item in items)
    duplicate_ids = sorted(item_id for item_id, count in ids.items() if count > 1)
    for item_id in duplicate_ids:
        errors.append(f"duplicate doctrine id: {item_id}")

    normalized_stems: dict[str, str] = {}
    family_domains: dict[str, str] = {}
    for item in items:
        label = item.id
        if item.schema_version != SCHEMA_VERSION:
            errors.append(f"{label}: schema_version must be {SCHEMA_VERSION}")
        if item.track != "doctrine":
            errors.append(f"{label}: track must be doctrine")
        if not item.family_id:
            errors.append(f"{label}: family_id is required")
        if official or candidate:
            if item.domain not in DOMAINS:
                errors.append(f"{label}: domain is not in the v4 registry")
            if not item.coverage_cell:
                errors.append(f"{label}: coverage_cell is required")
            prior_domain = family_domains.setdefault(item.family_id, item.domain)
            if prior_domain != item.domain:
                errors.append(f"{label}: family spans multiple domains")
        if item.gold.ruling not in item.allowed_rulings:
            errors.append(f"{label}: gold ruling is not in allowed_rulings")
        if set(item.allowed_rulings) - RULINGS:
            errors.append(f"{label}: unsupported ruling in allowed_rulings")
        if not item.gold.issue_codes:
            errors.append(f"{label}: at least one gold issue code is required")

        fact_ids = [fact.id for fact in item.facts]
        if len(fact_ids) != len(set(fact_ids)):
            errors.append(f"{label}: fact ids must be unique")
        issue_codes = set(item.gold.issue_codes)
        for grounding in item.gold.grounding:
            if grounding.issue_code not in issue_codes:
                errors.append(
                    f"{label}: grounding issue {grounding.issue_code!r} is not gold"
                )
            missing = sorted(set(grounding.fact_ids) - set(fact_ids))
            if missing:
                errors.append(f"{label}: grounding references missing facts {missing}")

        accepted = {
            normalize_citation(value) for value in item.gold.accepted_authorities
        }
        errors.extend(
            _authority_errors(item.gold.accepted_authorities, f"{label} accepted")
        )
        for group_index, group in enumerate(item.gold.required_authority_groups):
            if not group:
                errors.append(f"{label}: authority group {group_index} is empty")
            errors.extend(
                _authority_errors(group, f"{label} authority group {group_index}")
            )
            if any(normalize_citation(value) not in accepted for value in group):
                errors.append(
                    f"{label}: authority group {group_index} is not a subset "
                    "of accepted_authorities"
                )
        errors.extend(_review_errors(item.review, label, official))

        normalized = _normalized_text(item.stem)
        if normalized in normalized_stems:
            errors.append(
                f"{label}: exact normalized stem duplicate of "
                f"{normalized_stems[normalized]}"
            )
        else:
            normalized_stems[normalized] = label
    return errors


def _document_errors(task: MatterTask, task_dir: Path) -> list[str]:
    errors: list[str] = []
    document_root = (task_dir / "documents").resolve()
    for document in task.documents:
        candidate = (document_root / document.path).resolve()
        try:
            candidate.relative_to(document_root)
        except ValueError:
            errors.append(f"{task.id}: unsafe document path {document.path!r}")
            continue
        if not candidate.is_file():
            errors.append(f"{task.id}: missing document {document.path!r}")
            continue
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if digest != document.sha256:
            errors.append(f"{task.id}: sha256 mismatch for {document.path!r}")
        if document.canonical_text_path:
            canonical = (document_root / document.canonical_text_path).resolve()
            try:
                canonical.relative_to(document_root)
            except ValueError:
                errors.append(
                    f"{task.id}: unsafe canonical text path "
                    f"{document.canonical_text_path!r}"
                )
                continue
            if not canonical.is_file():
                errors.append(
                    f"{task.id}: missing canonical text "
                    f"{document.canonical_text_path!r}"
                )
            elif not document.canonical_text_sha256:
                errors.append(
                    f"{task.id}: canonical text sha256 is required"
                )
            elif hashlib.sha256(canonical.read_bytes()).hexdigest() != (
                document.canonical_text_sha256
            ):
                errors.append(
                    f"{task.id}: canonical text sha256 mismatch for "
                    f"{document.canonical_text_path!r}"
                )
    return errors


def validate_matter_tasks(
    path: str | Path, official: bool = False, candidate: bool = False
) -> list[str]:
    errors: list[str] = []
    root = Path(path)
    try:
        entries = load_matter_tasks(root)
    except (KeyError, TypeError, ValueError) as exc:
        return [f"{path}: could not parse matter data: {exc}"]
    ids = Counter(task.id for _, task in entries)
    for task_id, count in ids.items():
        if count > 1:
            errors.append(f"duplicate matter task id: {task_id}")

    for task_dir, task in entries:
        label = task.id
        if task.schema_version != SCHEMA_VERSION:
            errors.append(f"{label}: schema_version must be {SCHEMA_VERSION}")
        if task.track != "matter":
            errors.append(f"{label}: track must be matter")
        if not task.family_id:
            errors.append(f"{label}: family_id is required")
        if official or candidate:
            if task.domain not in DOMAINS:
                errors.append(f"{label}: domain is not in the v4 registry")
            if not task.coverage_cell:
                errors.append(f"{label}: coverage_cell is required")
            if not task.gold_findings:
                errors.append(f"{label}: gold_findings are required")
        if not task.documents:
            errors.append(f"{label}: at least one matter document is required")
        if not task.deliverables:
            errors.append(f"{label}: at least one deliverable is required")
        if any(Path(value).is_absolute() or ".." in Path(value).parts for value in task.deliverables):
            errors.append(f"{label}: deliverables must use safe relative paths")

        criterion_ids = [criterion.id for criterion in task.criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            errors.append(f"{label}: criterion ids must be unique")
        scoring = [criterion for criterion in task.criteria if not criterion.review_only]
        dimensions = {criterion.dimension for criterion in scoring}
        missing_dimensions = MATTER_DIMENSIONS - dimensions
        if missing_dimensions:
            errors.append(
                f"{label}: missing scoring dimensions {sorted(missing_dimensions)}"
            )
        if any(criterion.dimension not in MATTER_DIMENSIONS for criterion in scoring):
            errors.append(f"{label}: unsupported scoring criterion dimension")
        if not any(criterion.critical for criterion in scoring):
            errors.append(f"{label}: at least one scoring criterion must be critical")
        for criterion in scoring:
            criterion_label = f"{label}/{criterion.id}"
            if criterion.dimension == "deliverable":
                if criterion.deliverable not in task.deliverables:
                    errors.append(
                        f"{criterion_label}: deliverable is not declared by task"
                    )
                if criterion.min_bytes < 1:
                    errors.append(
                        f"{criterion_label}: min_bytes must be positive"
                    )
            else:
                if not criterion.issue_code:
                    errors.append(f"{criterion_label}: issue_code is required")
                if criterion.dimension == "authority":
                    errors.extend(
                        _authority_errors(
                            criterion.accepted_authorities,
                            f"{criterion_label} accepted",
                        )
                    )
                    accepted = {
                        normalize_citation(value)
                        for value in criterion.accepted_authorities
                    }
                    for group in criterion.required_authority_groups:
                        if not group:
                            errors.append(
                                f"{criterion_label}: authority group is empty"
                            )
                        if any(normalize_citation(value) not in accepted for value in group):
                            errors.append(
                                f"{criterion_label}: authority group is not accepted"
                            )
        gold_issues = [finding.issue_code for finding in task.gold_findings]
        if len(gold_issues) != len(set(gold_issues)):
            errors.append(f"{label}: gold finding issue codes must be unique")
        for finding in task.gold_findings:
            gold_label = f"{label}/{finding.issue_code}"
            if not finding.accepted_dispositions:
                errors.append(
                    f"{gold_label}: accepted_dispositions cannot be empty"
                )
            if not set(finding.required_fact_ids).issubset(
                finding.accepted_fact_ids
            ):
                errors.append(
                    f"{gold_label}: required facts must be accepted"
                )
            if not set(finding.required_record_refs).issubset(
                finding.accepted_record_refs
            ):
                errors.append(
                    f"{gold_label}: required record refs must be accepted"
                )
            accepted = {
                normalize_citation(value)
                for value in finding.accepted_authorities
            }
            errors.extend(
                _authority_errors(
                    finding.accepted_authorities,
                    f"{gold_label} accepted",
                )
            )
            for group in finding.required_authority_groups:
                if not group:
                    errors.append(f"{gold_label}: authority group is empty")
                if any(
                    normalize_citation(value) not in accepted for value in group
                ):
                    errors.append(
                        f"{gold_label}: required authority is not accepted"
                    )
        errors.extend(_document_errors(task, task_dir))
        errors.extend(_review_errors(task.review, label, official))
    return errors


def audit_doctrine_overlap(
    public_path: str | Path, holdout_path: str | Path
) -> list[str]:
    public = load_doctrine_items(public_path)
    holdout = load_doctrine_items(holdout_path)
    public_families = {item.family_id for item in public}
    public_stems = {_normalized_text(item.stem): item.id for item in public}
    findings: list[str] = []
    for item in holdout:
        if item.family_id in public_families:
            findings.append(f"{item.id}: family_id appears in public set")
        normalized = _normalized_text(item.stem)
        if normalized in public_stems:
            findings.append(
                f"{item.id}: normalized stem duplicates {public_stems[normalized]}"
            )
    return findings
