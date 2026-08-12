# AWS judge demo deployment

Verified on 2026-08-12 in AWS Asia Pacific (Mumbai), `ap-south-1`.

## Public URL

**https://shnxi3k7h7natsglz6l3zxma6u0dpggz.lambda-url.ap-south-1.on.aws/**

The URL uses AWS Lambda Function URL authentication mode `NONE`. It rendered successfully without application authentication and returned HTTP 200 during release verification. `/api/status` returned:

- `status: verified-live-proof-snapshot`
- `write_routes: 0`
- memory `TRACE-MEMORY-00401`
- retrieval `8033c0ed-9596-4aeb-ba95-e31d5825ac34`

## Deployment identity

| Field | Value |
|---|---|
| AWS service | Lambda + Lambda Function URL |
| Function | `trace-judge-console` |
| Runtime | Python 3.12 |
| Region | `ap-south-1` |
| Source | [`infra/judge_console_lambda.py`](../../infra/judge_console_lambda.py) |
| Access | Public, read-only, no write route |
| Cache policy | `no-store` |

The app is deliberately labelled as an immutable verified-live-proof snapshot captured on 2026-08-11. It does not claim that a fresh Bedrock inference or live database query occurs when a judge opens the page. The separate Managed MCP evidence is a real Read Data-only database call and the public proof viewer links to its immutable identifiers.
