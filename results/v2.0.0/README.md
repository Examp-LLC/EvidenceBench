# EvidenceBench v2.0.0 snapshot

This snapshot evaluates six pinned OpenRouter model routes on a sealed
112-question holdout: 96 FRE-focused questions and 16 evidence-caselaw
questions. The caselaw module contains two questions in every intersection of
federal/state, civil/criminal, and popular/obscure decisions.

Only aggregate results are public. Sealed prompts, annotations, and item-level
model outputs are excluded from git. The manifest records the holdout
commitment, prompt hash, model IDs, token usage, cost, overall metrics, and
dimension-level metrics.

v2 scores are not directly comparable to v1 because the prompt contract,
authority corpus, and holdout composition changed.
