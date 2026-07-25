#!/usr/bin/env python3
"""Create public aggregate and website payloads from the private v4 run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REPOSITORY_URL = "https://github.com/Examp-LLC/EvidenceBench"
METHODOLOGY_URL = f"{REPOSITORY_URL}/blob/main/METHODOLOGY_V4.md"
REVIEWER_URL = (
    f"{REPOSITORY_URL}/issues/new"
    "?template=evidencebench-v4-reviewer.yml"
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def public_payload(private: dict) -> dict:
    if private.get("release_status") != "unreviewed_research_release":
        raise ValueError("input is not the expected unreviewed research release")
    corpus = private["corpus"]
    cost = private["cost_accounting"]
    return {
        "schema_version": "4.0",
        "release_id": private["release_id"],
        "release_status": private["release_status"],
        "published_as_official": False,
        "review_status": private["review_status"],
        "corpus": {
            "doctrine": corpus["doctrine"],
            "matter": corpus["matter"],
            "combined_candidate_tree_sha256": corpus[
                "combined_candidate_tree_sha256"
            ],
        },
        "protocol": private["protocol"],
        "cost_accounting": {
            "hard_limit_usd": cost["hard_limit_usd"],
            "account_delta_usd": cost["account_delta_usd"],
            "full_run_reported_cost_usd": cost["full_run_reported_cost_usd"],
            "smoke_reported_cost_usd": cost["smoke_reported_cost_usd"],
        },
        "models": private["models"],
    }


def website_payload(public: dict) -> dict:
    return {
        "release_status": public["release_status"],
        "benchmark_version": "4.0.0-research",
        "published_at": f"{public['protocol']['run_date']}T00:00:00Z",
        "repository_url": REPOSITORY_URL,
        "methodology_url": METHODOLOGY_URL,
        "prior_version_url": "/articles/evidencebench-public-good-benchmark",
        "article_url": "/articles/evidencebench-v4-frontier-models",
        "reviewer_url": REVIEWER_URL,
        "review_status": public["review_status"],
        "corpus": {
            "doctrine_items": public["corpus"]["doctrine"]["count"],
            "doctrine_families": public["corpus"]["doctrine"]["families"],
            "doctrine_domains": 12,
            "matter_tasks": public["corpus"]["matter"]["count"],
            "documents_per_task": 6,
            "total_items": (
                public["corpus"]["doctrine"]["count"]
                + public["corpus"]["matter"]["count"]
            ),
            "commitment_sha256": public["corpus"][
                "combined_candidate_tree_sha256"
            ],
        },
        "protocol": {
            "provider": public["protocol"]["provider"],
            "runs_per_model": public["protocol"]["runs_per_model"],
            "overall_formula": "0.50 × Doctrine + 0.50 × Matter",
            "doctrine_tools_enabled": False,
            "matter_tools_enabled": True,
        },
        "models": public["models"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-aggregate", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--website-output", type=Path, required=True)
    args = parser.parse_args()
    private = json.loads(args.private_aggregate.read_text())
    public = public_payload(private)
    website = website_payload(public)
    write_json(args.public_output, public)
    write_json(args.website_output, website)
    print(f"published aggregate: {args.public_output}")
    print(f"published website payload: {args.website_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
