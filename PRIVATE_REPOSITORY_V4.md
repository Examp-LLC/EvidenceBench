# Private v4 repository contract

The official holdout should live in a dedicated private repository controlled
by Objection Academy, rather than in the public website repository.

Recommended layout:

```text
EvidenceBench-Private/
  candidates/doctrine/
  candidates/matter/
  holdout/v4/doctrine.jsonl
  holdout/v4/matter/
  reviews/
  adjudications/
  runs/raw/
  releases/
```

Only reviewed data moves from `candidates` to `holdout`. Branch protection
should require an authorized review for holdout, review, adjudication, and
release paths. Access should be limited to maintainers and reviewers who need
the sealed materials. The website should receive only signed or hashed release
metadata and aggregate results.

The private repository must not contain API keys, provider credentials, or
unredacted confidential client material. Use synthetic or properly licensed
records. Item-level model outputs and transcripts remain private because they
can reveal holdout content.

Every public release should include commitments for the Doctrine data, each
Matter task manifest and document inventory, scoring code, prompt templates,
and run protocol. A verifier with private access must be able to reproduce those
hashes from a clean checkout.
