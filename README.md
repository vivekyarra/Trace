# Trace

Most AI coding tools help teams write code faster. **Trace prevents teams from writing the wrong code again.**

Trace is institutional memory for software teams. It follows a change from issue to production, retrieves the decisions that govern the affected code, uses a schema-constrained Amazon Bedrock model to reason about conflicts and promises, and stores the resulting memory, provenance, and lifecycle in CockroachDB.

## The problem

Teams do not break architecture because they are careless. They break it because:

- the people who understood the original decision leave;
- decisions are buried in pull-request threads nobody can find;
- a locally reasonable change reintroduces the exact pattern that failed before;
- reviewers repeat the same correction because the repository never learned it.

ADRs require somebody to write and maintain them. Trace learns from the work the team already does.

## The original idea: memory that is allowed to disagree

Most agent memory optimizes for continuity: remember the user, retrieve a similar conversation, and help with the next request. Trace uses memory for something harder. It gives the codebase a durable point of view.

A Trace memory is not a text chunk. It is governed state with provenance, confidence, repository scope, security relevance, dependencies, and an ACTIVE/SUPERSEDED lifecycle. When a future pull request is locally reasonable but institutionally wrong, Trace retrieves the governing decision, explains the conflict, cites the exact source, and acts in the review before the mistake reaches production.

That creates a closed loop traditional tools leave open:

```text
team learns why → Trace preserves the decision → a later change conflicts
       ↑                                             ↓
source and lifecycle ← Trace cites, challenges, and records the outcome
```

The key insight is that agentic memory should not merely make an agent sound consistent. It should make an engineering organization behave consistently across time. [Read the originality case](docs/ORIGINALITY.md).

Guardkeeper makes that causal claim inspectable with a **memory consequence receipt** on every review: it lists the governing memories, separates memory-derived conflicts from independent deterministic findings, and states exactly which findings would disappear if memory were removed.

## How Trace works

Trace follows the complete engineering lifecycle and gets more useful after every merge:

1. **Issue created — Specforge pre-mortem.** Finds relevant failures, predicts risks, asks hard questions, and records implementation promises.
2. **Pull request opened — Guardkeeper.** Retrieves governed memory, detects semantic conflicts, verifies promises, inspects architectural drift, and runs deterministic security checks.
3. **Pull request merged — Tracekeeper.** Extracts decisions from discussion and code with provenance, dependencies, pattern rules, and carbon implications.
4. **Decision challenged — Reply Handler.** Supersedes or preserves memory without erasing history.
5. **Health and onboarding — Tracecast.** Builds decision health, security inventory, sustainability totals, knowledge graphs, and prioritized briefings.
6. **Any time — Trace Ask.** Answers questions with specific decisions, dates, people, sources, and dependency paths.

## Live functional demo — run the agent

