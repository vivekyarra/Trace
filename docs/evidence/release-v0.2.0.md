# Trace v0.2.0 release evidence

> # HISTORICAL PRE-LIVE VERIFICATION
>
> This record captures the repository before live cloud verification and is retained for audit history. Its external-blocker table is **not current release status**. For the successful GitHub → Amazon Bedrock → CockroachDB evidence chain, immutable identifiers, screenshots, and read-only Managed MCP verification, use the [live core proof](core-live-proof.md).

Date: 2026-08-11 IST
Base main SHA: `dd7d40d59b6a66d39c6fbdc212aa4c3dadba7ca7`

## Verified locally

| Gate | Result | Evidence |
|---|---|---|
| Runtime + compatibility tests | PASS | 79 tests passed under CPython 3.12.13 |
| Static analysis | PASS | Ruff completed with no findings |
| Bytecode compilation | PASS | `python -m compileall -q trace` |
| Dependency audit | PASS | `pip-audit`: no known vulnerabilities after upgrading pytest to 9.0.3 |
| CloudFormation structure | PASS | `cfn-lint infra/aws.yaml` |
| Python artifact | PASS | v0.2.0 wheel built; isolated `trace-runtime --help` succeeded; runtime and both migrations present |
| Diff integrity | PASS | `git diff --check` |
| Container base | PASS | Docker registry resolved pinned Linux/amd64 Python 3.12.13 digest |

## External gates at the time of this historical capture

| Gate | State | Reason/evidence required |
|---|---|---|
| Feature-branch CI | PASS | Final feature SHA `6ffa4d1470264a2390dbe7ca2aa50a5eb67cea34`; run `31512741447` completed successfully |
| PR gate | PASS | PR #1 was `CLEAN` and `MERGEABLE`; PR run `31512883199` completed successfully |
| Runtime image build | PASS IN CI | Feature, PR, and main runs built the pinned Python 3.12.13 image and passed `trace-runtime --help` |
| CockroachDB migration cycle | BLOCKED EXTERNALLY | No `DATABASE_URL` is exposed to this shell; needs fresh and 001→002 live runs |
| AWS stack deployment/alarm test | BLOCKED EXTERNALLY | SDK credential chain has no credentials; needs stack ID and alarm evidence |
| Live GitHub→SQS→Bedrock run | BLOCKED EXTERNALLY | Requires deployed endpoints and runtime secrets |
| Main CI | PASS | Merge SHA `fff4e7b03621b6d8d602e8c9d1e52a38efaa420c`; run `31513023031` completed successfully |

No blocked or pending gate was represented as passed in this historical capture. The later successful live run is recorded separately in the [live core proof](core-live-proof.md), so earlier limitations are not confused with current evidence.
