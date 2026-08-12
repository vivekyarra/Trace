# Trace judge demo runbook

Target length: **2 minutes 40 seconds**. Hard stop at **2:45**; never submit a cut at or above 3:00. Use the isolated PR #4/#5 demo history. Do not show secrets, connection strings, tokens, AWS account IDs, or raw customer code.

## Preflight — must be green

```text
[ ] Main CI succeeded for the exact release SHA
[ ] Public AWS judge-console URL opens in a signed-out browser
[ ] PR #4 and PR #5 are visible without authentication
[ ] CockroachDB Managed MCP is authorized with Read Data only
[ ] Managed MCP retrieves TRACE-MEMORY-00401 and retrieval 8033c0ed-9596-4aeb-ba95-e31d5825ac34
[ ] No secret, connection string, token, AWS account ID, or private console URL is visible
```

If any live check fails, label that segment `REPLAY` and use the previously captured real result. Never describe fixture values as live.

## Script and clicks

### 0:00–0:12 — The problem

Open [PR #4](https://github.com/vivekyarra/Trace/pull/4), already merged into the isolated demo base.

Say: “PR #4 records a non-negotiable authorization rule: permission changes must revoke cached access immediately.”

### 0:12–0:32 — The memory, live through Managed MCP

Use CockroachDB Managed MCP with read-only OAuth to retrieve the exact `TRACE-MEMORY-00401` row. Show its PR #4 source, ACTIVE state, Titan embedding provenance, and repository scope.

Say: “This is a live read-only Managed MCP database call, not a fixture. CockroachDB stores the governed memory and its 1024-dimensional Titan embedding.”

### 0:32–0:58 — PR #5 and Trace rejection

Open [PR #5](https://github.com/vivekyarra/Trace/pull/5). Do **not** merge it. Jump directly to Trace’s Guardkeeper comment and highlight:

1. `TRACE-MEMORY-00401`;
2. the PR #4 source citation;
3. retrieval `8033c0ed-9596-4aeb-ba95-e31d5825ac34`;
4. the rejection of the ten-minute stale authorization cache.

Say: “PR #5 looks plausible alone. Trace retrieves the governing decision, recognizes the semantic conflict, and rejects the stale authorization window before merge.”

### 0:58–1:28 — Public AWS judge console

Open the [public AWS judge proof console](https://shnxi3k7h7natsglz6l3zxma6u0dpggz.lambda-url.ap-south-1.on.aws/). Point to PR #4, `TRACE-MEMORY-00401`, PR #5, and the two CockroachDB tools. Expand the immutable identifiers and model provenance.

Say: “This unrestricted read-only proof viewer is deployed on AWS Lambda. It exposes the immutable identifiers from the verified live run and no write route; the fresh database read you just saw came directly through Managed MCP.”

### 1:28–2:08 — How the live path works

Show the current architecture diagram or README runtime flow: signed GitHub webhook → CockroachDB task/outbox transaction → encrypted SQS FIFO → Bedrock Claude/Titan → governed memory/review. Point out that CockroachDB provides Distributed Vector Indexing and read-only Managed MCP.

Say: “CockroachDB gives Trace serializable state, configured distributed vector indexing, and the Managed MCP surface you just saw. SQS makes processing durable; Bedrock supplies Titan embeddings and Claude reasoning.”

### 2:08–2:32 — Provenance and lifecycle

Return to the memory/retrieval record. Show source URL, selected state, model provenance, and the immutable IDs. State precisely that the current three-row `EXPLAIN` did not select the vector index; do not claim accelerated retrieval.

Say: “Every conclusion remains attributable. Decisions can be superseded without erasing why they existed.”

### 2:32–2:40 — Close

Return to PR #5.

Say: “Coding agents help teams move faster. Trace stops them from repeating what the team already learned the hard way.”

## Failure fallback

- Managed MCP delayed: use the already captured live MCP result and label it `REPLAY`.
- Console unavailable: use `/api/status`; if both fail, do not record or submit until the AWS URL is restored.
- Bedrock billing unavailable: show the immutable successful live record and label it `REPLAY`; never imply a fresh inference.
- Editing rule: remove pauses before removing proof. Final exported duration must be 2:35–2:45.
