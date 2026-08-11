# Devpost submission — Trace

## Tagline

Your codebase remembers why.

## Inspiration

The most expensive engineering mistakes are often repeats. A retry strategy was rejected after an outage, an authentication shortcut was prohibited in review, or a library was chosen to avoid a subtle failure—and six months later the reason is gone. ADRs help only when somebody writes them. Review comments help only when somebody can find them.

Trace turns the work a team already does into living, enforceable institutional memory.

## What it does

Trace follows a change from issue to production. On an issue it creates a failure pre-mortem. On a pull request it retrieves relevant historical decisions, checks implementation promises, inspects architectural drift, and always runs a deterministic security sentinel. After merge it extracts durable decisions into CockroachDB, including provenance and lifecycle state. When a decision changes, Trace supersedes it without erasing history.

The judge console makes the system inspectable: active and security-relevant memories, task outcomes, retrieval traces, pending outbox work, and dead-lettered failures are visible from the canonical database.

## How we built it

- CockroachDB stores tenant-scoped decision memory, vector embeddings, relationships, provenance, audit events, tasks, and the transactional outbox.
- Amazon Titan Text Embeddings V2 produces 1024-dimensional vectors.
- Anthropic Claude on Amazon Bedrock performs structured pre-mortem, review, and decision extraction reasoning.
- GitHub webhooks enter through an HMAC-verified, idempotent admission boundary.
- Amazon SQS FIFO separates delivery from reasoning; a KMS-encrypted DLQ and CloudWatch alarms make failure operationally visible.
- Python/Pydantic reject unknown fields and malformed model output at every boundary.

## The hard parts

The difficult problem was not generating prose. It was making AI behaviour durable and accountable. A webhook can be repeated. A database transaction can restart. A worker can crash after publishing. A model can return plausible but malformed output. Trace treats each of those as a normal production condition: deterministic keys, transactional outbox state, CockroachDB serialization retries, FIFO deduplication, strict schemas, bounded attempts, and provenance records.

Hybrid retrieval was another important choice. Vector similarity alone can bury a security decision. Trace combines semantic distance with code scope, confidence, security relevance, and human feedback, then records why each candidate was selected.

## Accomplishments

- A canonical vector-backed memory model with governed supersession instead of destructive updates.
- Real GitHub-to-SQS-to-Bedrock-to-CockroachDB runtime paths.
- Fail-closed webhook and model boundaries.
- Read-only MCP and judge/operator views over the same canonical source.
- Compatibility import for existing Trace wiki memory.
- Release gates covering the new runtime and the original 43-test CLI compatibility suite.

## What we learned

Institutional memory needs opinions, but infrastructure needs boring guarantees. Claude is strongest when semantic judgment is surrounded by deterministic admission, security, lifecycle, and audit rules. CockroachDB's serializable transactions and vector indexing let those guarantees and the semantic memory live in one inspectable system.

## What's next

The next production iteration will add GitHub App installation-token minting, multi-region worker deployment, operator-approved DLQ replay, retrieval-quality evaluation sets, and organization-level policy controls. These are roadmap items, not claims about this release.

## Built with

CockroachDB, Amazon Bedrock, Anthropic Claude, Amazon Titan Embeddings, Amazon SQS, AWS CloudWatch, GitHub, Python, Pydantic, and SQLAlchemy.
