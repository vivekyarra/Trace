# Trace judge demo runbook

Target length: **2 minutes 40 seconds**. Hard stop at **2:45**. Use the isolated PR #4/#5 history. Never show secrets, connection strings, tokens, AWS account IDs, or raw customer code.

## Preflight — every item must be green

```text
[ ] Branch CI succeeded for the exact SHA being demonstrated
[ ] Public AWS Run Trace URL opens signed out
[ ] PR #4 and PR #5 are public
[ ] Preset PR #5 completes with a LIVE receipt
[ ] Receipt shows Titan → CockroachDB → Bedrock classifier with fresh timings and the actual model ID
[ ] TRACE-MEMORY-00401 is selected and the verdict is CONFLICT
[ ] Replay snapshot remains labelled REPLAY and is not presented as fresh
[ ] No secret, connection string, token, or AWS account ID is visible
```

If a live check fails, show the captured proof only with a visible `REPLAY` label. Never call a fixture or snapshot live.

## Script and clicks

### 0:00–0:15 — The problem

Open [PR #4](https://github.com/vivekyarra/Trace/pull/4).

Say: “Most AI tools help you write code faster. Trace prevents you from writing the wrong code again. PR #4 records one hard-won rule: permission changes must revoke cached access immediately.”

### 0:15–0:30 — The locally plausible mistake

Open [PR #5](https://github.com/vivekyarra/Trace/pull/5) and show the ten-minute permission cache.

Say: “This is reasonable if you only read today’s diff. It is dangerous if your codebase remembers why this pattern was rejected.”

### 0:30–1:15 — Run the functional agent

Open the [public AWS app](https://shnxi3k7h7natsglz6l3zxma6u0dpggz.lambda-url.ap-south-1.on.aws/). Keep the PR #5 preset selected and click **Run Trace live**.

While it runs, point to the four stages:

1. fresh 1024-dimensional Titan embedding on Amazon Bedrock;
2. tenant-scoped CockroachDB vector retrieval;
3. schema-checked Bedrock conflict classification (Claude preferred; Nova truth-labelled fallback);
4. memory consequence receipt.

Say: “This button is traversing the live read path now. The page is not holding the answer. Titan embeds this diff, CockroachDB returns the active governed candidates, and the Bedrock classifier may select only IDs that came from that candidate set. The receipt names whether Claude or the Nova fallback actually ran.”

### 1:15–1:42 — Show the consequence, not just the answer

Read the `CONFLICT` verdict, selected `TRACE-MEMORY-00401`, source URL, timing rows, and receipt counterfactual.

Say: “The receipt proves causality. Without this CockroachDB memory, the governing conflict finding disappears. Memory did not decorate the prompt—it changed the review.”

### 1:42–2:05 — Explain the production loop

Show the README runtime diagram.

Say: “In production, a signed GitHub webhook commits task and outbox state atomically in CockroachDB, SQS provides durable execution, Titan and Claude reason through Bedrock, and every retrieval and action remains attributable. Crashes and duplicate deliveries do not create duplicate effective work.”

### 2:05–2:25 — Why CockroachDB

Show the candidate details or the previously verified Read Data-only Managed MCP row.

Say: “CockroachDB is not just a vector sidecar. It keeps vectors, provenance, lifecycle, dependencies, tasks, and audit truth together under serializable transactions. Managed MCP gives judges a second, direct read-only inspection path.”

Do not claim that the tiny proof query used the vector index. Say that distributed vector indexing is configured and the small-corpus `EXPLAIN` chose a scan.

### 2:25–2:40 — Close

Return to the verdict.

Say: “Most submissions ask AI to write more code. Trace asks whether the code should exist at all. Your codebase does not just remember—it has a point of view.”

## Failure fallback

- If live Bedrock or CockroachDB fails, expand the fallback and show `REPLAY`; never imply a fresh run.
- If the app fails before recording, do not submit until `/healthz` and a preset live run pass again.
- Remove pauses before removing proof. Final export should land between 2:35 and 2:45.
