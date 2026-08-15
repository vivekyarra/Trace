# Operations and incident runbook

## Service topology

Run one webhook service and independently autoscaled outbox/task workers from the same immutable image. Expose only the webhook service through TLS. Keep the console private. Use separate readiness checks and process-level restarts.

## Signals

- `trace_webhooks_total{status=...}`: ingress outcome.
- SQS `ApproximateAgeOfOldestMessage`: worker delay.
- SQS DLQ visible count: poison task incident.
- CockroachDB pending outbox count: publisher delay.
- `agent_tasks` status and attempts: execution truth.
- `audit_events`, `agent_actions`, and `retrieval_events`: investigation trail.

Suggested objectives: 99.9% accepted-webhook availability monthly, 95% of admitted tasks started within five minutes, zero silent terminal failures, and zero cross-tenant retrievals.

## Deploy

1. Run all release gates against the exact image source SHA.
2. Apply migrations with the DDL role and verify checksums.
3. Deploy `infra/aws.yaml`; record stack outputs in the secret/config store.
4. Deploy webhook, outbox worker, and task worker with the runtime role.
5. Verify health, metrics, one signed ping, one synthetic issue, and one synthetic pull request.
6. Confirm outbox and queues drain to zero before shifting all traffic.

## Rollback

Roll back the image, not the database. Migrations in this release are additive. Pause webhook traffic if an incompatible writer is discovered, allow admitted tasks to drain, deploy the prior image, and preserve all task/outbox/audit rows.

## DLQ incident

1. Acknowledge the alarm and record the affected task UUID.
2. Copy the DLQ envelope and linked database evidence into restricted incident storage.
3. Classify the failure as payload, GitHub, Bedrock, database, or code.
4. Patch and verify with a redacted fixture reproducer.
5. Replay through a new, explicitly recorded delivery key. Never mutate the original task to appear successful.
6. Confirm queue depth, outbox backlog, and error metrics return to normal.

## Secret rotation

Rotate GitHub App tokens through installation-token expiry. For webhook-secret rotation, briefly accept old and new secrets at the load balancer or perform a coordinated cutover, send a ping, then revoke the old value. Rotate database credentials using a second runtime user and connection-drain window.
