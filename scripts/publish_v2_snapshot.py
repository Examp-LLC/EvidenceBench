"""Create aggregate public artifacts from validated private v2 runs."""

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
}


def main() -> None:
    run_dir = Path("private/runs/v2.0.0")
    models = []
    for slug, (family, manifest_path) in MODELS.items():
        manifest = json.loads(Path(manifest_path).read_text())
        responses = [json.loads(line) for line in (run_dir / f"{slug}.jsonl").read_text().splitlines() if line]
        ids = [response["question_id"] for response in responses]
        if len(responses) != 112 or len(set(ids)) != 112:
            raise ValueError(f"{slug}: expected 112 unique responses")
        score = json.loads((run_dir / f"{slug}.score.json").read_text())
        usage = [response.get("usage") or {} for response in responses]
        models.append({
            "display_name": manifest["display_name"],
            "family": family,
            "model_id": manifest["model_id"],
            "provider_route": manifest["provider_route"],
            "status": "official",
            **{key: score["overall"][key] for key in ("overall", "answer_accuracy", "citation_f1", "hallucination_rate")},
            "dimensions": score["dimensions"],
            "cost_usd": round(sum(item.get("cost", 0) or 0 for item in usage), 6),
            "input_tokens": sum(item.get("prompt_tokens", 0) or 0 for item in usage),
            "output_tokens": sum(item.get("completion_tokens", 0) or 0 for item in usage),
        })
    models.sort(key=lambda model: model["overall"], reverse=True)
    published_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    manifest = {
        "benchmark_version": "2.0.0",
        "status": "official_snapshot",
        "published_at": published_at,
        "authority_corpus": {
            "version": "FRE-2025-12-01+CASELAW-2026-07-14",
            "fre_source_url": "https://www.uscourts.gov/sites/default/files/document/federal-rules-of-evidence.pdf",
            "case_index_version": "CASELAW-2026-07-14",
            "pending_amendments_excluded": [{"rule": "FRE 801(d)(1)(A)", "effective_date": "2026-12-01"}],
        },
        "holdout": {
            "status": "sealed",
            "question_count": 112,
            "fre_question_count": 96,
            "caselaw_question_count": 16,
            "development_question_count": 24,
            "dataset_sha256": file_sha256("private/holdout-v2.jsonl"),
            "caselaw_matrix": {
                "federal_civil_popular": 2, "federal_civil_obscure": 2,
                "federal_criminal_popular": 2, "federal_criminal_obscure": 2,
                "state_civil_popular": 2, "state_civil_obscure": 2,
                "state_criminal_popular": 2, "state_criminal_obscure": 2,
            },
            "categories": ["relevance", "hearsay", "witnesses", "experts", "authentication", "best_evidence", "character", "impeachment", "privilege", "caselaw"],
        },
        "protocol": {
            "name": "evidencebench-v2-closed-book",
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256": hashlib.sha256(inspect.getsource(prompt_for).encode()).hexdigest(),
            "runs_per_question": 1,
            "tools_enabled": False,
            "overall_formula": "0.70 * answer_accuracy + 0.30 * citation_f1",
        },
        "models": models,
    }
    destination = Path("results/v2.0.0/manifest.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
