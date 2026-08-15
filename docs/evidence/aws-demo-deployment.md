# AWS judge demo deployment

Verified on **2026-08-15** in AWS Asia Pacific (Mumbai), `ap-south-1`.

## Public URL

**https://shnxi3k7h7natsglz6l3zxma6u0dpggz.lambda-url.ap-south-1.on.aws/**

The public Lambda Function URL exposes a read-only product console. Clicking **Run Trace** executes the tracked production pipeline:

```text
Titan embedding → CockroachDB retrieval → Guardkeeper/Bedrock classification → consequence receipt
```

The app contains no replay snapshot and never fabricates a result when a dependency fails. `/api/status` reports `primary_mode: live-read-only`, `replay_mode: false`, and `write_routes: 0`.

## Deployment identity

| Field | Value |
|---|---|
| Function | `trace-judge-console` |
| Runtime / region | Python 3.12 / `ap-south-1` |
| Source | [`infra/judge_console_lambda.py`](../../infra/judge_console_lambda.py) |
| Production pipeline | `trace_memory.agents.Guardkeeper` |
| Code SHA-256 | `XBhcMs1T+Tb7m2/aHh+gvA83H6GSpN2adkFlL9GqxvI=` |
| Reasoning primary / fallback | `apac.amazon.nova-pro-v1:0` / `mistral.mistral-large-2402-v1:0` |
| Access | Public, read-only, no write route |
| Rate / concurrency | 12 requests per warm instance per minute / 2 reserved |
| Cache policy | `no-store` |

The deployment uses the CockroachDB SQLAlchemy dialect, TLS `verify-full`, and the bundled Cockroach Cloud root certificate at `/var/task/certs/cockroach-root.crt`. The read-only database identity inherits `trace_mcp_reader`; it has no insert, update, or delete privileges.

## Final live check

At `2026-08-15T15:29:23Z` through `15:29:25Z`, all three presets returned HTTP 200 and `memory_changed_review=true`:

- authorization revocation → `TRACE-MEMORY-00401`, `CONFLICT · HIGH`, 2203 ms;
- durable command architecture → `TRACE-MEMORY-00402`, `CONFLICT · MEDIUM`, 1230 ms;
- incident secret logging → `TRACE-MEMORY-00403`, `CONFLICT · HIGH`, 1355 ms.

Every response identified pipeline `trace_memory.agents.Guardkeeper`; the Lambda contains no duplicate classification implementation.
