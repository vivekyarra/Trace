"""Public, read-only AWS Lambda judge console for immutable Trace live proof."""

from __future__ import annotations

import json

PROOF = {
    "status": "verified-live-proof-snapshot",
    "captured_at": "2026-08-11",
    "write_routes": 0,
    "source_pr": "https://github.com/vivekyarra/Trace/pull/4",
    "conflict_pr": "https://github.com/vivekyarra/Trace/pull/5",
    "memory": {
        "external_id": "TRACE-MEMORY-00401",
        "id": "679be7b7-1476-4c7e-aacb-318f0cab3e80",
        "status": "ACTIVE",
        "embedding_model": "amazon.titan-embed-text-v2:0",
        "embedding_dimensions": 1024,
        "stored_in_cockroachdb": True,
    },
    "retrieval": {
        "id": "8033c0ed-9596-4aeb-ba95-e31d5825ac34",
        "selected": True,
        "reasoning_model": "apac.anthropic.claude-3-haiku-20240307-v1:0",
        "bedrock_selection": 1.0,
        "github_comment": "https://github.com/vivekyarra/Trace/pull/5#issuecomment-5256843528",
    },
    "cockroachdb_tools": [
        "Distributed Vector Indexing (configured; small-corpus EXPLAIN did not select it)",
        "Managed MCP (OAuth Read Data only; live memory and retrieval rows verified)",
    ],
    "evidence": "https://github.com/vivekyarra/Trace/blob/main/docs/evidence/core-live-proof.md",
}


def _html() -> str:
    proof_json = json.dumps(PROOF, indent=2)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Trace Judge Proof Console</title>
<style>:root{{color-scheme:dark}}body{{margin:0;background:#07111f;color:#eef5ff;font:16px/1.5 system-ui}}main{{max-width:1050px;margin:auto;padding:52px 22px}}h1{{font-size:clamp(2.4rem,7vw,4.7rem);line-height:1;margin:.2em 0}}p{{color:#a7b8cf}}.live{{color:#62e0bf;font-weight:800;letter-spacing:.1em}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:15px;margin:30px 0}}article,details{{background:#102039;border:1px solid #2e4a6c;border-radius:14px;padding:20px}}strong{{display:block;color:#62e0bf;font-size:1.7rem}}a{{color:#7fc8ff}}button{{background:#62e0bf;color:#06111d;border:0;border-radius:9px;padding:11px 16px;font-weight:800;cursor:pointer}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;color:#cfe0f6}}.honest{{border-left:4px solid #f2bb66;padding-left:16px}}</style></head>
<body><main><div class="live">● AWS DEPLOYED · PUBLIC · READ ONLY</div><h1>Your codebase remembers why.</h1>
<p class="honest">Immutable verified live-proof snapshot captured 2026-08-11. This public console remains useful if billing-dependent inference is paused; it does not claim a fresh Bedrock run.</p>
<div class="grid"><article><strong>PR #4</strong><span>governing authorization decision</span></article><article><strong>TRACE-MEMORY-00401</strong><span>CockroachDB governed memory</span></article><article><strong>PR #5</strong><span>conflict caught before merge</span></article><article><strong>2 tools</strong><span>Vector Indexing + Managed MCP</span></article></div>
<p><a href="https://github.com/vivekyarra/Trace/pull/4">Open source PR #4</a> · <a href="https://github.com/vivekyarra/Trace/pull/5">Open rejected PR #5</a> · <a href="https://github.com/vivekyarra/Trace/blob/main/docs/evidence/core-live-proof.md">Inspect full proof</a> · <a href="api/status">JSON status</a></p>
<details><summary><b>Inspect immutable identifiers and model provenance</b></summary><pre>{proof_json}</pre></details>
</main></body></html>"""


def handler(event: dict[str, object], _context: object) -> dict[str, object]:
    path = str(event.get("rawPath", "/"))
    if path in {"/api/status", "/healthz"}:
        body = json.dumps(PROOF if path == "/api/status" else {"status": "ok"})
        content_type = "application/json"
        status = 200
    elif path == "/":
        body = _html()
        content_type = "text/html; charset=utf-8"
        status = 200
    else:
        body = json.dumps({"error": "not found"})
        content_type = "application/json"
        status = 404
    return {
        "statusCode": status,
        "headers": {
            "content-type": content_type,
            "cache-control": "no-store",
            "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
            "x-content-type-options": "nosniff",
            "referrer-policy": "no-referrer",
        },
        "body": body,
    }
