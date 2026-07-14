from __future__ import annotations

import json
import re
from pathlib import Path

_CITATION = re.compile(
    r"(?:Fed(?:eral)?\.?\s*R(?:ule)?\.?\s*Evid\.?|FRE|Rule)?\s*"
    r"(?P<rule>\d{3,4})(?P<subsections>(?:\([a-zA-Z0-9]+\))*)",
    re.IGNORECASE,
)


def _index_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "fre-2025-rules.json"


def load_rule_index() -> dict[str, list[str]]:
    return json.loads(_index_path().read_text())["rules"]


def normalize_citation(value: str) -> str | None:
    match = _CITATION.search(value.strip())
    if not match:
        return None
    rule = match.group("rule")
    subsections = match.group("subsections") or ""
    return f"FRE {rule}{subsections.lower()}"


def citation_exists(citation: str, index: dict[str, list[str]] | None = None) -> bool:
    normalized = normalize_citation(citation)
    if not normalized:
        return False
    index = index or load_rule_index()
    match = re.fullmatch(r"FRE (\d{3,4})((?:\([a-z0-9]+\))*)", normalized)
    if not match:
        return False
    rule, subsections = match.groups()
    if rule not in index:
        return False
    return not subsections or subsections in index[rule]


def normalize_many(values: list[str]) -> list[str]:
    normalized = [normalize_citation(value) for value in values]
    return list(dict.fromkeys(value for value in normalized if value))
