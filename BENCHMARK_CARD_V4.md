# EvidenceBench v4 benchmark card

## Intended use

EvidenceBench v4 is a research evaluation for evidence-law reasoning and
closed-universe legal-agent execution. Appropriate uses include model
comparison, harness ablation, retrieval/tool experiments, error analysis, and
targeted post-training research.

It is not legal advice, a bar examination, a general legal-intelligence score,
or evidence that a system can work without attorney review.

## Unit of evaluation

Doctrine units are reviewed applied-ruling fact patterns. Matter units are
closed-universe workspaces containing instructions, documents, expected
deliverables, and atomic criteria. `family_id` is the resampling and leakage
boundary.

## Public data

`data/v4/dev` contains eight Doctrine items and two Matter tasks. All are
synthetic and marked `DRAFT`. They exercise schemas, runners, validators, and
scorers. They must not be described as the v4 holdout or used for an official
leaderboard.

## Private data

The corpus remains under Objection Academy control in a private
source-controlled repository. A public release commits to it by cryptographic
hash and reports counts and coverage without releasing answers or item-level
outputs. The July 2026 research corpus contains 240 Doctrine candidates and 60
Matter candidates; none had completed professional review at run time.

## Primary metric

The single overall score is the equal-weighted mean of Doctrine and Matter.
Both track scores and all submetrics remain mandatory, because equal headline
scores can conceal materially different capabilities.

Doctrine is family-first and then macro-averaged across 12 domains. Matter
penalizes unsupported extra findings through precision-aware legal, authority,
and factual F1. A separate all-critical-criteria task-resolution rate remains a
strict secondary metric.

## Quality controls

- independent legal review is required for every official item;
- authors cannot serve as their own sole reviewer;
- exact IDs, document hashes, citation existence, and rubric consistency are
  validated automatically;
- DRAFT data fails the official validation command;
- public/holdout family and exact-stem overlap is rejected;
- headline scoring is deterministic;
- uncertainty is clustered by task family; and
- official results require repeated runs and disclosure of failures and costs.

The July 2026 snapshot does not satisfy the independent-review or repeated-run
controls. It is published only as an unreviewed research release so researchers
can inspect the evaluator and initial measurement behavior while professional
review remains open.

## Foreseeable risks

Contamination can inflate results. Synthetic matters may not capture the
ambiguity of real litigation records. The pinned authority corpus can become
stale. Rubric incompleteness can penalize a legally sound alternative.
Provider routing can introduce unobserved model variation. Volunteer review can
create selection bias and inconsistent depth.

Mitigations include a sealed family-level holdout, annual authority freezes,
adjudicated challenge logs, reviewer calibration, route disclosure, and
prospective versioning rather than silent answer changes.

## Maintainer

Objection Academy. Security or embargo concerns should be reported privately to
dylan@examp.com.