**[Open the public AWS app and click Run Trace](https://shnxi3k7h7natsglz6l3zxma6u0dpggz.lambda-url.ap-south-1.on.aws/)**

Select the real PR #5 preset or paste a pull-request diff. Each click executes a fresh, read-only path:

```text
PR diff → Titan 1024-D embedding → CockroachDB governed retrieval
        → Bedrock conflict classification → memory consequence receipt
```

The receipt shows cloud-stage timings, retrieved candidates, selected memory IDs, the verdict, and the finding that would disappear without memory. If a cloud dependency is unavailable, the app returns `NOT_RUN`; it contains no replay result.

### Required platform integrations

| Platform tool/service | What Trace actually does with it |
|---|---|
| **CockroachDB Distributed Vector Indexing** | Stores tenant-scoped 1024-dimensional Titan embeddings beside transactional memory, provenance, tasks, and audit state. The distributed vector index is configured; the small-corpus proof does not claim optimizer index selection. |
| **CockroachDB Cloud Managed MCP Server** | Powers the read-only `Trace Auditor` agent, which joins the live `TRACE-MEMORY-00401` and retrieval `c12d9de4-0f8f-4c79-9b8b-1390b62c9590` records to provenance, task, action, and consequence evidence without a custom proxy. |
| **Amazon Bedrock** | Titan Text Embeddings V2 creates memory/query vectors. Nova Pro is the schema-constrained reasoning primary and Mistral Large is the strong secondary; every receipt records the model that actually ran. |
| **AWS Lambda** | Hosts the unrestricted public `Run Trace` app from tracked source in `infra/judge_console_lambda.py`; its primary route performs the live read path and exposes no write route. |
| **Amazon SQS, KMS, and CloudWatch** | FIFO delivery, encrypted DLQ retention, bounded retries, and operational alarms make the agent path durable and observable. |

It is built for one uncomfortable truth: teams rarely repeat failures because nobody cared. They repeat them because the reason behind yesterday's decision disappeared into a review thread.

## What is production-ready here

- CockroachDB is the canonical store. The schema includes tenant-scoped 1024-dimensional vector search, memory lifecycle and relationships, provenance, retrieval traces, audit events, agent tasks, and a transactional outbox.
- GitHub webhook ingress verifies `X-Hub-Signature-256`, rejects oversized or cross-repository payloads, ignores bot loops, and admits each delivery exactly once.
- The outbox publisher and SQS worker use durable task state, bounded retries, FIFO deduplication, and an encrypted dead-letter queue.
- Bedrock reasoning and Titan embeddings run through Amazon Bedrock. Every model response is schema-validated before it can affect stored state.
- Guardkeeper always runs deterministic security checks even if model reasoning is unavailable.
- The database-backed `trace-runtime console` exposes operator evidence without a write route. The public AWS app executes fresh read-only embedding, retrieval, and classification and returns no result when a dependency fails.
- Legacy wiki memories can be imported idempotently, and SQL migrations are checksum-tracked.
- Logs are structured and recursively redact secret-bearing fields; operational counters use Prometheus text format.

### Hackathon build versus pre-existing assets

| Area | Status |
|---|---|
| `legacy/` | Pre-existing prototype retained for historical comparison; not used by the production runtime. |
| `.gitlab/`, `flows/`, and top-level `agents/` | Pre-existing GitLab Duo/catalog definitions retained as compatibility and design references; not the deployed GitHub path. |
| `trace-cli/` | Pre-existing local wiki-memory CLI retained for compatibility; not the cloud execution engine. |
| `trace_memory/`, `migrations/`, `infra/`, `.github/workflows/`, `.github/agents/trace-auditor.agent.md` | Built for this hackathon: canonical CockroachDB runtime, Bedrock reasoning, GitHub automation, AWS durability, CI, and the Managed MCP auditor. |

## Runtime flow

```text
GitHub webhook
  → signature + tenant verification
  → CockroachDB agent_tasks + outbox_events (one transaction)
  → outbox worker
  → encrypted SQS FIFO queue
  → task worker
  → GitHub context + CockroachDB hybrid retrieval
  → Bedrock reasoning/Titan
  → review comment or governed memory
  → audit/task/retrieval evidence
```

If any process crashes, the database remains the recovery source. A delivery cannot create two tasks, an outbox event cannot create two effective executions, and poison tasks are retained in the DLQ for operator review.

## Repository map

| Path | Purpose |
|---|---|
| `trace_memory/domain` | Strict canonical models and lifecycle invariants |
| `trace_memory/persistence` | CockroachDB transactions and repositories |
| `trace_memory/retrieval` | Explainable hybrid ranking |
| `trace_memory/ai` | Bedrock embedding and structured reasoning adapters |
| `trace_memory/agents` | Guardkeeper and governed supersession |
| `trace_memory/runtime` | GitHub admission, automation, outbox, and SQS workers |
| `trace_memory/server.py` | Webhook, health, and metrics HTTP ingress |
| `trace_memory/console.py` | Read-only judge console |
| `migrations` | Ordered, checksum-tracked CockroachDB DDL |
| `infra/aws.yaml` | SQS FIFO/DLQ, least-privilege IAM, and CloudWatch alarms |
| `docs` | Architecture, operations, security, demo, Devpost, and release evidence |

## Local verification

Python 3.12 is required.

```bash
python -m pip install -e ".[test]"
python -m pip install -e ./trace-cli
python -m pytest tests trace-cli/tests
python -m ruff check trace_memory
python -m compileall -q trace_memory
```

The GitHub Actions workflow repeats those gates, validates both migrations, and audits installed Python dependencies.

## Configuration

Copy `.env.template` into your secret manager, not into Git. Required settings are:

- `DATABASE_URL`: the `trace_app` CockroachDB connection using the `cockroachdb://` SQLAlchemy dialect and
  `sslmode=verify-full` remotely.
- `TRACE_ORGANIZATION_ID` and `TRACE_REPOSITORY_ID`: canonical tenant IDs.
- `GITHUB_REPOSITORY`, `GITHUB_TOKEN`, and a 32+ character `GITHUB_WEBHOOK_SECRET`.
- `TRACE_SQS_QUEUE_URL` and `TRACE_SQS_DLQ_URL`.
- `AWS_REGION` and optional Bedrock model overrides.

Use a GitHub App installation token in production. Grant only metadata/content read, issues read/write, and pull-request read permissions. Do not use a personal access token as a long-lived runtime credential.

## Database and import

Apply all migrations with a DDL identity, never the `trace_app` runtime role:

```bash
trace-runtime migrate
```

Import a legacy Trace wiki export after setting the canonical organisation and repository IDs:

```bash
trace-runtime import ./memory-export.md
trace-runtime import ./memory-export.md --best-effort
```

Strict import validates the whole file before the first memory write. Best-effort mode reports malformed and duplicate records as skipped. Content hashes make a repeated import safe, and `import_runs` preserves the source checksum and outcome.

## Run the services

Each process is independently scalable:

```bash
trace-runtime webhook --host 0.0.0.0 --port 8000
trace-runtime outbox-worker
trace-runtime task-worker
trace-runtime console --host 127.0.0.1 --port 8080
```

Webhook endpoints:

- `POST /webhooks/github`
- `GET /healthz`
- `GET /metrics`

The console exposes `GET /` and `GET /api/status`; both are read-only and send no-store and browser-hardening headers. Put authentication and TLS at the load balancer before exposing it beyond a trusted judge/operator network.

## AWS deployment

`infra/aws.yaml` provisions:

- a KMS-encrypted FIFO task queue;
- a KMS-encrypted FIFO DLQ with 14-day retention;
- a least-privilege runtime IAM policy for those queues and the two configured Bedrock models;
- DLQ-depth and oldest-message CloudWatch alarms.

Deploy it with an existing ECS/App Runner task role, an SNS alarm topic, and exact model ARNs. Build the `Dockerfile` once and run the same image with the `webhook`, `outbox-worker`, and `task-worker` commands.

## Failure semantics

| Failure | Behaviour |
|---|---|
| Repeated GitHub delivery | Returns `200 duplicate`; no second task/outbox record |
| Invalid signature or wrong repository | Fails closed before persistence |
| CockroachDB serialization conflict | Retries only SQLSTATE `40001`, up to the configured bound |
| SQS transient handler failure | Schedules bounded retry and changes visibility |
| Third handler failure | Records `DEAD_LETTERED`, copies forensic envelope to DLQ, deletes source |
| Bedrock malformed output | Rejects it before a comment or memory write |
| Outbox crash after send | FIFO deduplication plus task idempotency prevents effective re-execution |

## Demo and release evidence

- [Public AWS judge proof console](https://shnxi3k7h7natsglz6l3zxma6u0dpggz.lambda-url.ap-south-1.on.aws/)
- [Immutable live core proof](docs/evidence/core-live-proof.md)
- [Demo runbook](docs/DEMO_RUNBOOK.md)
- [Devpost submission](docs/DEVPOST_SUBMISSION.md)
- [Operations and incident runbook](docs/OPERATIONS.md)
- [Security model](SECURITY.md)
- [Why Trace is an original agentic-memory design](docs/ORIGINALITY.md)
- [Release verification](docs/RELEASE_CHECKLIST.md)

Every demo step distinguishes live evidence from fixture data. No database, AWS, Bedrock, or GitHub result is claimed live until the corresponding preflight is green.

— Trace
