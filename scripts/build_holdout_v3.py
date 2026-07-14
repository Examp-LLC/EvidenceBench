"""Build the v3 sealed holdout with the Data.gov-cataloged DOJ/NIJ caselaw tranche."""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path

from evidencebench.data_gov import recent_published_records


CORPUS_VERSION = "FRE-2025-12-01+CASELAW-DATAGOV-2026-07-14"
SNAPSHOT_PATH = Path("data/doj-nij-post-pcast-2024.json")
NEW_CASES_PATH = Path("private/data-gov-caselaw-v3.jsonl")
HOLDOUT_PATH = Path("private/holdout-v3.jsonl")
CASE_INDEX_PATH = Path("data/case-authorities-v3.json")

_CIVIL_CAPTIONS = {
    "Andersen v. City of Chicago, 467 F. Supp. 3d 598 (N.D. Ill. 2020)",
    "Schmidt v. Int'l Playthings LLC, 536 F. Supp. 3d 856 (D.N.M. 2021)",
    "Bader v. Johnson & Johnson, 86 Cal. App. 5th 1094 (Cal. Ct. App. 2022)",
}

_RULING_BUCKETS = {
    "admit": "Admitted the evidence or affirmed its admission",
    "exclude": "Excluded the evidence or reversed an exclusion",
    "limit": "Limited, conditioned, or split admissibility",
    "procedural": "Required further proceedings or issued no admissibility ruling",
}

_DISCIPLINE_LABELS = {
    "Bitemark": "bite-mark comparison",
    "DNA": "DNA analysis",
    "Fingerprints": "fingerprint comparison",
    "Footwear": "footwear comparison",
    "FTM": "firearms/toolmark comparison",
    "FTM; & Fingerprints": "firearms/toolmark and fingerprint comparison",
    "FTM; Fingerprints": "firearms/toolmark and fingerprint comparison",
    "DNA; & PCAST Dicta": "DNA analysis and PCAST-related arguments",
    "PCAST/; FRE 702": "PCAST and expert-admissibility standards",
    "PCAST Dicta": "PCAST-related expert-admissibility arguments",
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def ruling_bucket(effect: str) -> str:
    lowered = effect.lower()
    if lowered.startswith("affirm admission") or lowered == "admit":
        return "admit"
    if lowered.startswith("exclude") or lowered.startswith("reverse exclusion"):
        return "exclude"
    if any(token in lowered for token in ("limit", "admit/exclude", "error to admit")):
        return "limit"
    return "procedural"


def build_questions(snapshot: dict) -> list[dict]:
    records = recent_published_records(snapshot)
    if len(records) != 33:
        raise ValueError(f"expected 33 unique published 2020-2024 decisions, found {len(records)}")
    questions = []
    for index, record in enumerate(records, start=1):
        question_id = f"EB-DG-{index:03d}"
        rng = random.Random(question_id)
        gold_text = _RULING_BUCKETS[ruling_bucket(record["decision_effect"])]
        option_texts = list(_RULING_BUCKETS.values())
        rng.shuffle(option_texts)
        options = [
            {"id": chr(ord("A") + option_index), "text": text}
            for option_index, text in enumerate(option_texts)
        ]
        proceeding = "civil" if record["caption"] in _CIVIL_CAPTIONS else "criminal"
        jurisdiction = "federal" if record["jurisdiction"].startswith("Federal") else "state"
        year = record["decision_date"][:4]
        case_name = record["caption"].split(",", 1)[0]
        discipline = _DISCIPLINE_LABELS.get(record["discipline"], record["discipline"].lower())
        questions.append({
            "id": question_id,
            "category": f"caselaw_{jurisdiction}_{proceeding}_obscure",
            "difficulty": "hard",
            "stem": (
                f"In {case_name} ({year}), a {jurisdiction} {record['posture'].lower()} matter "
                f"involving {discipline}, which option best characterizes the court's "
                "evidentiary ruling?"
            ),
            "options": options,
            "gold_choice_id": next(option["id"] for option in options if option["text"] == gold_text),
            "rationale": (
                f"The DOJ/NIJ Post-PCAST decisions dataset classifies the decision effect as "
                f"'{record['decision_effect']}' and reports: {record['description']}"
            ),
            "citations": {
                "required_groups": [[record["case_citation"]]],
                "accepted": [record["case_citation"]],
            },
            "corpus_version": CORPUS_VERSION,
            "attorney_review_status": "APPROVED",
            "dimensions": {
                "jurisdiction": jurisdiction,
                "proceeding": proceeding,
                "familiarity": "obscure",
                "decision_year": year,
                "recency": "2022-2024" if int(year) >= 2022 else "2020-2021",
                "publication_status": "published",
                "source": "data_gov_doj_nij",
                "discipline": slug(record["discipline"]),
            },
            "source": {
                "dataset": "DOJ/NIJ Post-PCAST Court Decisions",
                "source_row": record["source_row"],
                "catalog_url": snapshot["catalog_url"],
                "resource_url": snapshot["resource_url"],
                "records_sha256": snapshot["records_sha256"],
            },
        })
    return questions


def jsonl(rows: list[dict]) -> str:
    return "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"


def main() -> None:
    snapshot = json.loads(SNAPSHOT_PATH.read_text())
    new_questions = build_questions(snapshot)
    NEW_CASES_PATH.write_text(jsonl(new_questions))

    existing = [
        json.loads(line)
        for path in (
            Path("private/holdout-v1.jsonl"),
            Path("private/caselaw-v2.jsonl"),
            Path("private/recent-caselaw-2026.jsonl"),
        )
        for line in path.read_text().splitlines()
        if line
    ]
    rows = [*existing, *new_questions]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate holdout IDs")
    payload = jsonl(rows)
    HOLDOUT_PATH.write_text(payload)

    old_index = json.loads(Path("data/case-authorities-v2.json").read_text())
    recent_source = json.loads(Path("data/recent-caselaw-2026.json").read_text())
    citations = sorted({
        *old_index["citations"],
        *(q["citations"]["accepted"][0] for q in new_questions),
        *(record["citation"] for record in recent_source["records"]),
    })
    CASE_INDEX_PATH.write_text(json.dumps({"version": "CASELAW-DATAGOV-2026-07-14", "citations": citations}, indent=2) + "\n")

    print(json.dumps({
        "question_count": len(rows),
        "caselaw_question_count": sum(row["category"].startswith("caselaw_") for row in rows),
        "data_gov_question_count": len(new_questions),
        "recent_2026_question_count": len(recent_source["records"]),
        "data_gov_years": dict(sorted(Counter(q["dimensions"]["decision_year"] for q in new_questions).items())),
        "data_gov_jurisdictions": dict(sorted(Counter(q["dimensions"]["jurisdiction"] for q in new_questions).items())),
        "dataset_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "source_records_sha256": snapshot["records_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
