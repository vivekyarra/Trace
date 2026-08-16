# Production demo memory examples

These are the two secondary conflict cases in the live Trace tenant. The auth-cache
decision from PR #4 remains the default and primary demonstration.

## Architecture decision

- **Memory:** `TRACE-MEMORY-00402`
- **Live UUID:** `9f6f3dc8-fad2-5762-99ef-a1989adc0a3f`
- **Provenance:** [`docs/evidence/demo-memory-examples.md#architecture-decision`](demo-memory-examples.md#architecture-decision), scope `services/commands`, Titan V2 1024-dimensional embedding
- **Decision:** Route cross-service commands through the durable queue and outbox;
  direct synchronous HTTP commands between services are rejected.
- **Reason:** A downstream timeout must not lose an accepted command or force the
  caller to guess whether it was applied.
- **Conflict example:** A pull request adds `requests.post()` from the API directly
  to the billing service.
- **Live result:** `CONFLICT · MEDIUM`, `memory_changed_review=true`, 1230 ms total.

## Incident and security lesson

- **Memory:** `TRACE-MEMORY-00403`
- **Live UUID:** `050fbaeb-770b-5c39-93f0-2f6fe8b35a98`
- **Provenance:** [`docs/evidence/demo-memory-examples.md#incident-and-security-lesson`](demo-memory-examples.md#incident-and-security-lesson), scope `security/request-logging`, Titan V2 1024-dimensional embedding
- **Decision:** Redact `Authorization`, cookies, and session tokens before request
  metadata reaches logs.
- **Reason:** A prior incident exposed reusable bearer tokens in centralized logs.
- **Conflict example:** A pull request logs the complete request headers on an
  authentication failure.
- **Live result:** `CONFLICT · HIGH`, `memory_changed_review=true`, 1355 ms total.
