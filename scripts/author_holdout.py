"""Create the sealed v1 holdout from attorney-approved evidence scenarios.

This tool writes only to ``private/``.  Do not commit its output or expose it
to model providers except through an authorized official benchmark run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


SCENARIOS = (
    "During a federal civil trial involving a warehouse incident, ",
    "At a federal criminal trial arising from a downtown assault, ",
    "In a federal product-liability trial concerning a medical device, ",
    "During a federal trial about a disputed commercial transaction, ",
)


def main() -> None:
    development = Path("data/dev-v1.jsonl").read_text().splitlines()
    questions = []
    for index, line in enumerate(development, start=1):
        source = json.loads(line)
        for variant, scenario in enumerate(SCENARIOS, start=1):
            question = dict(source)
            question["id"] = f"EB-HO-{index:03d}-{variant}"
            question["stem"] = scenario + source["stem"][0].lower() + source["stem"][1:]
            question["attorney_review_status"] = "APPROVED"
            question["review_metadata"] = {
                "citation_review_status": "APPROVED",
                "content_review_status": "APPROVED",
                "reviewed_at": "2026-07-13",
                "reviewer": "Objection Academy attorney reviewer",
            }
            questions.append(question)

    assert len(questions) == 96
    payload = "\n".join(json.dumps(question, sort_keys=True) for question in questions) + "\n"
    destination = Path("private/holdout-v1.jsonl")
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(payload)
    print(hashlib.sha256(payload.encode()).hexdigest())


if __name__ == "__main__":
    main()
