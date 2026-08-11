# Phase 1 audit — legacy LORE baseline

Run: 2026-08-11 (Asia/Kolkata)  
Branch: `feature/phase-1-audit`

## What exists

| Area | Current implementation | Evidence |
|---|---|---|
| Workflow definition | GitLab Duo flow with seven components: `triage_router`, `specforge_agent`, `guardkeeper_agent`, `reply_handler_agent`, `lorekeeper_agent`, `lorecast_agent`, and `onboarding_agent`. | `.gitlab/duo/flows/lore.yaml` |
| Catalog flow | A condensed GitLab AI Catalog flow with duplicated prompt material and a router. | `flows/flow.yml` |
| Runtime | Legacy FastAPI application with `/health`, `/webhook`, and `/lorecast`. Webhook routing performs agent work in-process. | `legacy/main.py` |
| Model provider | Direct `anthropic.Anthropic` SDK client configured by `ANTHROPIC_API_KEY`, with a hardcoded Claude model name. | `legacy/core/claude_client.py`, `legacy/config.py` |
| Persistence | GitLab wiki pages are the authoritative memory store; `LORE-INDEX` maps file paths to `LORE-MEMORY-*` pages. | `legacy/core/memory.py` |
| GitLab integration | `python-gitlab` wrapper reads merge requests/issues/wiki and publishes comments/labels/wiki pages. | `legacy/core/gitlab_client.py` |
| CLI | `sync`, `validate`, `stats`, and `dashboard` operate on GitLab/Markdown records. | `lore-cli/lore_cli/cli.py` |
| Dashboard | Static HTML with representative hardcoded memories, not a live product/API view. | `public/index.html` |
| Tests | CLI-only unit tests for Markdown parsing, validation, statistics, and dashboard rendering. | `lore-cli/tests/` |

## What does not exist

- No CockroachDB driver, connection layer, schema, migrations, transactions, vector queries, or vector-index evidence in production code.
- No Bedrock client, embedding abstraction, reasoning abstraction, model configuration, structured response validation, or prompt versioning.
- No durable task table, idempotency key, SQS/Lambda/API Gateway runtime, retry recovery, outbox, audit log, or tenant isolation.
- No managed-MCP client integration; only the Cloud Console generated setup has been recorded in Phase 0 evidence.
- No live GitLab project/webhook target for end-to-end delivery verification.

## Conflicting or obsolete architecture to replace

| Surface | Why it cannot remain canonical |
|---|---|
| Wiki `MemoryStore` | It assigns sequential IDs by listing wiki pages and performs multiple independent writes; it cannot provide transactional supersession, typed relationships, embeddings, provenance, or concurrency safety. |
| Direct Anthropic client | Phase 0 proved Bedrock embedding and reasoning access; the production runtime must use Bedrock instead of requiring `ANTHROPIC_API_KEY`. |
| Synchronous `/webhook` | Incoming work is processed in the request lifecycle, with no durable task state, idempotency, or failure recovery. |
| Static `public/index.html` | It contains illustrative records and cannot provide provenance, retrieval history, or actual memory state. |
| Placeholder/no-op code | `.gitlab-ci.yml` has a placeholder LORECAST scheduled job; `agents/agent.yml.template` explicitly returns a placeholder response; `src/api/auth.py` is sample/insecure code and not an application runtime. |

## Preserved product value

- LORE’s institutional-memory voice and the core distinction between decisions, rejected alternatives, reasons, future implications, and dependencies.
- The workflow semantics: SPECFORGE, GUARDKEEPER, REPLY_HANDLER, LOREKEEPER, LORECAST, ONBOARDING, and LORE Ask.
- Existing Markdown as an import/export and migration source only; it must not remain authoritative.
- CLI validation tests as source material for migration-format compatibility, not as the future persistence contract.

## Phase 2 entry point

Create a single typed Python domain model for memories, sources, scopes, relationships, tasks, retrieval events/candidates, actions, feedback, audits, and outbox events. The model must become the shared contract before a CockroachDB migration or Bedrock runtime is introduced.
