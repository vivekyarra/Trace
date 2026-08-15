# LORE judge demo runbook

Target length: 4 minutes. Use a dedicated demo repository and synthetic decision text. Do not show secrets, connection strings, tokens, AWS account IDs, or raw customer code.

## Preflight — must be green

```text
[ ] Feature-branch CI succeeded for the exact demo SHA
[ ] Main/release CI succeeded for the exact release SHA
[ ] GET /healthz returns {"status":"ok"}
[ ] Judge console shows pending_outbox = 0 and dead_lettered_tasks = 0
[ ] SQS main queue and DLQ both begin at depth 0
[ ] Bedrock model access succeeds in the deployment region
[ ] GitHub webhook recent delivery is HTTP 202 or an intentional duplicate HTTP 200
```

If any check fails, label the segment `REPLAY` and use a previously captured real run. Never describe fixture values as live.

## Script and clicks

### 0:00–0:30 — The problem

Open the repository pull request containing a deliberate retry-policy conflict.

Say: “This change looks reasonable in isolation. The team rejected it after an earlier retry storm, but that decision is buried in history. LORE makes that history active.”

### 0:30–1:10 — Canonical memory

Open the judge console. Point to active memories, security decisions, and zero pending/dead-letter counts. Open `/api/status` in a second tab to show the same live values as JSON.

Say: “This is not a generated dashboard fixture. These counts come read-only from CockroachDB, the canonical store.”

### 1:10–2:10 — Trigger Guardkeeper

Push or reopen the prepared pull request. In GitHub webhook deliveries, show the signed delivery succeeded. Then show SQS receive activity and refresh the console until the task is `SUCCEEDED`.

Open the LORE review comment. Highlight:

1. the historical decision and evidence;
2. the unfulfilled issue promise, if present;
3. the deterministic security section;
4. the `— LORE` signature.

Say: “Claude performs the semantic reasoning, but deterministic security checks and strict output validation remain in control.”

### 2:10–3:05 — Explain the durable path

Show the architecture section in the README.

Say: “GitHub is acknowledged only after one task and one outbox event commit together. A separate worker publishes to encrypted FIFO SQS. Retries are bounded. After the final attempt, the forensic envelope moves to the encrypted DLQ and an alarm fires.”

### 3:05–3:40 — Memory after merge

Merge the prepared safe alternative or show a labelled real replay. Refresh the console and query the decision through the read-only MCP surface. Show source PR, confidence basis, lifecycle state, and governing repository scope.

Say: “LORE did not just summarize the pull request. It created a governed memory with provenance. A future override supersedes it without deleting the historical reason.”

### 3:40–4:00 — Close

Return to the console.

Say: “Coding assistants help teams write faster. LORE helps them remember why the code must be written this way.”

## Failure fallback

- GitHub delivery delayed: show delivery ID and task row, then use `REPLAY` evidence.
- Bedrock throttled: show the bounded retry state; do not manually edit a successful result.
- Queue failure: show CloudWatch alarm/DLQ only if it is a prepared synthetic failure.
- Console unavailable: use `/api/status`; if both fail, stop claiming a live run.
