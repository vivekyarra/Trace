# Trace

Trace is institutional memory for software teams. It observes GitHub issues and pull requests, retrieves the decisions that govern the affected code, uses Anthropic Claude on Amazon Bedrock to reason about conflicts and promises, and stores the resulting memory and provenance in CockroachDB.

It is built for one uncomfortable truth: teams rarely repeat failures because nobody cared. They repeat them because the reason behind yesterday's decision disappeared into a review thread.

## What is production-ready here

- CockroachDB is the canonical store. The schema includes tenant-scoped 1024-dimensional vector search, memory lifecycle and relationships, provenance, retrieval traces, audit events, agent tasks, and a transactional outbox.
- GitHub webhook ingress verifies `X-Hub-Signature-256`, rejects oversized or cross-repository payloads, ignores bot loops, and admits each delivery exactly once.
- The outbox publisher and SQS worker use durable task state, bounded retries, FIFO deduplication, and an encrypted dead-letter queue.
- Anthropic Claude reasoning and Titan embeddings run through Amazon Bedrock. Every model response is schema-validated before it can affect stored state.
- Guardkeeper always runs deterministic security checks even if model reasoning is unavailable.
- The read-only judge console exposes live counts, recent task state, health, and evidence without a write route.
- Legacy wiki memories can be imported idempotently, and SQL migrations are checksum-tracked.
- Logs are structured and recursively redact secret-bearing fields; operational counters use Prometheus text format.

The original GitLab Duo flow, standalone agents, and `trace-cli` remain in the repository as compatibility/reference assets. The durable cloud runtime in `trace_memory/` is GitHub-native.

## Runtime flow

```text
GitHub webhook
  → signature + tenant verification
  → CockroachDB agent_tasks + outbox_events (one transaction)
  → outbox worker
  → encrypted SQS FIFO queue
  → task worker
  → GitHub context + CockroachDB hybrid retrieval
  → Bedrock Claude/Titan
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

- [Demo runbook](docs/DEMO_RUNBOOK.md)
- [Devpost submission](docs/DEVPOST_SUBMISSION.md)
- [Operations and incident runbook](docs/OPERATIONS.md)
- [Security model](SECURITY.md)
- [Release verification](docs/RELEASE_CHECKLIST.md)

Every demo step distinguishes live evidence from fixture data. No database, AWS, Bedrock, or GitHub result is claimed live until the corresponding preflight is green.

— Trace
