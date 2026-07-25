from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import asdict
from statistics import mean
from typing import Callable, Iterable, TypeVar

from .models_v4 import DoctrineItemScore, MatterTaskScore


T = TypeVar("T")


def _percentile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        return 0.0
    index = (len(sorted_values) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def cluster_bootstrap_interval(
    values: Iterable[T],
    family: Callable[[T], str],
    metric: Callable[[T], float],
    *,
    iterations: int = 5000,
    seed: int = 20260304,
) -> tuple[float, float]:
    grouped: dict[str, list[T]] = defaultdict(list)
    for value in values:
        grouped[family(value)].append(value)
    families = sorted(grouped)
    if not families:
        return 0.0, 0.0
    generator = random.Random(seed)
    estimates: list[float] = []
    for _ in range(iterations):
        sampled = [
            item
            for _ in families
            for item in grouped[generator.choice(families)]
        ]
        estimates.append(mean(metric(item) for item in sampled))
    estimates.sort()
    return _percentile(estimates, 0.025), _percentile(estimates, 0.975)


def summarize_doctrine(scores: list[DoctrineItemScore]) -> dict:
    metric_names = (
        "doctrine_score",
        "outcome_accuracy",
        "issue_f1",
        "authority_f1",
        "grounding_f1",
        "calibration",
    )
    families: dict[str, list[DoctrineItemScore]] = defaultdict(list)
    for score in scores:
        families[score.family_id].append(score)
    family_records = [
        {
            "family_id": family_id,
            "domain": values[0].domain,
            **{
                metric_name: mean(
                    getattr(value, metric_name) for value in values
                )
                for metric_name in metric_names
            },
        }
        for family_id, values in sorted(families.items())
    ]
    domains: dict[str, list[dict]] = defaultdict(list)
    for record in family_records:
        domains[record["domain"]].append(record)

    def domain_macro(metric_name: str) -> float:
        return (
            mean(
                mean(record[metric_name] for record in records)
                for records in domains.values()
            )
            if domains
            else 0.0
        )

    result = {
        "n": len(scores),
        "family_count": len(family_records),
        "domain_count": len(domains),
        **{name: domain_macro(name) for name in metric_names},
        "item_mean_score": mean(score.doctrine_score for score in scores)
        if scores
        else 0.0,
        "family_mean_score": mean(
            record["doctrine_score"] for record in family_records
        )
        if family_records
        else 0.0,
        "by_domain": {
            domain: {
                "family_count": len(records),
                "doctrine_score": mean(
                    record["doctrine_score"] for record in records
                ),
            }
            for domain, records in sorted(domains.items())
        },
        "invalid_authority_count": sum(
            len(score.invalid_authorities) for score in scores
        ),
        "hallucinated_authority_count": sum(
            len(score.hallucinated_authorities) for score in scores
        ),
        "failure_count": sum(score.status != "ok" for score in scores),
    }
    generator = random.Random(20260304)
    bootstrap_values: list[float] = []
    for _ in range(5000):
        bootstrap_values.append(
            mean(
                mean(
                    generator.choice(records)["doctrine_score"]
                    for _ in records
                )
                for records in domains.values()
            )
            if domains
            else 0.0
        )
    bootstrap_values.sort()
    low, high = (
        _percentile(bootstrap_values, 0.025),
        _percentile(bootstrap_values, 0.975),
    )
    result["score_ci_95"] = [low, high]
    return result


def summarize_matter(scores: list[MatterTaskScore]) -> dict:
    metric_names = (
        "matter_score",
        "legal_criteria_rate",
        "authority_grounding_rate",
        "factual_accuracy_rate",
        "deliverable_completeness_rate",
    )
    result = {
        "n": len(scores),
        **{
            name: mean(getattr(score, name) for score in scores) if scores else 0.0
            for name in metric_names
        },
        "complete_task_rate": mean(score.complete_task for score in scores)
        if scores
        else 0.0,
        "invalid_authority_count": sum(
            len(score.invalid_authorities) for score in scores
        ),
        "hallucinated_authority_count": sum(
            len(score.hallucinated_authorities) for score in scores
        ),
        "failure_count": sum(score.status != "ok" for score in scores),
    }
    low, high = cluster_bootstrap_interval(
        scores, lambda score: score.family_id, lambda score: score.matter_score
    )
    result["score_ci_95"] = [low, high]
    return result


def summarize_suite(
    doctrine_scores: list[DoctrineItemScore],
    matter_scores: list[MatterTaskScore],
) -> dict:
    doctrine = summarize_doctrine(doctrine_scores)
    matter = summarize_matter(matter_scores)
    if not doctrine_scores or not matter_scores:
        raise ValueError("overall score requires non-empty Doctrine and Matter tracks")
    overall = 0.5 * doctrine["doctrine_score"] + 0.5 * matter["matter_score"]

    doctrine_groups: dict[str, list[DoctrineItemScore]] = defaultdict(list)
    matter_groups: dict[str, list[MatterTaskScore]] = defaultdict(list)
    for score in doctrine_scores:
        doctrine_groups[score.family_id].append(score)
    for score in matter_scores:
        matter_groups[score.family_id].append(score)
    doctrine_domains: dict[str, list[str]] = defaultdict(list)
    for family_id, values in doctrine_groups.items():
        doctrine_domains[values[0].domain].append(family_id)
    matter_families = sorted(matter_groups)
    generator = random.Random(20260304)
    samples: list[float] = []
    for _ in range(5000):
        sampled_matter = [
            item
            for _ in matter_families
            for item in matter_groups[generator.choice(matter_families)]
        ]
        samples.append(
            0.5
            * mean(
                mean(
                    mean(
                        item.doctrine_score
                        for item in doctrine_groups[
                            generator.choice(family_ids)
                        ]
                    )
                    for _ in family_ids
                )
                for family_ids in doctrine_domains.values()
            )
            + 0.5 * mean(score.matter_score for score in sampled_matter)
        )
    samples.sort()
    return {
        "schema_version": "4.0",
        "overall_score": overall,
        "overall_score_100": overall * 100,
        "overall_ci_95": [
            _percentile(samples, 0.025),
            _percentile(samples, 0.975),
        ],
        "track_weights": {"doctrine": 0.5, "matter": 0.5},
        "weight_sensitivity": {
            "doctrine_40_matter_60": (
                0.4 * doctrine["doctrine_score"] + 0.6 * matter["matter_score"]
            ),
            "doctrine_50_matter_50": overall,
            "doctrine_60_matter_40": (
                0.6 * doctrine["doctrine_score"] + 0.4 * matter["matter_score"]
            ),
        },
        "doctrine": doctrine,
        "matter": matter,
    }


def score_records(scores: Iterable[DoctrineItemScore | MatterTaskScore]) -> list[dict]:
    return [asdict(score) for score in scores]
