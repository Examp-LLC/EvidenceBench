from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


CATALOG_URL = (
    "https://catalog.data.gov/dataset/"
    "post-pcast-court-decisions-assessing-the-admissibility-of-forensic-science-evidence"
)
RESOURCE_URL = (
    "https://nij.ojp.gov/program/national-center-forensics/"
    "post-pcast-court-decisions-assessing-admissibility-forensic-science-evidence"
)

_HEADERS = {
    "Caption": "caption",
    "Federal or; State": "jurisdiction",
    "State, Including Federal District or Circuit": "court_location",
    "Posture": "posture",
    "Discipline": "discipline",
    "Decision Date": "decision_date_raw",
    "Decision Effect": "decision_effect",
    "Outcome": "outcome",
    "Publication Status": "publication_status",
    "Description": "description",
}

_REPORTER_PATTERN = re.compile(
    r"(?P<volume>\d+)\s+"
    r"(?P<reporter>"
    r"U\.\s*S\.|F\.\s*(?:2d|3d|4th)|F\.\s*Supp\.\s*(?:2d|3d)|"
    r"N\.\s*E\.\s*3d|N\.\s*J\.\s*Super\.|N\.\s*Y\.\s*3d|"
    r"Cal\.\s*App\.\s*(?:4th|5th)|A\.\s*3d|P\.\s*3d|S\.\s*W\.\s*3d|"
    r"Conn\.|Neb\.|Md\.|Pa\.|N\.\s*C\.\s*App\.|Misc\.\s*3d"
    r")\s+(?P<page>\d+)",
    re.IGNORECASE,
)
_LEXIS_PATTERN = re.compile(
    r"(?P<year>20\d{2})\s+"
    r"(?P<reporter>U\.\s*S\.\s*(?:Dist|App)\.\s*LEXIS|Cal\.\s*App\.\s*LEXIS)\s+"
    r"(?P<number>\d+)",
    re.IGNORECASE,
)
_OHIO_PATTERN = re.compile(r"20\d{2}-Ohio-\d+", re.IGNORECASE)
_NY_SLIP_PATTERN = re.compile(r"20\d{2}\s+NY\s+Slip\s+Op\s+\d+(?:\(U\))?", re.IGNORECASE)
_DOCKET_PATTERN = re.compile(r"(?:No\.\s*)?(?P<docket>\d{2}-\d{4,5})", re.IGNORECASE)

_REPORTERS = {
    "US": "U.S.",
    "F2D": "F.2d",
    "F3D": "F.3d",
    "F4TH": "F.4th",
    "FSUPP2D": "F. Supp. 2d",
    "FSUPP3D": "F. Supp. 3d",
    "NE3D": "N.E.3d",
    "NJSUPER": "N.J. Super.",
    "NY3D": "N.Y.3d",
    "CALAPP4TH": "Cal. App. 4th",
    "CALAPP5TH": "Cal. App. 5th",
    "A3D": "A.3d",
    "P3D": "P.3d",
    "SW3D": "S.W.3d",
    "CONN": "Conn.",
    "NEB": "Neb.",
    "MD": "Md.",
    "PA": "Pa.",
    "NCAPP": "N.C. App.",
    "MISC3D": "Misc. 3d",
}


class DecisionsTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.cell: list[str] | None = None
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and "datatable" in (attributes.get("class") or "").split():
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.row = []
        elif self.in_table and tag in {"th", "td"}:
            self.cell = []

    def handle_endtag(self, tag: str) -> None:
        if not self.in_table:
            return
        if tag in {"th", "td"} and self.cell is not None:
            self.row.append(re.sub(r"\s+", " ", "".join(self.cell)).strip())
            self.cell = None
        elif tag == "tr" and self.row:
            self.rows.append(self.row)
        elif tag == "table":
            self.in_table = False

    def handle_data(self, data: str) -> None:
        if self.in_table and self.cell is not None:
            self.cell.append(data)


def fetch_resource() -> bytes:
    request = Request(RESOURCE_URL, headers={"User-Agent": "EvidenceBench/3.0"})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed public URL
        return response.read()


