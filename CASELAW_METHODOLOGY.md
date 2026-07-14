# EvidenceBench caselaw module

The v2 sealed holdout adds 16 evidence-caselaw questions to the 96 FRE-focused
items. The caselaw module is balanced across eight intersections:

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

The v2 prompt asks for legal authorities. FRE questions continue to require
normalized FRE citations, while caselaw questions require official reporter
citations. Answer accuracy, authority precision, authority recall, authority
F1, hallucination rate, and the 70/30 overall formula are otherwise unchanged.
