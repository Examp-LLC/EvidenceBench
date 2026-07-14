# EvidenceBench v1 methodology

EvidenceBench evaluates closed-book responses to attorney-authored evidence
questions. A model receives a multiple-choice question and must return JSON
containing one option ID, a concise explanation, and supporting FRE or official
reporter citations. No browsing, retrieval, tools, or external authority text
is available to the model.

## Dataset

- Development set: 24 public questions licensed CC BY-NC 4.0.
- Official v2 holdout: 112 sealed questions—96 FRE-focused and 16 caselaw;
  only aggregate results are published.
- Every item has a stable ID, category, difficulty, rationale, gold answer,
  required citation groups, accepted citations, corpus version, and attorney
  review record.

## Scoring

Answer accuracy is exact option match. Citation precision is accepted cited
rules divided by all cited rules. Citation recall is the share of required
citation groups satisfied. Citation F1 is their harmonic mean. A citation that
does not exist in the frozen FRE corpus is hallucinated; a real but
unannotated authority is unsupported. Overall score is 70% answer accuracy and
30% authority-citation F1. Caselaw results are additionally aggregated across
federal/state, civil/criminal, and popular/obscure dimensions.

## Reproducibility

Every official release records the dataset hash, prompt hash, model ID,
provider route, timestamp, parameters, token usage, cost, corpus version, and
aggregate results. The public development set permits independent verification
of prompt rendering and scoring without exposing the official holdout.

## Limits

EvidenceBench measures this specific closed-book task. It does not measure
case-law research, jurisdiction-specific practice, current good-law status,
or the safety of using a model in litigation.

## Authority freeze

v1 uses the Federal Rules effective December 1, 2025. As of July 2026, the
Rule 801(d)(1)(A) amendment has been transmitted to Congress but is not
effective until December 1, 2026 unless Congress acts; v1 excludes it.
