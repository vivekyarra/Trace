# Trace CLI

Trace CLI synchronizes, validates, reports on, and renders dashboards for Trace architectural-decision memories stored in GitLab.

```bash
python -m pip install ".[test]"
trace --help
pytest
```

The durable GitHub, CockroachDB, Bedrock, and SQS runtime is distributed separately as `trace-memory` and exposes `trace-runtime`.
