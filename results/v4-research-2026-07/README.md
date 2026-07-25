# EvidenceBench v4 July 2026 research snapshot

This directory contains aggregate-only results for four frontier model families
evaluated on the frozen 240-item Doctrine and 60-task Matter candidate corpus.

This is an **unreviewed research release**, not an official or
attorney-validated leaderboard:

- zero of 300 gold annotations had completed independent professional review;
- each model was run once, so no run-to-run variance estimate is available;
- item-level prompts, gold annotations, responses, transcripts, deliverables,
  and scores remain sealed;
- confidence intervals reflect family-clustered corpus resampling only; and
- all calls used OpenRouter with provider fallback disabled.

`aggregate-results.json` will contain the corpus commitment, exact model IDs,
parameters, cost and failure disclosures, track metrics, authority-error counts,
confidence intervals, and the single 50/50 overall score.

The evaluator, model manifests, methodology, and public development fixtures
are in this repository. Professional reviewers may volunteer through
[the v4 reviewer program](../../REVIEWING_V4.md).
