# EvidenceBench

EvidenceBench is Objection Academy's evidence-law benchmark. v4 adds a
closed-book Doctrine track and a closed-universe Matter agent track while
preserving the v3 evaluator for reproducibility. It is an educational research
project, not legal advice or a substitute for professional legal research.

## v4 status

The v4 evaluator, schemas, OpenRouter runners, scoring, integrity checks, public
development fixtures, and private 300-item candidate corpus are implemented.
The July 2026 four-model snapshot is an **unreviewed research release**: all
gold labels remain `DRAFT`, zero professional reviews were complete at run
time, and only one run was made per model. EvidenceBench v4 must not be
presented as an official or attorney-validated leaderboard until the
legal-review and release gates in [V4_RELEASE_GATES.md](V4_RELEASE_GATES.md)
are complete.

Identity-verified legal professionals can help complete that gate through the
[EvidenceBench v4 reviewer program](REVIEWING_V4.md).

v4 reports a single overall score:

`0.50 × Doctrine score + 0.50 × Matter score`

It also reports both track scores, submetrics, strict Matter task-resolution
rate, family- and domain-aware 95% bootstrap intervals, and 40/60 versus 60/40
weight sensitivity. Doctrine variants are averaged within families and then
macro-averaged across 12 domains. Matter uses precision-aware F1 so unsupported
extra issues, authorities, facts, and record references reduce the score.
Headline scoring is deterministic; LLM judges cannot change the official score.

See [METHODOLOGY_V4.md](METHODOLOGY_V4.md) and
[BENCHMARK_CARD_V4.md](BENCHMARK_CARD_V4.md). The design rationale and the
specific lessons taken from Harvey LAB are in
[HARVEY_LAB_COMPARISON.md](HARVEY_LAB_COMPARISON.md).

## What is public

- A 24-question development set and its scoring annotations.
- The prompt contract, scoring code, model manifests, methodology, and website
  export format.
- Aggregate research or official results with their release and review status.

## What is sealed

The v3 official holdout contains 96 FRE-focused questions plus a 55-question
caselaw module. The original 16-case matrix remains balanced across
federal/state, civil/criminal, and popular/obscure decisions. A new 33-question
tranche covers every unique, citable decision from 2020–2024 classified as
published in the public-domain DOJ/NIJ Post-PCAST dataset cataloged by
[Data.gov](https://catalog.data.gov/dataset/post-pcast-court-decisions-assessing-the-admissibility-of-forensic-science-evidence).
Six additional published 2026 decisions are frozen from official federal court,
GovInfo, and New York Official Reports sources.
It is attorney-reviewed,
and never distributed with the Objection Academy app. Its prompts,
annotations, and item-level results are not public. Once approved, published
manifests will commit to the holdout with a SHA-256 hash, counts, categories,
protocol hash, and aggregate metrics.

The private v4 research corpus contains 240 Doctrine candidates and 60 Matter
tasks. These remain a candidate pool—not an official holdout—until every item
passes the review and freeze gates.

## v4 commands

```bash
uv run --python 3.12 evidencebench validate-v4 --track doctrine --input data/v4/dev/doctrine.jsonl
uv run --python 3.12 evidencebench validate-v4 --track matter --input data/v4/dev/matter
uv run --python 3.12 evidencebench score-v4 --track doctrine --input data/v4/dev/doctrine.jsonl --responses results/v4/doctrine-responses.jsonl --output results/v4/doctrine-scores.json
uv run --python 3.12 evidencebench score-v4 --track matter --input data/v4/dev/matter --responses results/v4/matter-responses.jsonl --output results/v4/matter-scores.json
uv run --python 3.12 evidencebench summarize-v4 --doctrine-scores results/v4/doctrine-scores.json --matter-scores results/v4/matter-scores.json --output results/v4/summary.json
uv run --python 3.12 evidencebench manifest-v4 --doctrine data/v4/dev/doctrine.jsonl --matter data/v4/dev/matter --output results/v4/development-manifest.json
```

The runners use OpenRouter and read `OPENROUTER_API_KEY` from the process
environment. No key belongs in a tracked manifest. Doctrine runs have tools
disabled. Matter runs expose only document listing, document reading, literal
search, and output writing; the model receives no shell or network tool.

```bash
uv run --python 3.12 evidencebench run-v4-doctrine --manifest models/v4/openrouter-doctrine.example.json --items data/v4/dev/doctrine.jsonl --output results/v4/doctrine-responses.jsonl
uv run --python 3.12 evidencebench run-v4-matter --manifest models/v4/openrouter-matter.example.json --tasks data/v4/dev/matter --output results/v4/matter-run
```

## v3 commands

```bash
uv run --python 3.12 evidencebench validate data/dev-v1.jsonl
uv run --python 3.12 evidencebench score --questions data/dev-v1.jsonl --responses results/fixtures/dev-responses.jsonl
uv run --python 3.12 evidencebench export-web --manifest results/v1.0.0/manifest.json --output exports/latest.json
```

The v3 `run` command is deliberately opt-in. It requires a model manifest plus the provider
credentials named in that manifest. It never enables web search or tools.

## v3 metrics

Each item receives answer accuracy, authority precision, authority recall,
citation F1, citation-existence status, and unsupported-citation status.
Official overall score is `0.70 * answer accuracy + 0.30 * citation F1`.
Missing citations, refusals, and invalid structured outputs score zero for
authority F1. Caselaw questions require a frozen reporter, slip-opinion, or
published LEXIS citation.

## Authority corpus

v3 uses the Federal Rules of Evidence in effect December 1, 2025. The pending
Rule 801 amendment effective December 1, 2026 is excluded.

## v3 official-run gate

The sealed holdout has an attorney-approved citation and content review record
and is committed in each public manifest by SHA-256. The normalized government
source snapshot is public; sealed questions and item-level model outputs are not.
