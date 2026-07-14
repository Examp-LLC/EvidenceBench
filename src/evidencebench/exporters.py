from __future__ import annotations

import json
from pathlib import Path


def export_web(manifest_path: str, output_path: str) -> None:
    manifest = json.loads(Path(manifest_path).read_text())
    payload = {
        "benchmark_name": "EvidenceBench",
        "benchmark_version": manifest["benchmark_version"],
        "status": manifest["status"],
        "published_at": manifest["published_at"],
        "authority_corpus": manifest["authority_corpus"],
        "holdout": manifest["holdout"],
        "protocol": manifest["protocol"],
        "models": manifest["models"],
        "methodology_url": "https://github.com/Examp-LLC/EvidenceBench/blob/main/METHODOLOGY.md",
        "repository_url": "https://github.com/Examp-LLC/EvidenceBench",
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(payload, indent=2) + "\n")
