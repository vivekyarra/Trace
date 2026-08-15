# Phase 0 cloud preflight

Revalidated: 2026-08-15 (Asia/Kolkata)
Scope: live CockroachDB Cloud and AWS sessions authenticated in Chrome, plus the active workspace and the `vivekyarra/Trace` GitHub repository.

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
| Production `EXPLAIN ANALYZE` | **VERIFIED, positive result** | The materialized production ANN query over 10,000 realistic 1024-dimensional rows uses `memories_embedding_vector_idx`, exact organization/repository prefix spans, and no full scan. Thirty database executions measured 79.5 ms median and 90 ms p95; the vector operator measured 15.5 ms median and 20 ms p95. See `docs/evidence/vector-explain.txt`. |
| Managed MCP configuration | **VERIFIED** | Cloud Console generated Codex configuration for `https://cockroachlabs.cloud/mcp` with header `mcp-cluster-id: 9727d881-7fa9-4e9c-9e57-437e1afad9b7`; the same configuration is installed in the local Codex client. |
| Managed MCP transport and OAuth discovery | **VERIFIED** | A live unauthenticated `initialize` request reached the endpoint and returned `401` with `WWW-Authenticate: Bearer`, resource metadata at `/.well-known/oauth-protected-resource/mcp`, and supported scopes `mcp:read`, `mcp:write`. This proves the managed endpoint and its authorization server are live. |
| Managed MCP read-only tool call | **VERIFIED** | Codex completed the CockroachDB Cloud OAuth flow with **Read Data** only; Write Data remained unchecked. A live `cockroachdb-cloud/list_databases` MCP call then returned `defaultdb`. |
| Read-only database access | **VERIFIED** | An independently connected temporary SQL login inherited only `trace_preflight_readonly`: `SELECT count(*)` returned `3`; an `INSERT` failed with `does not have INSERT privilege`. The temporary user and password were removed immediately after the probe. |

### Historical test objects

The following isolated test objects remain in `defaultdb.public` so that subsequent preflight and implementation work can inspect the same results:

```sql
trace_preflight_vectors
trace_preflight_vectors_embedding_idx
trace_preflight_vectors_prefix_idx
```

They contain only three synthetic vectors and no application or personal data. That early scan was a syntax preflight only and has been superseded by the isolated 10,000-row production-schema benchmark.

### Managed MCP configuration

The Cloud Console generated this client command. It contains a public endpoint and cluster ID, not a secret:

```bash
claude mcp add cockroachdb-cloud https://cockroachlabs.cloud/mcp \
  --transport http \
  --header "mcp-cluster-id: 9727d881-7fa9-4e9c-9e57-437e1afad9b7"
```

Read-only consent and non-mutating schema/query calls were subsequently verified in the final Managed MCP audit.

## AWS

| Check | Result | Observed evidence |
|---|---|---|
| Selected region | **VERIFIED** | AWS Console region is Asia Pacific (Mumbai), `ap-south-1`, matching the CockroachDB cluster provider region. |
| Titan embeddings | **VERIFIED** | CloudShell invoked `amazon.titan-embed-text-v2:0` with `dimensions: 1024` and `normalize: true`. The response contained `embedding_length: 1024` and `inputTextTokenCount: 6`. |
| Reasoning model | **VERIFIED** | The production proof invoked `apac.amazon.nova-pro-v1:0` through Bedrock and recorded it on the memory/action and retrieval rows. Marketplace-backed Opus requests returned `INVALID_PAYMENT_INSTRUMENT`, so they are not claimed in the final proof. |
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
aws bedrock-runtime converse \
  --region ap-south-1 \
  --model-id apac.amazon.nova-pro-v1:0 \
  --messages '[{"role":"user","content":[{"text":"Reply only: Trace preflight OK"}]}]' \
  --inference-config '{"maxTokens":32,"temperature":0}'
```

## GitHub

| Check | Result | Observed evidence |
|---|---|---|
| Authentication mechanism | **VERIFIED** | `gh auth status` reports the authenticated GitHub account `vivekyarra`; API identity lookup succeeded. |
| Target repository API permissions | **VERIFIED** | GitHub API reports admin, maintain, push, triage, and pull permissions on `vivekyarra/Trace`. |
| Webhook headers in a live delivery | **VERIFIED** | A temporary GitHub webhook delivered a successful `ping` (HTTP 200) to a test receiver. GitHub recorded `X-Github-Event: ping`, `X-Github-Delivery`, `X-Github-Hook-Id`, `X-Github-Hook-Installation-Target-Id`, and `X-Github-Hook-Installation-Target-Type`. The temporary hook was removed after the test. |

## Source-control context

The working tree is the `vivekyarra/Trace` GitHub repository. `main` is the repository default branch; Phase 0 and implementation changes are promoted only after the GitHub Actions verification gate passes.

## Remaining Phase 0 gates

None. The realistic vector-index proof and read-only Managed MCP audit supersede the earlier open gates.
