# Trace live core proof

Captured on 2026-08-11 against real GitHub, Amazon Bedrock, and CockroachDB Cloud services.

## Acceptance result

The required path completed successfully:

1. [PR A #4](https://github.com/vivekyarra/Trace/pull/4) merged into the isolated demo base at commit `7bd53303e786afd41c8fbc9b22147257387a1a2d`.
2. Trace created `TRACE-MEMORY-00401` (`679be7b7-1476-4c7e-aacb-318f0cab3e80`) with PR-source provenance.
3. Amazon Titan Text Embeddings V2 produced and CockroachDB stored the 1024-dimensional vector.
4. Open [PR B #5](https://github.com/vivekyarra/Trace/pull/5) triggered CockroachDB vector candidate retrieval backed by a configured distributed vector index, followed by the production `HybridRanker` and Bedrock reranking.
5. Retrieval `8033c0ed-9596-4aeb-ba95-e31d5825ac34` selected the memory and Trace's Guardkeeper comment cited PR A.

PR B remains open and `main` was not changed.

## Immutable evidence chain

| Stage | Identifier |
|---|---|
| PR A task | `4facb438-2917-488b-b500-fcfd45565905` |
| PR A GitHub comment | `5256842332` |
| Memory | `TRACE-MEMORY-00401` / `679be7b7-1476-4c7e-aacb-318f0cab3e80` |
| Source | `https://github.com/vivekyarra/Trace/pull/4` |
| Embedding | `amazon.titan-embed-text-v2:0`, version `v2`, stored `true` |
| PR B task | `1293facd-a701-490b-82df-0686d670638c` |
| Retrieval | `8033c0ed-9596-4aeb-ba95-e31d5825ac34` |
| Reasoning model | `apac.anthropic.claude-3-haiku-20240307-v1:0` |
| Hybrid pre-rerank score | `0.28500000000000003` |
| Bedrock selection | `1.00`, selected `true` |
| PR B GitHub comment | `5256843528` |

The successful live run occurred before commit `3f40f86`, and its textual `selection_reason` durably contains `Bedrock=1.00`. Commit `3f40f86` additionally persists that numeric value in `llm_rerank_score`; its regression test and branch CI are green. A post-fix live rerun was not substituted into this evidence because AWS subsequently returned `INVALID_PAYMENT_INSTRUMENT`. The original successful chain above remains independently inspectable in GitHub and CockroachDB.

## Verification

- Local: `python -m pytest -q` — 37 passed.
- Local: `python -m ruff check trace_memory tests scripts` — passed.
- GitHub Actions: [Verify Trace run 31519929892](https://github.com/vivekyarra/Trace/actions/runs/31519929892) — success on `3f40f86c811ef9fb3a92a1fe4d567243b3605d8c`.
- **CockroachDB Managed MCP (second CockroachDB tool):** Codex completed OAuth with **Read Data** only and independently read the live `TRACE-MEMORY-00401` memory and retrieval `8033c0ed-9596-4aeb-ba95-e31d5825ac34`. This is a live database tool call, not a screenshot or fixture.
- **Vector-index precision:** the live schema has a configured distributed vector index, but the three-row `EXPLAIN` in [`vector-explain.txt`](vector-explain.txt) selected a primary-key scan. This evidence therefore does not claim that the optimizer selected the vector index or accelerated retrieval at that corpus size.

The screenshots and their proof mapping are in [`screenshots/README.md`](../../screenshots/README.md).