def parse_decision_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%m/%d/%Y").date()
    except ValueError:
        pass
    if value.isdigit():
        return date(1899, 12, 30) + timedelta(days=int(value))
    return None


def canonical_case_citation(caption: str) -> str | None:
    match = _LEXIS_PATTERN.search(caption)
    if match:
        reporter_key = re.sub(r"[^A-Z]", "", match.group("reporter").upper())
        reporter = {
            "USDISTLEXIS": "U.S. Dist. LEXIS",
            "USAPPLEXIS": "U.S. App. LEXIS",
            "CALAPPLEXIS": "Cal. App. LEXIS",
        }[reporter_key]
        return f"{match.group('year')} {reporter} {match.group('number')}"
    match = _OHIO_PATTERN.search(caption)
    if match:
        return match.group(0).replace("ohio", "Ohio")
    match = _NY_SLIP_PATTERN.search(caption)
    if match:
        return re.sub(r"\s+", " ", match.group(0)).replace("ny slip op", "NY Slip Op")
    match = _REPORTER_PATTERN.search(caption)
    if not match:
        docket_match = _DOCKET_PATTERN.search(caption)
        return f"No. {docket_match.group('docket')}" if docket_match else None
    reporter_key = re.sub(r"[^A-Z0-9]", "", match.group("reporter").upper())
    reporter = _REPORTERS.get(reporter_key)
    if not reporter:
        return None
    return f"{match.group('volume')} {reporter} {match.group('page')}"


def parse_resource(html: bytes) -> list[dict[str, str | bool | None]]:
    parser = DecisionsTableParser()
    parser.feed(html.decode("utf-8"))
    if not parser.rows or parser.rows[0] != list(_HEADERS):
        raise ValueError("NIJ decisions table headers changed")
    records: list[dict[str, str | bool | None]] = []
    for index, values in enumerate(parser.rows[1:], start=1):
        if len(values) != len(_HEADERS):
            raise ValueError(f"NIJ row {index} has {len(values)} cells")
        record = {_HEADERS[key]: value for key, value in zip(_HEADERS, values, strict=True)}
        decision_date = parse_decision_date(record["decision_date_raw"])
        caption_years = [int(value) for value in re.findall(r"\b(20\d{2})\b", record["caption"])]
        date_mismatch = bool(decision_date and caption_years and decision_date.year not in caption_years)
        records.append({
            "source_row": index,
            **record,
            "decision_date": decision_date.isoformat() if decision_date else None,
            "case_citation": canonical_case_citation(record["caption"]),
            "date_mismatch": date_mismatch,
        })
    return records


def snapshot_payload(html: bytes, retrieved_at: datetime | None = None) -> dict:
    records = parse_resource(html)
    normalized = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    timestamp = retrieved_at or datetime.now(UTC)
    return {
        "dataset": "Post-PCAST Court Decisions Assessing the Admissibility of Forensic Science Evidence",
        "catalog_url": CATALOG_URL,
        "resource_url": RESOURCE_URL,
        "publisher": "U.S. Department of Justice, National Institute of Justice",
        "license": "Public Domain",
        "retrieved_at": timestamp.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_html_sha256": hashlib.sha256(html).hexdigest(),
        "records_sha256": hashlib.sha256(normalized).hexdigest(),
        "record_count": len(records),
        "records": records,
    }


def recent_published_records(snapshot: dict, start_year: int = 2020, end_year: int = 2024) -> list[dict]:
    selected: dict[str, dict] = {}
    for record in snapshot["records"]:
        value = record.get("decision_date")
        if not value or record.get("date_mismatch"):
            continue
        year = int(value[:4])
        if not start_year <= year <= end_year:
            continue
        if not record["publication_status"].startswith("Pub") or not record.get("case_citation"):
            continue
        previous = selected.get(record["caption"])
        if previous is None or "/" in record["decision_date_raw"]:
            selected[record["caption"]] = record
    return sorted(selected.values(), key=lambda item: (item["decision_date"], item["caption"]))


def write_snapshot(path: str | Path, html: bytes | None = None) -> dict:
    payload = snapshot_payload(html or fetch_resource())
    Path(path).write_text(json.dumps(payload, indent=2) + "\n")
    return payload
