# LORE v0.2.0 release evidence

Date: 2026-08-11 IST
Base main SHA: `dd7d40d59b6a66d39c6fbdc212aa4c3dadba7ca7`

## Verified locally

| Gate | Result | Evidence |
|---|---|---|
| Runtime + compatibility tests | PASS | 79 tests passed under CPython 3.12.13 |
| Static analysis | PASS | Ruff completed with no findings |
| Bytecode compilation | PASS | `python -m compileall -q lore` |
| Dependency audit | PASS | `pip-audit`: no known vulnerabilities after upgrading pytest to 9.0.3 |
| CloudFormation structure | PASS | `cfn-lint infra/aws.yaml` |
| Python artifact | PASS | v0.2.0 wheel built; isolated `lore-runtime --help` succeeded; runtime and both migrations present |
| Diff integrity | PASS | `git diff --check` |
| Container base | PASS | Docker registry resolved pinned Linux/amd64 Python 3.12.13 digest |

## External gates

| Gate | State | Reason/evidence required |
|---|---|---|
| Feature-branch CI | PASS | SHA `c6df2310aa539e9e3161fa4f08064380dbad5e45`; run `31512451530` completed successfully |
| Runtime image build | PASS IN CI | The same run built the pinned Python 3.12.13 image and passed `lore-runtime --help` |
| CockroachDB migration cycle | BLOCKED EXTERNALLY | No `DATABASE_URL` is exposed to this shell; needs fresh and 001→002 live runs |
| AWS stack deployment/alarm test | BLOCKED EXTERNALLY | SDK credential chain has no credentials; needs stack ID and alarm evidence |
| Live GitHub→SQS→Bedrock run | BLOCKED EXTERNALLY | Requires deployed endpoints and runtime secrets |
| Main CI | PENDING | Only after feature CI and PR merge |

No blocked or pending gate is represented as passed. Update this record with immutable URLs/IDs when the corresponding external environment is available.
