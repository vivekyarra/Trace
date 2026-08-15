# Trace live core proof

Captured on **2026-08-15** against real GitHub, Amazon Bedrock, AWS Lambda, and CockroachDB Cloud services.

## Acceptance result

1. [PR #4](https://github.com/vivekyarra/Trace/pull/4) merged at `34dc3821c41ac85e64a881dfe8e6bafa03740df8`.
2. Trace task `ee4e5da8-c764-4278-9ef5-1fc475185b2f` created `TRACE-MEMORY-00401` with PR-source provenance and a Titan 1024-dimensional embedding.
3. [PR #5](https://github.com/vivekyarra/Trace/pull/5) triggered tenant-scoped retrieval and Bedrock reranking.
4. Retrieval `c12d9de4-0f8f-4c79-9b8b-1390b62c9590` selected the governing memory and produced the published conflict review.
5. The public Lambda now invokes the production `trace_memory.agents.Guardkeeper` pipeline, not a duplicate implementation, and all three live conflict presets pass.

PR #5 remains open and unmerged.

## Durable memory-to-action chain

| Stage | Identifier |
|---|---|
| PR #4 task | `ee4e5da8-c764-4278-9ef5-1fc475185b2f` |
| PR #4 comment | [`5302264557`](https://github.com/vivekyarra/Trace/pull/4#issuecomment-5302264557) |
| Memory | `TRACE-MEMORY-00401` / `e9ba2d0e-5543-4e06-a8e0-e2b6640dc062` |
| Source | `https://github.com/vivekyarra/Trace/pull/4` |
| Embedding | `amazon.titan-embed-text-v2:0`, version `v2`, 1024 dimensions |
| PR #5 task | `4abf1168-1b18-4563-b44b-5cc58fc3d049` |
| Retrieval | `c12d9de4-0f8f-4c79-9b8b-1390b62c9590` |
| Reasoning model | `apac.amazon.nova-pro-v1:0` |
| Rerank result | score `0.30`, selected `true` |
| Published review | [`5302264619`](https://github.com/vivekyarra/Trace/pull/5#issuecomment-5302264619) |

The PR #5 review contains one `MEMORY_CONFLICT` governed by `TRACE-MEMORY-00401`. Retrieval alone is not counted as consequence. The stored receipt has `memory_changed_review=true`: without the selected memory, that finding is absent.

## GitHub App proof

The actual GitHub App `trace-memory-governor` was installed only on `vivekyarra/Trace`. Its accepted repository permissions are metadata/content read and issues/pull-request read/write. Runtime code mints installation tokens from App ID `4604859` and installation ID `153959613`; no personal access token is required.

The App posted [comment `5302940425`](https://github.com/vivekyarra/Trace/pull/5#issuecomment-5302940425) as `trace-memory-governor[bot]`. That comment is an authentication and deployment proof, separate from durable production action `5302264619`, so it is not falsely joined to the original task/action chain.

## Live Lambda verification

Function `trace-judge-console` in `ap-south-1` is deployed from the shared production path. Code SHA-256: `XBhcMs1T+Tb7m2/aHh+gvA83H6GSpN2adkFlL9GqxvI=`. Reserved concurrency is 2; `/api/status` reports `live-read-only`, `replay_mode=false`, and `write_routes=0`.

| Preset | Run time (UTC) | Selected memory | Verdict | Embed / retrieve / reason | Total |
|---|---|---|---|---|---|
| Authorization revocation | `2026-08-15T15:29:23.163874Z` | `TRACE-MEMORY-00401` | `CONFLICT · HIGH` | 239 / 1117 / 846 ms | 2203 ms |
| Durable command architecture | `2026-08-15T15:29:24.468769Z` | `TRACE-MEMORY-00402` | `CONFLICT · MEDIUM` | 203 / 218 / 807 ms | 1230 ms |
| Incident secret logging | `2026-08-15T15:29:25.875054Z` | `TRACE-MEMORY-00403` | `CONFLICT · HIGH` | 204 / 207 / 943 ms | 1355 ms |

Each result reports pipeline `trace_memory.agents.Guardkeeper`, `memory_changed_review=true`, and model `apac.amazon.nova-pro-v1:0`.

## CockroachDB evidence

- `TRACE-MEMORY-00402` and `TRACE-MEMORY-00403` were seeded in the live tenant with source, scope, and Titan embedding provenance.
- Migration `004_runtime_least_privilege.sql` was applied and reverified. Runtime roles have no `DELETE`; unnecessary organization, repository, and action writes are revoked; the read-only judge role inherits only `trace_mcp_reader`.
- A 10,000-row, 1024-dimensional production-schema benchmark uses `memories_embedding_vector_idx` with exact tenant-prefix spans and no full scan.
- Across 30 `EXPLAIN ANALYZE` executions, database execution was 76 ms minimum, 79.5 ms median, and 90 ms p95; the vector operator was 15 ms minimum, 15.5 ms median, and 20 ms p95. See [`vector-explain.txt`](vector-explain.txt).

## Managed MCP receipt

The CockroachDB Cloud Managed MCP connection had Read Data only. The Trace Auditor first listed tables and schemas, then issued one bounded joined `SELECT` across the exact memory → retrieval → action chain.

```text
TRACE AUDITOR · LIVE MANAGED MCP · READ ONLY
Audit time: 2026-08-15T15:36:38.948592Z
Verdict: VERIFIED
Memory: TRACE-MEMORY-00401 · ACTIVE · amazon.titan-embed-text-v2:0
Source: https://github.com/vivekyarra/Trace/pull/4 · 34dc3821c41ac85e64a881dfe8e6bafa03740df8
Retrieval: c12d9de4-0f8f-4c79-9b8b-1390b62c9590 · selected=true · apac.amazon.nova-pro-v1:0
Review effect: 5302264619
Memory changed review: true
Why: The selected memory produced the published HIGH MEMORY_CONFLICT and the stored counterfactual says that finding is absent without it.
Failures: none
— Trace Auditor
```

The judge-facing AWS deployment is recorded in [`aws-demo-deployment.md`](aws-demo-deployment.md).

## Local release verification

- Python 3.12.13: **51 tests passed**.
- Ruff, `compileall`, and `git diff --check`: passed.
- Source distribution and wheel build: passed; the wheel installed in an isolated environment and `trace-runtime --help` passed.
- `cfn-lint infra/aws.yaml`: passed.
- `pip-audit --skip-editable`: no known vulnerabilities after upgrading the verifier to patched pip `>=26.1.2`.
- The local Docker daemon was unavailable; the repository CI performs the required container build and smoke test on the exact PR SHA.
