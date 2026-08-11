# Trace proof screenshots

These captures contain no database passwords, GitHub tokens, or AWS credentials.

| File | Proof |
|---|---|
| `01-aws-titan-1024-live.jpg` | Live Titan embedding response dimension is 1024. |
| `02-pr-a-merged-source.jpg` | PR A is merged and contains the source decision. |
| `03-pr-b-open-conflict.jpg` | PR B is open with the conflicting TTL-only authorization cache. |
| `04-cockroach-vector-schema-live.jpg` | Live CockroachDB schema has `VECTOR(1024)` and the vector index. |
| `05-anthropic-use-case-form.jpg` | AWS Anthropic use-case activation screen used for the live run. |
| `06-branch-ci-green.jpg` | Earlier production-hardening branch CI passed. |
| `07-live-core-acceptance.jpg` | CloudShell's real end-to-end evidence JSON, including task/comment/memory/retrieval IDs. |
| `08-cockroach-memory-vector-provenance.jpg` | Live memory is ACTIVE, Titan-embedded, and linked to PR A. |
| `09-cockroach-retrieval-hybrid-selection.jpg` | Live vector distance, hybrid score, selected memory, and Bedrock selection reason. |
| `10-pr-b-guardkeeper-source-citation.jpg` | Guardkeeper cites `TRACE-MEMORY-00401`, PR A, and the retrieval ID on PR B. |
| `11-pr-a-created-embedded-memory.jpg` | Trace's idempotent PR A comment reports the created embedded memory. |
| `12-final-code-ci-green.jpg` | Final code commit `3f40f86` passes GitHub Actions. |
| `13-cockroach-bedrock-model-selection.jpg` | Live retrieval row records Claude 3 Haiku and `Bedrock_selected=true`. |
