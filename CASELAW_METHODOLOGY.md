# EvidenceBench caselaw module

The v3 sealed holdout contains 55 evidence-caselaw questions alongside the 96
FRE-focused items. Its original 16-question module is balanced across eight intersections:

- federal and state authority;
- civil and criminal proceedings; and
- widely cited and less familiar decisions.

Each intersection contains two questions. Popularity is a sampling stratum,
not a claim about precedential weight. The questions test holdings concerning
expert gatekeeping, scientific evidence, eyewitness identification, hearsay,
prior statements, and Rule 403.

Case existence and citation form are validated against a frozen reporter index.
Question rationales were checked against official court publications or official
reporters where available. The benchmark requires a reporter citation; a case
name without a reporter citation does not satisfy citation recall.

The v3 prompt asks for legal authorities. FRE questions continue to require
normalized FRE citations, while caselaw questions require official reporter
citations. Answer accuracy, authority precision, authority recall, authority
F1, hallucination rate, and the 70/30 overall formula are otherwise unchanged.

## Data.gov/DOJ-NIJ expansion

The 33-question v3 tranche uses every unique, citable decision dated 2020–2024
that the public-domain DOJ/NIJ Post-PCAST decisions table labels published.
This triples caselaw coverage from 16 to 49 questions and adds explicit year,
recency, publication-status, forensic-discipline, and source dimensions. The
government table is frozen as a normalized 124-row JSON snapshot with hashes.

Each sealed question asks for the evidentiary decision effect recorded for one
case and requires that case's published reporter, slip-opinion, or LEXIS
citation. Dataset labels and summaries are preserved in the sealed rationale.
The source is primarily forensic and criminal; published decisions in this
slice include 21 state and 12 federal cases, but only three civil cases. Scores
therefore report source-specific dimensions rather than implying balance.

## Published 2026 decisions

Six current decisions supplement the Data.gov tranche: four published federal
appellate opinions and two decisions in New York's Official Reports. They cover
Rule 702 expert gatekeeping, Rule 403 and stipulations, documentary evidence,
expert disclosure, hearsay exceptions, and the Confrontation Clause. Because
official reporter pagination may not yet exist for recently issued opinions,
the frozen authority index accepts the court docket or New York slip citation.
The public `data/recent-caselaw-2026.json` file records official source URLs and
SHA-256 hashes; no secondary case summary is treated as authority.
