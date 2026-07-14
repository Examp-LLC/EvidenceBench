# EvidenceBench

EvidenceBench is Objection Academy's public benchmark for evidence-law answer
accuracy and legal-authority citation reliability. It is an
educational research project, not legal advice and not a substitute for
professional legal research.

## What is public

- A 24-question development set and its scoring annotations.
- The prompt contract, scoring code, model manifests, methodology, and website
  export format.
- Aggregate official results after an approved sealed holdout run, including
  separate FRE and caselaw dimensions.

## What is sealed

The v2 official holdout contains 96 FRE-focused questions plus a 16-question
caselaw module balanced across federal/state, civil/criminal, and
popular/obscure decisions. It is attorney-reviewed,
and never distributed with the Objection Academy app. Its prompts,
annotations, and item-level results are not public. Once approved, published
manifests will commit to the holdout with a SHA-256 hash, counts, categories,
protocol hash, and aggregate metrics.

## Commands

```bash
uv run --python 3.12 evidencebench validate data/dev-v1.jsonl
uv run --python 3.12 evidencebench score --questions data/dev-v1.jsonl --responses results/fixtures/dev-responses.jsonl
uv run --python 3.12 evidencebench export-web --manifest results/v1.0.0/manifest.json --output exports/latest.json
```

`run` is deliberately opt-in. It requires a model manifest plus the provider
credentials named in that manifest. It never enables web search or tools.

## Metrics

Each item receives answer accuracy, authority precision, authority recall,
citation F1, citation-existence status, and unsupported-citation status.
Official overall score is `0.70 * answer accuracy + 0.30 * citation F1`.
Missing citations, refusals, and invalid structured outputs score zero for
authority F1. Caselaw questions require an official reporter citation.

## Authority corpus

v1 uses the Federal Rules of Evidence in effect December 1, 2025. The pending
Rule 801 amendment effective December 1, 2026 is excluded from v1.

## Official-run gate

The sealed 96-question holdout has an attorney-approved citation and content
review record and is committed in the public manifest by SHA-256. The initial
leaderboard remains empty until six credentialed, closed-book provider runs
complete and their signed aggregate results are exported.
