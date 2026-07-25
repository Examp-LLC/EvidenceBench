# EvidenceBench v4 methodology

Status: evaluator-complete. The July 2026 four-model snapshot is an
**unreviewed research release**, not an official or attorney-validated
leaderboard. The official gates remain unchanged.

## Research question

EvidenceBench v4 measures whether an LLM system can reach sound evidence-law
outcomes, identify the controlling issues, cite authorities that exist in a
pinned corpus, connect conclusions to supplied facts, and complete a
record-grounded work product. It does not measure whether a system can replace
a lawyer or safely practice law without supervision.

## Why two tracks

Harvey's Legal Agent Benchmark demonstrates the value of matter-centric,
long-horizon assignments: an instruction, a closed-universe client matter,
filesystem tools, reviewable deliverables, and atomic criteria. Its first
release described more than 1,200 tasks across 24 practice areas and more than
75,000 expert-written criteria. EvidenceBench adopts the parts that fit
evidence-law research while retaining a controlled doctrine track.

The Doctrine track is a short-horizon diagnostic. It tests rulings, issue
recognition, authority selection, fact grounding, and confidence without tools.
The Matter track is a constrained agent task. It tests document discovery,
record synthesis, evidence analysis, citation, and delivery through read,
literal-search, and output-write tools.

The two tracks answer different questions and are always reported separately.
One headline score is also reported:

`EvidenceBench v4 = 0.50 × Doctrine + 0.50 × Matter`

The fixed equal weighting prevents the larger track from silently dominating.
Every release also reports 40/60 and 60/40 sensitivity values. A submission
must complete both tracks; a missing track does not receive a headline score.

## Doctrine scoring

Each item receives:

- outcome accuracy: 40%;
- issue-code F1: 25%;
- authority F1: 20%;
- issue-to-fact grounding F1: 10%; and
- Brier-derived calibration (`1 - (confidence - correctness)^2`): 5%.

Authority precision counts every nonempty submitted string in its denominator.
Unparseable citations are not discarded. Authority recall is the fraction of
required authority groups for which at least one accepted citation is supplied.
The benchmark separately records invalid, hallucinated, and real-but-unsupported
authorities.

Item scores are not pooled directly. Variants first average within
`family_id`, family scores then average within each of the 12 registered
evidence domains, and the Doctrine track is the unweighted macro-average of
those domain scores. This prevents a four-variant family or a densely sampled
topic from receiving extra headline weight. Confidence intervals resample
families within domains.

## Matter scoring

Expert rubrics are atomic and binary. Scoring dimensions are:

- legal conclusions: 50%;
- authority grounding: 20%;
- factual/record grounding: 15%; and
- deliverable completeness: 15%.

Legal, authority, and factual dimensions use precision, recall, and F1 against
versioned accepted and required sets. Unsupported extra issues, dispositions,
facts, record references, and authorities reduce precision; missing required
material reduces recall. Deliverable criteria remain deterministic binary
checks of benchmark-observed file bytes and required sections. The Matter score
is the weighted mean of legal F1, authority F1, factual/record F1, and
deliverable pass rate.

A task-resolution flag passes only if every critical atomic criterion passes
and every scored dimension equals one. This preserves the useful strictness of
all-pass review without collapsing the headline metric into a mostly-zero
statistic. Criteria marked `review_only` can support qualitative error analysis
but cannot change the official score.

The evaluator derives deliverable existence from the output filesystem; a
model cannot earn credit merely by claiming it wrote a file.

## Determinism and judges

All headline scoring is deterministic. No LLM judge participates in the
official score. A later research release may publish blinded human or LLM
quality ratings as secondary fields, but those ratings must report the judge
prompt, model, agreement, and adjudication protocol and may not be merged into
the v4 score.

Model sampling is temperature zero with a recorded seed when the route supports
it. Each official model result must include at least three independent runs.
The July 2026 research release uses one run per model and reports
family-clustered 95% bootstrap confidence intervals across the frozen corpus;
those intervals measure item-family sampling uncertainty, not run-to-run model
variance.

## Dataset design

Public development families are for integration and evaluator testing.
Official prompts, annotations, matter files, and item-level responses remain in
a private, access-controlled repository. Public and holdout data may not share
a `family_id`. Exact normalized stem overlap is automatically rejected; release
review must additionally test semantic overlap and contamination.

Synthetic matters must use fictional parties and facts. Native PDF and DOCX
records have hashed canonical-text companions so extraction-library variance
cannot change the input presented to a model. Real cases may be used
only when the source, license, holding, current-law status, and retrieval hash
are recorded. Every official item must name an author and at least one
independent reviewer and must have status `APPROVED`. The July 2026 research
corpus is frozen while all 300 items remain `DRAFT`; its public results must
carry that limitation wherever they appear.

The construction target is 240 Doctrine items and 60 Matter tasks. Doctrine
contains 151 migrated v3 concepts and 89 new coverage items, scored as 168
families across 12 domains. Its jurisdiction split is 144 federal and 96 state
items. Matter contains five task archetypes in every domain, with 36 federal
and 24 state tasks. The selected state panel is California, New York, Texas,
Florida, Pennsylvania, New Jersey, Illinois, Ohio, Michigan, Georgia,
Washington, and Arizona.
The 89 new items use this panel. Migrated legacy precedent concepts retain
their original jurisdictions, including several states outside the panel, so
historical lineage is not silently rewritten.

## Required reporting

An official result publishes:

- benchmark and corpus versions, dataset commitments, and prompt versions;
- exact model slug and OpenRouter route metadata available for the run;
- parameters, tool policy, maximum turns, token usage, cost, failures, and
  fallback behavior;
- track scores, submetrics, task-resolution rate, invalid and hallucinated
  citation counts;
- family-clustered confidence intervals and weighting sensitivity; and
- all deviations from the reference harness.

The July 2026 research release publishes the same aggregate fields where
available, plus an explicit zero-of-300 review count, one-run disclosure, and
`unreviewed_research_release` status. Item-level prompts, annotations,
responses, transcripts, and scores remain private.

## Known limitations

EvidenceBench focuses on United States federal evidence doctrine and a
population-and-region-selected 12-state panel; it does not claim complete
coverage of every state. Development fixtures are small and synthetic.
Deterministic issue codes and rubrics reduce
judge variance but can under-credit unanticipated sound analysis; challenges
must be adjudicated and incorporated prospectively in a versioned annotation.
OpenRouter can route the same model slug through different upstream providers,
so an official run must pin and disclose route behavior where the service
permits it.

## References

- Harvey, “Open-Sourcing Harvey's Long Horizon Legal Agent Benchmark,”
  <https://www.harvey.ai/blog/introducing-harveys-legal-agent-benchmark>
- Harvey LAB source, <https://github.com/harveyai/harvey-labs>
- Vals AI LAB results and harness description,
  <https://www.vals.ai/benchmarks/hlab>
