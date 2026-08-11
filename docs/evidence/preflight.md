# Phase 0 cloud preflight

Run: 2026-08-11 (Asia/Kolkata)
Scope: live CockroachDB Cloud and AWS sessions authenticated in Chrome, plus the `D:\Lore-cockroachDB` workspace.

This is evidence, not an architecture claim. A capability marked **NOT VERIFIED** must be retested before it is used as a production assumption.

## CockroachDB Cloud

| Check | Result | Observed evidence |
|---|---|---|
| Competition cluster | **VERIFIED** | `lucid-owlet` is Available on the Basic plan, hosted on AWS in Mumbai (`ap-south-1`). No second cluster was created. |
| Version | **VERIFIED** | `SELECT version()` returned `CockroachDB CCL v26.2.5`. |
| SQL access | **VERIFIED** | The Cloud SQL Shell connected as the authenticated console user to `defaultdb` and executed SQL successfully. |
| `VECTOR` support | **VERIFIED** | `CREATE TABLE lore_preflight_vectors (... embedding VECTOR(3) NOT NULL)` succeeded. |
| Vector index | **VERIFIED** | `CREATE VECTOR INDEX lore_preflight_vectors_embedding_idx ON lore_preflight_vectors (embedding)` succeeded. |
| Prefix vector-index syntax | **VERIFIED** | `CREATE VECTOR INDEX lore_preflight_vectors_prefix_idx ON lore_preflight_vectors (organization_id, repository_id, embedding)` succeeded. This is the tested tenant/repository-prefix form for this cluster version. |
| Representative vector query | **VERIFIED** | A cosine-distance query over three vectors returned IDs `1`, `2`, `3` with distances `0`, `0.006116251198662548`, `1` respectively. |
| `EXPLAIN` | **VERIFIED, negative result** | The tested three-row query plans a primary-key full scan, not either vector index. See `docs/evidence/vector-explain.txt`. Do **not** claim accelerated vector retrieval until a realistic corpus and plan demonstrate index selection. |
| Managed MCP configuration | **VERIFIED** | Cloud Console generated the cluster-scoped OAuth command for `https://cockroachlabs.cloud/mcp` with header `mcp-cluster-id: 9727d881-7fa9-4e9c-9e57-437e1afad9b7`. |
| Managed MCP authenticated call | **NOT VERIFIED** | This machine has no Claude/MCP client (`claude` is not installed), so the OAuth read-only authorization flow and an MCP tool call were not exercised. |
| Read-only database access | **PARTIALLY VERIFIED** | Role `lore_preflight_readonly` has only `SELECT` on the isolated preflight table and was granted to SQL user `yarra`. Cloud SQL Shell blocks `SET ROLE` as a disallowed statement type, so an independent role login must still prove `SELECT` succeeds and writes fail. |

### Test objects

The following isolated test objects remain in `defaultdb.public` so that subsequent preflight and implementation work can inspect the same results:

```sql
lore_preflight_vectors
lore_preflight_vectors_embedding_idx
lore_preflight_vectors_prefix_idx
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
| Reasoning model | **VERIFIED** | CloudShell invoked `global.anthropic.claude-sonnet-4-5-20250929-v1:0` through Bedrock and returned `LORE preflight OK`. Direct on-demand model invocation was rejected because this model requires an inference profile; the global profile is the verified configuration value. |
| Lambda runtime compatibility | **NOT VERIFIED** | The existing CLI declares Python `>=3.10`, so `python3.12` is compatible at the declared-language level. No Lambda function/package has been selected or deployed, so runtime compatibility remains unproven. |

### Verified invocation commands

The commands were run in AWS CloudShell in `ap-south-1`; temporary response files stayed in CloudShell and contain no credentials.

```bash
aws bedrock-runtime invoke-model \
  --region ap-south-1 \
  --cli-binary-format raw-in-base64-out \
  --model-id amazon.titan-embed-text-v2:0 \
  --content-type application/json \
  --accept application/json \
  --body '{"inputText":"LORE preflight embedding","dimensions":1024,"normalize":true}' \
  /tmp/lore-titan.json
```

```bash
aws bedrock-runtime invoke-model \
  --region ap-south-1 \
  --cli-binary-format raw-in-base64-out \
  --model-id global.anthropic.claude-sonnet-4-5-20250929-v1:0 \
  --content-type application/json \
  --accept application/json \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":32,"messages":[{"role":"user","content":"Reply only: LORE preflight OK"}]}' \
  /tmp/lore-reasoning.json
```

## GitLab

| Check | Result | Observed evidence |
|---|---|---|
| Authentication mechanism | **VERIFIED** | `glab auth status` reports authenticated HTTPS and API access to `https://gitlab.com/api/v4/` as `vivekyarra567`; `GET /user` returned HTTP 200. |
| General API read access | **PARTIALLY VERIFIED** | `GET /projects?membership=true&simple=true&per_page=1` returned HTTP 200. Target-project permissions are not established. |
| Webhook headers in a live delivery | **NOT VERIFIED** | No GitLab project/webhook endpoint or captured delivery has been supplied. Legacy source expects `X-Gitlab-Event` and `X-Gitlab-Token`, but that remains source-only evidence. |

## Source-control context

The working tree is now the `vivekyarra/Trace` GitHub repository, on branch `phase/0-cloud-preflight`. The remote is configured as `https://github.com/vivekyarra/Trace.git`; `main` has not been pushed or changed.

## Remaining Phase 0 gates

1. Generate and exercise a CockroachDB Managed MCP read-only configuration against `lucid-owlet`.
2. Create and independently connect with a least-privilege SQL role to prove reads succeed and writes fail.
3. Build a representative vector corpus, rerun `EXPLAIN`, and retain only a query/index design whose plan uses the vector index.
4. Package and invoke the chosen Lambda runtime before declaring Lambda compatibility.
5. Supply the GitLab target project and webhook endpoint, then send a harmless test delivery and capture its headers.
