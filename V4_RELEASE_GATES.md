# EvidenceBench v4 release gates

No result is “official EvidenceBench v4” until all gates pass.

The July 2026 four-model snapshot is permitted only under the distinct label
`unreviewed_research_release`. It does not waive, satisfy, or weaken any gate
below and must not be described as an official or attorney-validated
leaderboard.

## Data gate

- [ ] Target sample and coverage plan are frozen before model runs.
- [ ] Every item/task is `APPROVED` by an author and an independent reviewer.
- [ ] High-risk or disputed annotations have adjudication records.
- [ ] Citation corpus and effective dates are verified.
- [ ] Matter document hashes match.
- [ ] Public/holdout family, exact-text, and semantic leakage audits pass.
- [ ] No benchmark item is a deterministic transformation of a public item.

## Measurement gate

- [ ] Gold-response tests cover every scoring branch.
- [ ] Adversarial tests cover malformed JSON, path traversal, missing outputs,
      invalid citations, fabricated citations, refusals, and partial failures.
- [ ] A frozen scoring version and prompt version are recorded.
- [ ] Family-clustered confidence intervals are reported.
- [ ] Doctrine family-first and 12-domain macro-averaging are independently
      recomputed from released aggregate records.
- [ ] Precision attacks with extra issues, citations, facts, and record
      references are covered by gold-response tests.
- [ ] At least three runs per system are completed.
- [ ] Track-weight sensitivity is reported.
- [ ] Human agreement and adjudication statistics are published.
- [ ] All PDF/DOCX canonical companions match the reviewed native documents,
      and a batch render audit finds no truncation or malformed pages.

## Execution gate

- [ ] Exact model IDs and OpenRouter route/fallback policy are recorded.
- [ ] Matter tools cannot read outside documents or write outside outputs.
- [ ] Network and shell access are unavailable to the model.
- [ ] Time, token, turn, and cost limits are identical across compared systems.
- [ ] Failures remain failures; only retryable transport errors are retried.
- [ ] Transcripts and item-level outputs remain sealed for audit.

## Publication gate

- [ ] Benchmark card and methodology match the executable code.
- [ ] Dataset and protocol SHA-256 commitments are public.
- [ ] A preregistered analysis plan identifies the primary comparison.
- [ ] No ranking claim is made when confidence intervals and repeated-run
      variation do not support it.
- [ ] Aggregate results include failure, invalid-citation, and
      hallucinated-citation counts.
- [ ] The release clearly distinguishes public development data, private
      holdout data, and any unreviewed candidate pool.

Passing the software tests alone is insufficient. Until the legal-review and
measurement gates pass, the implementation is a v4 candidate.
