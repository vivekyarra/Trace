# Why Trace is an original agentic-memory design

## The thesis

Agent memory is usually designed to help an agent continue: recall a preference, retrieve a similar passage, or resume a task. Trace asks a different question:

> What if memory could prevent an organization from repeating a mistake even when the new change looks reasonable on its own?

Trace turns institutional memory into a temporal control system. A past decision can govern future code, challenge a pull request, cite its origin, and evolve without being erased.

## Not another RAG wrapper

| Conventional approach | What it leaves unresolved | Trace's agentic move |
|---|---|---|
| Chat history | Remembers conversation, not engineering authority | Stores governed decisions with scope, confidence, security relevance, and lifecycle |
| ADR or wiki search | Requires a human to know that the right document exists | Automatically retrieves governing memory from the actual issue/PR context |
| Vector-only RAG | Similarity can elevate stale or irrelevant text | Combines vector distance with file scope, confidence, security importance, feedback, and ACTIVE state |
| Static lint rule | Catches syntax the rule author anticipated | Uses Bedrock reasoning to recognize semantic equivalents while deterministic checks remain in control |
| PR summarizer | Describes the current change | Compares the change with historical promises and rejected alternatives, then acts in review |
| Mutable knowledge base | New text silently replaces old truth | Supersedes decisions with provenance, dependencies, and an audit-preserving lifecycle |

## The complete agent loop

Trace is agentic because memory changes behavior:

1. **Observe:** receive a signed GitHub issue or pull-request event.
2. **Remember:** retrieve tenant-scoped CockroachDB memories and their provenance.
3. **Judge:** use a schema-constrained Bedrock model to detect semantic conflicts and promise gaps.
4. **Act:** post an attributable Guardkeeper review or create a governed memory.
5. **Learn:** record retrieval, reasoning, feedback, dependencies, and the resulting lifecycle transition.

The next run begins from the durable outcome of the previous one. That is a feedback loop, not a stateless model call.

## Causal proof: the memory consequence receipt

It is easy for an agent to retrieve a memory and then ignore it. Trace therefore makes memory influence explicit in every Guardkeeper result:

```text
Memory changed this review: yes
Governing memories: TRACE-MEMORY-00401
Counterfactual: without the selected institutional memory, the memory-conflict
finding would be absent; independent deterministic findings would remain.
```

The receipt does not speculate that every final outcome would reverse. It makes the narrower causal fact auditable: which review findings exist because memory was selected. The behavior is generated deterministically from the validated review and covered by regression tests.

## The proof is a conflict, not a happy-path chat

The live demonstration deliberately uses two pull requests:

```text
PR #4 establishes an immediate authorization-revocation invariant
  → Trace creates TRACE-MEMORY-00401 with source and embedding provenance
  → PR #5 introduces a plausible ten-minute permission cache
  → Trace retrieves the memory and rejects the semantic conflict before merge
```

PR #5 is important because it shows the memory has consequence. If the memory were removed, the agent's action would change.

## Why CockroachDB is part of the invention

The design depends on keeping semantic and operational truth together:

- 1024-dimensional Titan embeddings and configured Distributed Vector Indexing support semantic recall.
- Serializable transactions bind webhook admission, task state, outbox delivery, memory lifecycle, and provenance.
- Managed MCP gives judges and operators a direct, read-only path to the same canonical rows without a custom proxy.

A separate vector store would introduce a consistency gap between “what looks similar” and “what is currently authoritative.” Trace makes that gap a database invariant instead of an application hope.

## The memorable one-line pitch

**Trace gives the codebase a memory with standing: it can cite the past, disagree with the present, constrain the future, and prove how memory changed its review.**
