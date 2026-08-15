# Trace live core proof

Captured on **2026-08-15** against real GitHub, Amazon Bedrock, and CockroachDB Cloud services.

## Acceptance result

1. [PR #4](https://github.com/vivekyarra/Trace/pull/4) merged at `34dc3821c41ac85e64a881dfe8e6bafa03740df8`.
2. Trace task `ee4e5da8-c764-4278-9ef5-1fc475185b2f` created `TRACE-MEMORY-00401` with PR-source provenance.
3. Amazon Titan Text Embeddings V2 produced the stored 1024-dimensional vector.
4. Open [PR #5](https://github.com/vivekyarra/Trace/pull/5) triggered tenant-scoped retrieval and Bedrock reranking.
5. Retrieval `c12d9de4-0f8f-4c79-9b8b-1390b62c9590` selected the governing memory and blocked the review.

PR #5 remains open and unmerged.

## Live evidence chain

| Stage | Identifier |
|---|---|
| PR #4 task | `ee4e5da8-c764-4278-9ef5-1fc475185b2f` |
| PR #4 comment | [`5302264557`](https://github.com/vivekyarra/Trace/pull/4#issuecomment-5302264557) |
| Memory | `TRACE-MEMORY-00401` / `e9ba2d0e-5543-4e06-a8e0-e2b6640dc062` |
| Source | `https://github.com/vivekyarra/Trace/pull/4` |
| Created and embedded | `2026-08-15T12:37:06Z` |
| Embedding | `amazon.titan-embed-text-v2:0`, version `v2`, 1024 dimensions |
| PR #5 task | `4abf1168-1b18-4563-b44b-5cc58fc3d049` |
| Retrieval | `c12d9de4-0f8f-4c79-9b8b-1390b62c9590` |
| Retrieval time | `2026-08-15T12:37:08Z` |
| Reasoning model | `apac.amazon.nova-pro-v1:0` |
| Bedrock rerank score | `0.30`, selected `true` |
| PR #5 comment | [`5302264619`](https://github.com/vivekyarra/Trace/pull/5#issuecomment-5302264619) |

The two GitHub comments are the only Trace proof comments on their respective pull requests. Their task IDs and external effect IDs match the CockroachDB `agent_tasks` and `agent_actions` rows.

## Consequence

The PR #5 review contains one `MEMORY_CONFLICT` governed by `TRACE-MEMORY-00401`. Retrieval alone is not counted as consequence. `memory_changed_review` is true because the selected memory produced that conflict finding; without the memory, the finding is absent.

## Verification

- Local: `py -m pytest tests` — 44 passed before publication.
- Changed-file lint and `git diff --check` — passed.
- CockroachDB Managed MCP: the `Trace Auditor` workspace agent is restricted to read-only Managed MCP tools and verifies the joined memory, source, scope, retrieval, candidate, task, action, and consequence rows.
- Managed MCP audit time: `2026-08-15T12:48:09Z`; verdict `VERIFIED`, published effect `5302264619`, `memory_changed_review=true`.
- Distributed vector indexing is configured. The tiny proof corpus does not establish optimizer index selection or acceleration.

The judge-facing AWS deployment is recorded in [`aws-demo-deployment.md`](aws-demo-deployment.md).
