from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DOMAINS = [
    "D01_JUDICIAL_ADMINISTRATION",
    "D02_RELEVANCE_403",
    "D03_CHARACTER_PROPENSITY_HABIT",
    "D04_POLICY_EXCLUSIONS",
    "D05_WITNESS_EXAMINATION",
    "D06_IMPEACHMENT_REHABILITATION",
    "D07_OPINION_EXPERTS",
    "D08_HEARSAY_DEFINITIONS",
    "D09_HEARSAY_EXCEPTIONS",
    "D10_AUTHENTICATION_IDENTIFICATION",
    "D11_CONTENTS_ORIGINALS_SUMMARIES",
    "D12_PRIVILEGE_CONSTITUTIONAL",
]

SOURCES = {
    "federal": "https://www.uscourts.gov/sites/default/files/document/federal-rules-of-evidence.pdf",
    "california": "https://leginfo.legislature.ca.gov/faces/codes.xhtml",
    "new_york": "https://www.nycourts.gov/guide-new-york-evidence",
    "texas": "https://txcourts.gov/rules-forms/",
    "florida": "https://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0000-0099/0090/0090ContentsIndex.html",
    "pennsylvania": "https://www.pacourts.us/courts/supreme-court/committees/rules-committees/committee-on-rules-of-evidence",
    "new_jersey": "https://www.njcourts.gov/sites/default/files/evidence1.pdf",
    "illinois": "https://www.illinoiscourts.gov/courts-supreme-court-illinois-rules-of-evidence/",
    "ohio": "https://www.supremecourt.ohio.gov/docs/LegalResources/Rules/evidence/evidence.pdf",
    "michigan": "https://www.courts.michigan.gov/siteassets/rules-instructions-administrative-orders/rules-of-evidence/michigan-rules-of-evidence.pdf",
    "georgia": "https://www.legis.ga.gov/",
    "washington": "https://www.courts.wa.gov/court_rules/",
    "arizona": "https://www.azcourts.gov/rules/CurrentArizonaRules.aspx",
}

STANDARD_RULES = ["104", "403", "404", "407", "611", "613", "702", "801", "803(6)", "901", "1002", "502"]
PREFIXES = {
    "federal": "FRE",
    "texas": "Tex. R. Evid.",
    "pennsylvania": "Pa. R.E.",
    "new_jersey": "N.J.R.E.",
    "illinois": "Ill. R. Evid.",
    "ohio": "Ohio R. Evid.",
    "michigan": "MRE",
    "washington": "Wash. ER",
    "arizona": "Ariz. R. Evid.",
}

SPECIAL = {
    "california": [
        "Cal. Evid. Code § 405",
        "Cal. Evid. Code § 352",
        "Cal. Evid. Code § 1101",
        "Cal. Evid. Code § 1151",
        "Cal. Evid. Code § 765",
        "Cal. Evid. Code § 780",
        "Cal. Evid. Code § 801",
        "Cal. Evid. Code § 1200",
        "Cal. Evid. Code § 1271",
        "Cal. Evid. Code § 1400",
        "Cal. Evid. Code § 1521",
        "Cal. Evid. Code § 954",
    ],
    "new_york": [
        "GNYE 1.09",
        "GNYE 4.07",
        "GNYE 4.09",
        "GNYE 4.19",
        "GNYE 6.10",
        "GNYE 6.15",
        "GNYE 7.01",
        "GNYE 8.00",
        "GNYE 8.08",
        "GNYE 9.01",
        "GNYE 10.03",
        "GNYE 5.03",
    ],
    "florida": [
        "Fla. Stat. § 90.105",
        "Fla. Stat. § 90.403",
        "Fla. Stat. § 90.404",
        "Fla. Stat. § 90.407",
        "Fla. Stat. § 90.612",
        "Fla. Stat. § 90.608",
        "Fla. Stat. § 90.702",
        "Fla. Stat. § 90.801",
        "Fla. Stat. § 90.803(6)",
        "Fla. Stat. § 90.901",
        "Fla. Stat. § 90.952",
        "Fla. Stat. § 90.502",
    ],
    "georgia": [
        "O.C.G.A. § 24-1-104",
        "O.C.G.A. § 24-4-403",
        "O.C.G.A. § 24-4-404",
        "O.C.G.A. § 24-4-407",
        "O.C.G.A. § 24-6-611",
        "O.C.G.A. § 24-6-613",
        "O.C.G.A. § 24-7-702",
        "O.C.G.A. § 24-8-801",
        "O.C.G.A. § 24-8-803",
        "O.C.G.A. § 24-9-901",
        "O.C.G.A. § 24-10-1002",
        "O.C.G.A. § 24-5-501",
    ],
}

# Privilege rules are not numbered uniformly.  Keep these explicit instead of
# implying a false cross-jurisdictional parallel to FRE 502.
PRIVILEGE_OVERRIDES = {
    "texas": "Tex. R. Evid. 503",
    "new_jersey": "N.J.R.E. 500",
    "michigan": "MRE 501",
    "washington": "Wash. ER 501",
}


def _aliases(canonical: str) -> list[str]:
    aliases = [canonical.replace("§", "Section")]
    aliases.append(canonical.replace(". ", " ").replace("R. Evid.", "Rules of Evidence"))
    return list(dict.fromkeys(value for value in aliases if value != canonical))


def main() -> None:
    entries = []
    for jurisdiction, source_url in SOURCES.items():
        if jurisdiction in SPECIAL:
            citations = SPECIAL[jurisdiction]
        else:
            prefix = PREFIXES[jurisdiction]
            citations = [f"{prefix} {rule}" for rule in STANDARD_RULES]
            if jurisdiction in PRIVILEGE_OVERRIDES:
                citations[-1] = PRIVILEGE_OVERRIDES[jurisdiction]
        for domain, canonical in zip(DOMAINS, citations, strict=True):
            entries.append(
                {
                    "canonical": canonical,
                    "aliases": _aliases(canonical),
                    "jurisdiction": jurisdiction,
                    "domain": domain,
                    "source_url": source_url,
                    "effective_status": "verify_at_freeze",
                }
            )
    output = {
        "schema_version": "4.0",
        "freeze_policy": "current law on final corpus-freeze date",
        "authorities": entries,
    }
    destination = ROOT / "data" / "authority-corpus-v4.json"
    destination.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
