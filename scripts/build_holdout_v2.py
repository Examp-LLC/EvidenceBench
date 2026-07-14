"""Build the sealed v2 holdout and print its public commitment metadata."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    sources = [Path("private/holdout-v1.jsonl"), Path("private/caselaw-v2.jsonl")]
    rows = [json.loads(line) for source in sources for line in source.read_text().splitlines() if line]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate holdout IDs")
    payload = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
    destination = Path("private/holdout-v2.jsonl")
    destination.write_text(payload)
    matrix = Counter(row["category"] for row in rows if row["category"].startswith("caselaw_"))
    print(json.dumps({
        "question_count": len(rows),
        "caselaw_question_count": sum(matrix.values()),
        "caselaw_matrix": dict(sorted(matrix.items())),
        "dataset_sha256": hashlib.sha256(payload.encode()).hexdigest(),
    }, indent=2))


if __name__ == "__main__":
    main()
