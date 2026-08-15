# Release verification checklist

Release candidate: `v0.2.0`

## Source and CI

- [ ] Work is committed to a feature/release branch, never directly to `main`.
- [ ] `git diff --check` is clean.
- [ ] Runtime tests pass.
- [ ] Ruff and compileall pass.
- [ ] Dependency audit reports no known vulnerability.
- [ ] Feature-branch GitHub Actions succeeds for the exact candidate SHA.
- [ ] PR review/merge gate is complete.
- [ ] Main GitHub Actions succeeds for the exact merged SHA.

## Data and migration

- [ ] A fresh CockroachDB database applies migrations 001 through 004.
- [ ] An existing database applies each remaining migration exactly once.
- [ ] Migration checksum drift is rejected.
- [ ] Runtime uses `trace_app`; migration identity is separate.
- [ ] Runtime roles cannot delete governed state and hold only their required insert/update grants.
- [ ] Tenant-prefixed vector query plan uses `memories_embedding_vector_idx`.

## Runtime

- [ ] Valid signed GitHub delivery returns 202 and creates one task/outbox pair.
- [ ] Replay returns 200 and creates no duplicate.
- [ ] Invalid signature, oversized body, bot event, and wrong repository fail safely.
- [ ] Outbox drains to SQS FIFO and records `published_at`.
- [ ] Successful task reaches `SUCCEEDED` and deletes the SQS message.
- [ ] Synthetic three-attempt failure reaches `DEAD_LETTERED`, copies to DLQ, and alarms.
- [ ] Bedrock malformed output cannot create a comment or memory.
- [ ] Judge console and `/api/status` are read-only and values match CockroachDB.

## Security and operations

- [ ] Remote database certificate verification is enforced.
- [ ] GitHub App permissions and AWS IAM match least-privilege documentation.
- [ ] No secret appears in source, image history, logs, console, CI, or demo recording.
- [ ] Queue/DLQ encryption, retention, redrive, and alarms are verified.
- [ ] Backup/restore and rollback owners are named.
- [ ] Demo preflight and failure fallback are rehearsed.

## Evidence record

Record the current proof identifiers, CI URL, migration result, AWS deployment state, CockroachDB evidence, and demo timestamp in `docs/evidence/core-live-proof.md`. Unchecked live-infrastructure gates must be reported as blockers, never silently treated as passed.
