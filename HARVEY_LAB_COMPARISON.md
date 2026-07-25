# Harvey LAB and EvidenceBench v4

This design comparison was frozen on July 25, 2026. Harvey LAB is evolving, so
counts are descriptive rather than permanent.

| Dimension | Harvey LAB | EvidenceBench v4 |
|---|---|---|
| Primary target | Long-horizon legal work across many practice areas | Evidence-law doctrine and litigation-record analysis |
| Unit | Matter files, instruction, and reviewable work product | Doctrine item or closed-universe evidence matter |
| Breadth | Harvey's May 2026 announcement reported more than 1,200 tasks, 24 practice areas, and 75,000 expert-written criteria | Private research corpus has 240 Doctrine items and 60 Matter tasks; 8 Doctrine and 2 Matter fixtures are public |
| Tools | File read/edit/write, glob, grep, bash, and document-format skills | List/read/search documents and write outputs; no model shell or network |
| Core grading | Semantic LLM judge for each binary criterion; task score uses all-pass | Deterministic structured criteria; weighted track score plus all-critical Matter resolution |
| Citation treatment | A rubric can require citations | Citations are normalized against a pinned authority corpus; invalid, nonexistent, and unsupported authorities are separated |
| Uncertainty | Results emphasize all-pass and criterion pass rates | Family-clustered 95% bootstrap intervals, repeated-run requirement, and weight sensitivity |
| Contamination strategy | Public tasks plus a held-out test set | Public DRAFT development set plus a private family-separated candidate corpus with a public cryptographic commitment |

## Lessons adopted

Matter-centric assignments are a better frontier-model test than more
multiple-choice variants. v4 therefore requires agents to find facts across
files and create artifacts. Criteria are atomic, attached to material legal,
authority, factual, and delivery requirements, and critical omissions produce
a strict task-resolution failure. The harness records transcripts and actual
deliverables.

LAB also makes a strong case for treating the harness as part of the evaluated
system. EvidenceBench records prompt versions, tool policy, route, token and
turn limits, failures, and costs rather than labeling a result with only a
model name.

## Deliberate differences

EvidenceBench retains a Doctrine track because controlled diagnostics can
localize whether a failure came from the legal rule, issue spotting, authority
selection, factual grounding, or agent execution. A Matter-only score cannot
separate these causes cleanly.

The official v4 score does not depend on an LLM judge. LAB's semantic judge is
flexible for diverse prose work product, but it adds judge-model sensitivity,
cost, and a second failure surface. EvidenceBench narrows its outputs enough to
score headline criteria deterministically. Human and LLM qualitative review
may be published separately.

EvidenceBench also measures citation reliability as a first-class construct.
An unparseable citation remains in the precision denominator, and the evaluator
distinguishes a fabricated authority from a real authority omitted from the
annotation.

## Improvements over EvidenceBench v3

v3 was useful for closed-book answer and citation testing but was too narrow
for frontier agent research. Its multiple-choice format encouraged saturation;
its public development and mechanically varied holdout families created
leakage risk; an explanation was requested but not scored; invalid citations
could be normalized away; and aggregate tables lacked uncertainty.

v4 addresses those problems with:

- independent family IDs and a public/holdout overlap audit;
- a private, source-controlled holdout;
- structured issue and fact grounding;
- a long-horizon Matter track;
- explicit DRAFT/APPROVED review state enforced by the official validator;
- retry-on-transport-only execution;
- deterministic scoring and citation error accounting;
- one preregistered overall score with mandatory track disclosure; and
- clustered confidence intervals, run replication, and weighting sensitivity.

## What remains before an official launch

The candidate corpus has a frozen coverage matrix, original families, private
provenance, review packets, and deterministic validation. It still needs
independent professional review, adjudication, replicated model runs, external
reproduction, and prospective challenge handling. Until those gates pass, the
July 2026 results remain an unreviewed research release rather than an official
leaderboard.

## Sources

- Harvey announcement:
  <https://www.harvey.ai/blog/introducing-harveys-legal-agent-benchmark>
- Harvey LAB repository:
  <https://github.com/harveyai/harvey-labs>
- Harvey evaluation methodology:
  <https://github.com/harveyai/harvey-labs/blob/main/docs/eval-strategies.md>
- Vals AI independent benchmark page:
  <https://www.vals.ai/benchmarks/hlab>
