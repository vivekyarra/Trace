# Security model

## Supported release

The durable `lore/` runtime on the latest tagged release receives security fixes. Files under `legacy/` are reference-only and must not be deployed.

Report vulnerabilities privately through the repository's GitHub Security Advisory flow. Do not open a public issue containing credentials, exploit details, tenant data, or webhook payloads.

## Non-negotiable properties

- A GitHub event is trusted only after HMAC-SHA256 verification with constant-time comparison.
- Repository identity from the signed payload must match the configured tenant repository.
- Remote CockroachDB connections require certificate and hostname verification.
- Runtime credentials come from a secret manager and never from source, image layers, logs, comments, or model prompts.
- The runtime database role has DML access only. Migrations use a separate short-lived DDL identity.
- GitHub uses a short-lived App installation token with minimum repository permissions.
- SQS and its DLQ are encrypted. Bedrock and SQS IAM resources are explicitly scoped.
- User-controlled payload size, model output, comments, and persisted errors are bounded.
- Model output is untrusted until strict schema validation succeeds.
- The judge console is read-only and must sit behind TLS and operator authentication when remotely accessible.

## Threats and controls

| Threat | Control |
|---|---|
| Forged/replayed webhook | HMAC verification plus repository-scoped delivery idempotency |
| Cross-tenant retrieval | Organisation and repository predicates precede vector ordering |
| Prompt injection | Minimal webhook envelope, bounded source context, deterministic security sentinel, validated output |
| Secret leakage | Recursive structured-log redaction and deliberately generic remote API errors |
| Retry storm | Bounded exponential delay, visibility changes, max attempts, DLQ |
| Poison message loss | Forensic envelope copied to encrypted DLQ before source deletion |
| Model supply drift | Explicit model IDs and persisted embedding/prompt version metadata |
| Dependency compromise | Locked resolution, CI dependency audit, minimal runtime dependencies |

## Production verification

Before release, complete every gate in `docs/RELEASE_CHECKLIST.md`. Rotate the webhook secret and GitHub installation token after any suspected disclosure. A DLQ alarm is an incident: quarantine the payload, preserve task/audit rows, establish whether the failure is deterministic, then replay with a new delivery key only after remediation.
