"""Create public aggregate artifacts from validated private v3 runs."""

from __future__ import annotations

import hashlib
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path

from evidencebench.datasets import file_sha256
from evidencebench.runner import PROMPT_VERSION, prompt_for


MODELS = {
    "openai-gpt-5-6-sol": ("OpenAI", "models/openai-gpt-5-6-sol.json"),
    "anthropic-claude-fable-5": ("Anthropic", "models/anthropic-claude-fable-5.json"),
    "google-gemini-3-5-flash": ("Google", "models/google-gemini-3-5-flash.json"),
    "xai-grok-4-5": ("xAI", "models/xai-grok-4-5.json"),
    "deepseek-v4-pro": ("DeepSeek", "models/deepseek-v4-pro.json"),
    "mistral-large-3": ("Mistral", "models/mistral-large-3.json"),
    "moonshotai-kimi-k3": ("Moonshot AI", "models/moonshotai-kimi-k3.json"),
}


def main() -> None:
    run_dir = Path("private/runs/v3.0.0")
    source = json.loads(Path("data/doj-nij-post-pcast-2024.json").read_text())
    models = []
    for slug, (family, manifest_path) in MODELS.items():
        manifest = json.loads(Path(manifest_path).read_text())
        response_path = run_dir / f"{slug}.jsonl"
        responses = [json.loads(line) for line in response_path.read_text().splitlines() if line]
        ids = [response["question_id"] for response in responses]
        if len(responses) != 151 or len(set(ids)) != 151:
            raise ValueError(f"{slug}: expected 151 unique responses")
        score = json.loads((run_dir / f"{slug}.score.json").read_text())
        usage = [response.get("usage") or {} for response in responses]
        models.append({
            "display_name": manifest["display_name"],
            "family": family,
            "model_id": manifest["model_id"],
            "provider_route": manifest["provider_route"],
            "status": "official",
            **{
                key: score["overall"][key]
                for key in ("overall", "answer_accuracy", "citation_f1", "hallucination_rate")
            },
            "dimensions": score["dimensions"],
            "cost_usd": round(sum(item.get("cost", 0) or 0 for item in usage), 6),
            "input_tokens": sum(item.get("prompt_tokens", 0) or 0 for item in usage),
            "output_tokens": sum(item.get("completion_tokens", 0) or 0 for item in usage),
        })
    models.sort(key=lambda model: model["overall"], reverse=True)
    published_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    manifest = {
        "benchmark_version": "3.0.0",
        "status": "official_snapshot",
        "published_at": published_at,
        "authority_corpus": {
            "version": "FRE-2025-12-01+CASELAW-DATAGOV-2026-07-14",
            "fre_source_url": "https://www.uscourts.gov/sites/default/files/document/federal-rules-of-evidence.pdf",
            "case_index_version": "CASELAW-DATAGOV-2026-07-14",
            "data_gov_catalog_url": source["catalog_url"],
            "data_gov_resource_url": source["resource_url"],
            "data_gov_license": source["license"],
            "data_gov_source_html_sha256": source["source_html_sha256"],
            "data_gov_records_sha256": source["records_sha256"],
            "recent_2026_source_version": "RECENT-CASELAW-2026-07-14",
            "recent_2026_metadata_sha256": file_sha256("data/recent-caselaw-2026.json"),
            "pending_amendments_excluded": [
                {"rule": "FRE 801(d)(1)(A)", "effective_date": "2026-12-01"}
            ],
        },
        "holdout": {
            "status": "sealed",
            "question_count": 151,
            "fre_question_count": 96,
            "caselaw_question_count": 55,
            "data_gov_caselaw_question_count": 33,
            "recent_2026_caselaw_question_count": 6,
            "development_question_count": 24,
            "dataset_sha256": file_sha256("private/holdout-v3.jsonl"),
            "data_gov_window": {"start": "2020-01-01", "end": "2024-12-31"},
            "data_gov_years": {"2020": 13, "2021": 6, "2022": 6, "2023": 6, "2024": 2},
            "data_gov_jurisdictions": {"federal": 12, "state": 21},
            "data_gov_proceedings": {"civil": 3, "criminal": 30},
            "recent_2026_jurisdictions": {"federal": 4, "state": 2},
            "recent_2026_proceedings": {"civil": 4, "criminal": 2},
            "data_gov_selection": "unique+citable+publication_status_published+decision_date_2020_2024",
            "recent_2026_selection": "published+official_source+material_evidence_holding+decision_date_2026",
            "categories": [
                "relevance", "hearsay", "witnesses", "experts", "authentication",
                "best_evidence", "character", "impeachment", "privilege", "caselaw",
            ],
        },
        "protocol": {
            "name": "evidencebench-v3-closed-book",
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256": hashlib.sha256(inspect.getsource(prompt_for).encode()).hexdigest(),
            "runs_per_question": 1,
            "tools_enabled": False,
            "overall_formula": "0.70 * answer_accuracy + 0.30 * citation_f1",
        },
        "models": models,
    }
    destination = Path("results/v3.0.0/manifest.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
