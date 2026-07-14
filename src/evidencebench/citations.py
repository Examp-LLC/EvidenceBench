from __future__ import annotations

import json
import re
from pathlib import Path

from .data_gov import canonical_case_citation

_CITATION = re.compile(
    r"(?:Fed(?:eral)?\.?\s*R(?:ule)?\.?\s*Evid\.?|FRE|Rule)?\s*"
    r"(?P<rule>\d{3,4})(?P<subsections>(?:\([a-zA-Z0-9]+\))*)",
    re.IGNORECASE,
)

_CASE_CITATION = re.compile(
    r"(?P<volume>\d+)\s+"
    r"(?P<reporter>U\.?\s*S\.?|Cal\.?\s*(?:3d|4th|5th)|N\.?\s*Y\.?\s*3d|"
    r"N\.?\s*J\.?|Or\.?|A\.?\s*3d)\s+"
    r"(?P<page>\d+)",
    re.IGNORECASE,
)

_REPORTERS = {
    "US": "U.S.",
    "CAL3D": "Cal. 3d",
    "CAL4TH": "Cal. 4th",
    "CAL5TH": "Cal. 5th",
    "NY3D": "N.Y.3d",
    "NJ": "N.J.",
    "OR": "Or.",
    "A3D": "A.3d",
}


def _index_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "fre-2025-rules.json"


def _case_index_path() -> Path:
    root = Path(__file__).resolve().parents[2] / "data"
    v3 = root / "case-authorities-v3.json"
    return v3 if v3.exists() else root / "case-authorities-v2.json"


def load_rule_index() -> dict[str, list[str]]:
    return json.loads(_index_path().read_text())["rules"]


def load_case_index() -> set[str]:
    return set(json.loads(_case_index_path().read_text())["citations"])


def normalize_citation(value: str) -> str | None:
    stripped = value.strip()
    if re.search(r"(?:FRE|Fed(?:eral)?\.?\s*R(?:ule)?\.?\s*Evid\.?|Rule)\s*\d", stripped, re.I):
        match = _CITATION.search(stripped)
        if match:
            rule = match.group("rule")
            subsections = match.group("subsections") or ""
            return f"FRE {rule}{subsections.lower()}"
    case_match = _CASE_CITATION.search(stripped)
    if case_match:
        reporter_key = re.sub(r"[^A-Z0-9]", "", case_match.group("reporter").upper())
        reporter = _REPORTERS.get(reporter_key)
        if reporter:
            return f"{case_match.group('volume')} {reporter} {case_match.group('page')}"
    data_gov_citation = canonical_case_citation(stripped)
    if data_gov_citation:
        return data_gov_citation
    match = _CITATION.fullmatch(stripped)
    if match:
        return f"FRE {match.group('rule')}{(match.group('subsections') or '').lower()}"
    return None


def citation_exists(citation: str, index: dict[str, list[str]] | None = None) -> bool:
    normalized = normalize_citation(citation)
    if not normalized:
        return False
    if not normalized.startswith("FRE "):
        return normalized in load_case_index()
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
