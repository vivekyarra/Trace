# Trace — Your codebase remembers why

## Inspiration

Most AI coding tools help teams write code faster. Trace prevents teams from writing the wrong code again.

Teams rarely repeat failures because nobody cared. They repeat them because the reason behind yesterday's decision disappeared into a pull-request thread:

- the engineer who understood the original trade-off left;
- the outage report is disconnected from the code it governs;
- six months later, a locally sensible change reintroduces the rejected pattern;
- reviewers repeat the same correction because the repository never learned it.

ADRs work only when somebody writes and maintains them. Trace turns the work a team already does into living, enforceable institutional memory.

## What it does

Trace follows a change from issue to production and gets more useful after every merge.

1. **Before code — Specforge.** It retrieves relevant incidents and decisions, predicts likely failures, asks hard questions, and turns the answers into promises the eventual pull request must keep.
2. **During review — Guardkeeper.** It embeds the diff, retrieves governed memory from CockroachDB, asks a schema-constrained Amazon Bedrock model to identify semantic conflicts, verifies promises, and always runs deterministic security checks.
3. **After merge — Tracekeeper.** It extracts decisions from both discussion and code, stores provenance and Titan embeddings, tracks relationships and carbon implications, and captures recurring review rules.
4. **When a decision changes — Reply Handler.** It supersedes the old memory without erasing it, transfers dependency links, and records the new reasoning.
5. **Across the team — Tracecast and Onboarding.** It produces decision health, security inventory, sustainability totals, knowledge graphs, and prioritized briefings.
6. **At any time — Trace Ask.** It answers natural-language questions with specific decisions, dates, sources, and dependency paths.

The public demo executes the core loop on demand: select or paste a PR diff, create a fresh Titan embedding, retrieve tenant-scoped memories from CockroachDB, classify the conflict with Bedrock, and return a memory consequence receipt. It contains no replay result.

## The proof in one change

PR #4 established a security invariant: permission changes must invalidate cached authorization immediately. Trace preserved it as `TRACE-MEMORY-00401`, with its source, scope, status, rationale, and 1024-dimensional Titan embedding.

PR #5 later introduced a ten-minute permission-decision cache. The diff looks reasonable in isolation. Trace retrieves the PR #4 memory, recognizes that the new implementation recreates the forbidden stale-authorization window, and classifies the change as a conflict before merge.

The result includes a **memory consequence receipt**: the governing memory IDs, the number of retrieved candidates, and the exact counterfactual—what finding would disappear if institutional memory were removed. “Memory changed the agent” is therefore an inspectable product property, not demo narration.

## Why this is agentic memory

Trace is not a chatbot with longer context, an ADR search box, or a vector database bolted onto code review.

Most memory systems optimize for continuity: retrieve something similar and help with the next request. Trace gives memory authority. A memory has provenance, confidence, repository scope, security relevance, dependency links, and an `ACTIVE` or `SUPERSEDED` lifecycle. It can disagree with a developer, change the review outcome, cite the decision that governs the code, and evolve without rewriting history.

Three design choices make that possible:

1. **Authority beyond similarity.** Ranking combines vector distance with file scope, confidence, security relevance, feedback, and lifecycle state.
2. **Correct forgetting.** Supersession is an auditable state transition, not an overwrite.
3. **A closed loop.** Trace observes work, remembers why, acts on a later change, and records the consequence as future evidence.

## How we built it

- **CockroachDB Cloud** stores tenant-scoped memories, `VECTOR(1024)` embeddings, provenance, relationships, retrieval traces, tasks, audit events, and a transactional outbox in one serializable source of truth.
- **CockroachDB Distributed Vector Indexing** is configured with organization and repository prefix columns. We do not claim optimizer index selection for the tiny proof corpus; its recorded `EXPLAIN` chose a scan.
- **CockroachDB Cloud Managed MCP** was authorized with Read Data only and independently retrieved the exact live memory and retrieval rows.
- **Amazon Titan Text Embeddings V2 on Bedrock** creates stored memory vectors and fresh query vectors.
- **Amazon Bedrock** runs schema-constrained reasoning with Nova Pro as the reliable primary and Mistral Large as the strong secondary. The receipt records the model that actually ran.
- **AWS Lambda** hosts the public read-only `Run Trace` app. Its primary route traverses Bedrock → CockroachDB → Bedrock; it exposes no write route.
- **Amazon SQS FIFO, KMS, and CloudWatch** make the production webhook path durable, encrypted, bounded, and observable.
- **Python, Pydantic, SQLAlchemy, and pg8000** enforce typed boundaries from model output to transactional state and the lightweight Lambda read path.

## Challenges we ran into

The hard problem was not generating prose. It was making AI behaviour durable and accountable.

A webhook may be delivered twice. A CockroachDB transaction may restart. A worker may crash after publishing. A model may return confident but malformed output. Trace treats each as a normal production condition with deterministic keys, transactional outbox state, serialization retries, FIFO deduplication, strict output schemas, bounded attempts, and provenance.

Hybrid retrieval was equally important. Pure similarity can bury a high-impact security decision beneath nearby text. Trace separates candidate retrieval from constrained model selection and records both the rank components and final reasoning.

The demo itself exposed another useful standard: a static proof page is evidence, not a functional app. The judge action therefore executes a fresh, read-only memory loop with timings and model/database provenance and fabricates nothing on failure.

## Accomplishments that we're proud of

- A governed memory lifecycle that supersedes decisions without destroying history.
- A real GitHub → CockroachDB/SQS → Bedrock → GitHub production path.
- A public judge action that performs fresh Titan embedding, CockroachDB retrieval, Bedrock classification, and consequence reporting with no replay path.
- Fail-closed webhook and model boundaries plus an always-on deterministic security sentinel.
- Retrieval evidence that makes memory influence causally inspectable.
- Read-only Managed MCP verification against the same canonical CockroachDB source.
- A release suite covering runtime, migration, security, retrieval, queue, and UI behavior.

## What we learned

Institutional memory needs opinions; infrastructure needs boring guarantees. Model reasoning is useful when surrounded by deterministic admission, security, lifecycle, and audit rules. CockroachDB makes the central idea practical because semantic recall and operational truth live in the same transactional system.

Most importantly, memory becomes valuable when it can change an action. Retrieval alone is not the product. The consequence is.

## What's next

Next we will add GitHub App installation-token minting, multi-region workers, operator-approved dead-letter replay, retrieval-quality evaluation sets, and organization-level policy controls. These are roadmap items, not claims about this release.

## Built with

CockroachDB Cloud, CockroachDB Distributed Vector Indexing, CockroachDB Cloud Managed MCP, Amazon Bedrock, Amazon Nova Pro, Mistral Large, Amazon Titan Text Embeddings V2, AWS Lambda, Amazon SQS, AWS KMS, Amazon CloudWatch, GitHub, Python, Pydantic, SQLAlchemy, and pg8000.

## Closing

Most submissions ask AI to write more code. Trace asks whether the code should exist at all.

It does not just remember decisions. It turns yesterday's hard-won reason into an active constraint on tomorrow's agent.

— Trace
