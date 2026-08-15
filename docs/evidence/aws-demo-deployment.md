# AWS judge demo deployment

Verified on **2026-08-15** in AWS Asia Pacific (Mumbai), `ap-south-1`.

## Public URL

**https://shnxi3k7h7natsglz6l3zxma6u0dpggz.lambda-url.ap-south-1.on.aws/**

The public Lambda Function URL exposes a read-only product console. Clicking **Run Trace** performs a fresh path:

```text
Titan embedding → CockroachDB retrieval → Bedrock classification → consequence receipt
```

The app contains no replay snapshot and never fabricates a result when a dependency fails. `/api/status` reports `primary_mode: live-read-only`, `replay_mode: false`, and `write_routes: 0`.

## Deployment identity

| Field | Value |
|---|---|
| AWS service | Lambda + Lambda Function URL |
| Function | `trace-judge-console` |
| Runtime | Python 3.12 |
| Region | `ap-south-1` |
| Source | [`infra/judge_console_lambda.py`](../../infra/judge_console_lambda.py) |
| Reasoning primary | `apac.amazon.nova-pro-v1:0` |
| Reasoning fallback | `mistral.mistral-large-2402-v1:0` |
| Access | Public, read-only, no write route |
| Rate limit | 12 requests per warm instance per minute |
| Reserved concurrency | 2 concurrent Lambda environments |
| Cache policy | `no-store` |

The production PR proof uses memory `TRACE-MEMORY-00401` and retrieval `c12d9de4-0f8f-4c79-9b8b-1390b62c9590`; the public Lambda runs the same read-only decision path on demand without creating database rows.

Final live check: `2026-08-15T13:02:57Z`. The preset completed in 2623 ms using `apac.amazon.nova-pro-v1:0`, returned `CONFLICT · HIGH`, and produced `memory_changed_review=true`. The deployed page used one 1280×529 viewport with no document scroll; the headline remained on one line and the Run action stayed visible.
