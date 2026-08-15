# Phase 0 cloud preflight

Run: 2026-08-11 (Asia/Kolkata)
Scope: live CockroachDB Cloud and AWS sessions authenticated in Chrome, plus the active workspace and the `vivekyarra/Trace` GitHub repository. GitLab is explicitly out of scope for this GitHub-only product.

This is evidence, not an architecture claim. A capability marked **NOT VERIFIED** must be retested before it is used as a production assumption.

## CockroachDB Cloud

| Check | Result | Observed evidence |
|---|---|---|
| Competition cluster | **VERIFIED** | `lucid-owlet` is Available on the Basic plan, hosted on AWS in Mumbai (`ap-south-1`). No second cluster was created. |
| Version | **VERIFIED** | `SELECT version()` returned `CockroachDB CCL v26.2.5`. |
| SQL access | **VERIFIED** | The Cloud SQL Shell connected as the authenticated console user to `defaultdb` and executed SQL successfully. |
| `VECTOR` support | **VERIFIED** | `CREATE TABLE trace_preflight_vectors (... embedding VECTOR(3) NOT NULL)` succeeded. |
| Vector index | **VERIFIED** | `CREATE VECTOR INDEX trace_preflight_vectors_embedding_idx ON trace_preflight_vectors (embedding)` succeeded. |
| Prefix vector-index syntax | **VERIFIED** | `CREATE VECTOR INDEX trace_preflight_vectors_prefix_idx ON trace_preflight_vectors (organization_id, repository_id, embedding)` succeeded. This is the tested tenant/repository-prefix form for this cluster version. |
| Representative vector query | **VERIFIED** | A cosine-distance query over three vectors returned IDs `1`, `2`, `3` with distances `0`, `0.006116251198662548`, `1` respectively. |
| `EXPLAIN` | **VERIFIED, negative result** | The tested three-row query plans a primary-key full scan, not either vector index. See `docs/evidence/vector-explain.txt`. Do **not** claim accelerated vector retrieval until a realistic corpus and plan demonstrate index selection. |
| Managed MCP configuration | **VERIFIED** | Cloud Console generated Codex configuration for `https://cockroachlabs.cloud/mcp` with header `mcp-cluster-id: 9727d881-7fa9-4e9c-9e57-437e1afad9b7`; the same configuration is installed in the local Codex client. |
| Managed MCP transport and OAuth discovery | **VERIFIED** | A live unauthenticated `initialize` request reached the endpoint and returned `401` with `WWW-Authenticate: Bearer`, resource metadata at `/.well-known/oauth-protected-resource/mcp`, and supported scopes `mcp:read`, `mcp:write`. This proves the managed endpoint and its authorization server are live. |
| Managed MCP read-only tool call | **VERIFIED** | Codex completed the CockroachDB Cloud OAuth flow with **Read Data** only; Write Data remained unchecked. A live `cockroachdb-cloud/list_databases` MCP call then returned `defaultdb`. |
| Read-only database access | **VERIFIED** | An independently connected temporary SQL login inherited only `trace_preflight_readonly`: `SELECT count(*)` returned `3`; an `INSERT` failed with `does not have INSERT privilege`. The temporary user and password were removed immediately after the probe. |

### Test objects

The following isolated test objects remain in `defaultdb.public` so that subsequent preflight and implementation work can inspect the same results:

```sql
trace_preflight_vectors
trace_preflight_vectors_embedding_idx
trace_preflight_vectors_prefix_idx
```

They contain only three synthetic vectors and no application or personal data. They may be dropped after durable migration tests replace them.

### Managed MCP configuration

The Cloud Console generated this client command. It contains a public endpoint and cluster ID, not a secret:

```bash
claude mcp add cockroachdb-cloud https://cockroachlabs.cloud/mcp \
  --transport http \
  --header "mcp-cluster-id: 9727d881-7fa9-4e9c-9e57-437e1afad9b7"
```

The required next verification is to authenticate with **read-only** consent, then invoke a non-mutating MCP tool such as schema listing or `EXPLAIN`.

## AWS

| Check | Result | Observed evidence |
|---|---|---|
| Selected region | **VERIFIED** | AWS Console region is Asia Pacific (Mumbai), `ap-south-1`, matching the CockroachDB cluster provider region. |
| Titan embeddings | **VERIFIED** | CloudShell invoked `amazon.titan-embed-text-v2:0` with `dimensions: 1024` and `normalize: true`. The response contained `embedding_length: 1024` and `inputTextTokenCount: 6`. |
| Reasoning model | **VERIFIED** | CloudShell invoked `global.anthropic.claude-sonnet-4-5-20250929-v1:0` through Bedrock and returned `Trace preflight OK`. Direct on-demand model invocation was rejected because this model requires an inference profile; the global profile is the verified configuration value. |
| Lambda runtime compatibility | **VERIFIED** | In `ap-south-1`, a real `trace-preflight-python312` Lambda using runtime `python3.12` was deployed with an isolated execution role and invoked successfully. It returned `StatusCode: 200` and `{"statusCode": 200, "body": "Trace Lambda preflight OK"}`. |

### Verified invocation commands

The commands were run in AWS CloudShell in `ap-south-1`; temporary response files stayed in CloudShell and contain no credentials.

```bash
aws bedrock-runtime invoke-model \
  --region ap-south-1 \
  --cli-binary-format raw-in-base64-out \
  --model-id amazon.titan-embed-text-v2:0 \
  --content-type application/json \
  --accept application/json \
  --body '{"inputText":"Trace preflight embedding","dimensions":1024,"normalize":true}' \
  /tmp/trace-titan.json
```

```bash
aws bedrock-runtime invoke-model \
  --region ap-south-1 \
  --cli-binary-format raw-in-base64-out \
  --model-id global.anthropic.claude-sonnet-4-5-20250929-v1:0 \
  --content-type application/json \
  --accept application/json \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":32,"messages":[{"role":"user","content":"Reply only: Trace preflight OK"}]}' \
  /tmp/trace-reasoning.json
```

## GitHub (replaces GitLab for this product)

| Check | Result | Observed evidence |
|---|---|---|
| Authentication mechanism | **VERIFIED** | `gh auth status` reports the authenticated GitHub account `vivekyarra`; API identity lookup succeeded. |
| Target repository API permissions | **VERIFIED** | GitHub API reports admin, maintain, push, triage, and pull permissions on `vivekyarra/Trace`. |
| Webhook headers in a live delivery | **VERIFIED** | A temporary GitHub webhook delivered a successful `ping` (HTTP 200) to a test receiver. GitHub recorded `X-Github-Event: ping`, `X-Github-Delivery`, `X-Github-Hook-Id`, `X-Github-Hook-Installation-Target-Id`, and `X-Github-Hook-Installation-Target-Type`. The temporary hook was removed after the test. |

## Source-control context

The working tree is the `vivekyarra/Trace` GitHub repository. `main` is the repository default branch; Phase 0 and implementation changes are promoted only after the GitHub Actions verification gate passes.

## Remaining Phase 0 gates

1. Before claiming vector-index acceleration, rerun `EXPLAIN` against a realistic corpus; the current three-row plan deliberately does not establish that claim.
