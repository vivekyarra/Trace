"""Public, read-only Trace agent demo deployed as an AWS Lambda Function URL."""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
from collections import deque
from time import monotonic
from typing import Any
from uuid import UUID

from trace_memory.runtime import production_read_only_pipeline

PRESET_DIFF = """diff --git a/src/api/auth.py b/src/api/auth.py
index 88f94f1..fa07e6b 100644
--- a/src/api/auth.py
+++ b/src/api/auth.py
@@ -18,6 +18,14 @@ def authorize(user_id: str, resource: str) -> bool:
+    cache_key = f"{user_id}:{resource}"
+    cached = permission_cache.get(cache_key)
+    if cached and cached.age_seconds < 600:
+        return cached.allowed
+
     return policy_engine.check(user_id, resource)
"""

_REQUEST_TIMES: deque[float] = deque()
_RATE_LOCK = threading.Lock()
_LOGGER = logging.getLogger(__name__)


def _live_run(diff: str) -> dict[str, object]:
    required = ("DATABASE_URL", "TRACE_ORGANIZATION_ID", "TRACE_REPOSITORY_ID")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("live runtime is missing required configuration")
    pipeline = production_read_only_pipeline(
        database_url=os.environ["DATABASE_URL"],
        embedding_model_id=os.environ.get(
            "BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
        ),
        reasoning_model_id=os.environ.get(
            "BEDROCK_REASONING_MODEL_ID", "apac.amazon.nova-pro-v1:0"
        ),
        fallback_model_id=os.environ.get(
            "BEDROCK_FALLBACK_MODEL_ID", "mistral.mistral-large-2402-v1:0"
        ),
    )
    return pipeline.run(
        organization_id=UUID(os.environ["TRACE_ORGANIZATION_ID"]),
        repository_id=UUID(os.environ["TRACE_REPOSITORY_ID"]),
        diff=diff,
    )


def _html() -> str:
    preset = json.dumps(PRESET_DIFF)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Trace — Memory with standing</title>
<style>
:root{{color-scheme:dark;--bg:#03070d;--panel:#09111d;--panel2:#0c1726;--line:#1d3045;--ink:#f4f8fb;--muted:#8093a8;--mint:#57f0bd;--blue:#67b7ff;--red:#ff647c}}
*{{box-sizing:border-box}}html,body{{height:100%;overflow:hidden}}body{{margin:0;background:radial-gradient(900px 520px at 18% -10%,#163b3b 0,transparent 62%),radial-gradient(850px 520px at 96% 8%,#102f55 0,transparent 58%),var(--bg);color:var(--ink);font:15px/1.4 Inter,ui-sans-serif,system-ui;letter-spacing:-.01em}}
body:before{{content:"";position:fixed;inset:0;pointer-events:none;background-image:linear-gradient(#ffffff05 1px,transparent 1px),linear-gradient(90deg,#ffffff05 1px,transparent 1px);background-size:44px 44px;mask-image:linear-gradient(to bottom,#0008,transparent 78%)}}
main{{position:relative;width:min(1180px,100%);height:100vh;margin:auto;padding:14px 24px;display:flex;flex-direction:column}}nav{{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}}.brand{{display:flex;gap:9px;align-items:center;font-size:17px;font-weight:850}}.mark{{display:grid;place-items:center;width:30px;height:30px;border:1px solid #65f4c866;border-radius:10px;background:#57f0bd12;box-shadow:0 0 30px #57f0bd22;color:var(--mint)}}.live{{display:flex;align-items:center;gap:8px;padding:6px 10px;border:1px solid #28425b;border-radius:999px;color:#a8bbcc;font-size:10px;font-weight:800;letter-spacing:.12em}}.dot{{width:7px;height:7px;background:var(--mint);border-radius:50%;box-shadow:0 0 12px var(--mint)}}
.hero{{display:grid;grid-template-columns:1.35fr .65fr;gap:20px;align-items:end;margin-bottom:8px}}h1{{font-size:clamp(2.4rem,4vw,3.65rem);line-height:.88;letter-spacing:-.065em;margin:0;white-space:nowrap}}h1 span{{color:var(--mint)}}.sub{{color:#9cafc2;font-size:14px;max-width:390px;padding-bottom:2px}}.meta{{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}}.chip{{padding:5px 8px;border:1px solid var(--line);border-radius:7px;color:#9fb2c5;font:700 9px ui-monospace,monospace;text-transform:uppercase}}
.pipeline{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:8px 0}}.step{{position:relative;padding:8px 12px;border:1px solid var(--line);border-radius:11px;background:#08111ccc;color:var(--muted);overflow:hidden}}.step:after{{content:"";position:absolute;left:0;bottom:0;width:0;height:2px;background:var(--mint);transition:.35s}}.step.on,.step.done{{border-color:#4adbb06b}}.step.on:after,.step.done:after{{width:100%}}.num{{color:var(--mint);font:700 9px ui-monospace,monospace}}.step b{{display:inline;margin:0 7px;color:var(--ink);font-size:12px}}.step small{{font-size:10px}}
.workspace{{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(330px,.85fr);gap:12px;flex:1;min-height:0}}.panel{{background:linear-gradient(145deg,#0b1624ed,#07101bed);border:1px solid var(--line);border-radius:16px;box-shadow:0 22px 60px #0008;overflow:hidden}}.workspace>.panel:first-child{{display:flex;flex-direction:column;min-height:0}}.bar{{display:flex;align-items:center;justify-content:space-between;padding:9px 14px;border-bottom:1px solid var(--line);color:#9dafc0;font:700 10px ui-monospace,monospace;text-transform:uppercase}}.bar span:last-child{{color:#526b82}}textarea{{display:block;width:100%;height:auto;min-height:0;flex:1;resize:none;border:0;outline:0;background:#050b13cc;color:#cde0ef;padding:15px;font:11px/1.45 "SFMono-Regular",Consolas,monospace}}.actions{{display:flex;align-items:center;gap:9px;padding:9px 12px;border-top:1px solid var(--line)}}button{{border:0;border-radius:9px;padding:9px 14px;font-weight:850;cursor:pointer}}#run{{background:var(--mint);color:#04110d;box-shadow:0 8px 30px #57f0bd2b}}button.secondary{{background:#122238;color:#c8d7e5;border:1px solid #28415b}}button:disabled{{opacity:.55;cursor:wait}}#status{{margin-left:auto;color:#71879a;font:10px ui-monospace,monospace;text-align:right}}
.result{{min-height:0;display:flex;flex-direction:column}}.idle{{display:grid;place-items:center;flex:1;color:#52677a;text-align:center}}.orb{{width:62px;height:62px;border-radius:50%;border:1px solid #2a4c61;background:radial-gradient(circle,#57f0bd2b,transparent 67%);box-shadow:0 0 70px #57f0bd12;margin:auto auto 12px;animation:pulse 2.8s ease-in-out infinite}}@keyframes pulse{{50%{{transform:scale(1.07);box-shadow:0 0 95px #57f0bd24}}}}#result{{display:none;padding:15px;overflow:auto}}.badge{{display:inline-flex;padding:5px 8px;border-radius:7px;background:#172a3d;color:var(--blue);font:800 9px ui-monospace,monospace}}#verdict{{font-size:34px;letter-spacing:-.05em;margin:10px 0 6px}}#summary{{color:#adbdca;font-size:12px}}.consequence{{margin-top:12px;padding:11px;border:1px solid #593441;border-left:3px solid var(--red);border-radius:9px;background:#2a101822;color:#eab7c1;font-size:11px}}#stageRows{{display:grid;gap:4px;margin-top:10px;color:#7f95a8;font:9px ui-monospace,monospace}}details{{margin-top:auto;border-top:1px solid var(--line);padding:9px 15px;color:#89a0b4}}summary{{cursor:pointer;font:750 9px ui-monospace,monospace;text-transform:uppercase}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;color:#a8bdd0;font-size:9px;max-height:220px;overflow:auto}}footer{{display:flex;justify-content:space-between;gap:12px;margin-top:7px;color:#5f7487;font:9px ui-monospace,monospace}}a{{color:#809eb9;text-decoration:none}}a:hover{{color:var(--mint)}}
@media(max-height:700px) and (min-width:851px){{.hero{{grid-template-columns:1fr;margin-bottom:5px}}h1{{font-size:3.1rem}}.sub{{display:none}}.meta{{position:absolute;right:24px;top:57px;margin:0}}.pipeline{{margin:6px 0}}}}@media(max-width:850px){{html,body{{height:auto;overflow:auto}}main{{height:auto;min-height:100vh;padding:16px}}.hero,.workspace{{grid-template-columns:1fr}}.pipeline{{grid-template-columns:1fr 1fr}}h1{{font-size:clamp(1.8rem,8vw,3.5rem)}}.sub{{display:none}}textarea{{height:270px;flex:none}}.result{{min-height:360px}}#status{{display:none}}}}@media(max-width:500px){{main{{padding:14px}}.pipeline{{grid-template-columns:1fr 1fr}}footer{{flex-direction:column}}}}
</style></head><body><main>
<nav><div class="brand"><div class="mark">T</div>Trace</div><div class="live"><i class="dot"></i>LIVE · AP-SOUTH-1</div></nav>
<section class="hero"><div><h1>Memory with <span>standing.</span></h1><div class="meta"><span class="chip">Read only</span><span class="chip">No replay</span><span class="chip">Provenance on</span></div></div><div class="sub">Yesterday's decision becomes today's review gate.</div></section>
<section class="pipeline"><div class="step" id="s0"><span class="num">01</span><b>Embed</b><small>Amazon Titan</small></div><div class="step" id="s1"><span class="num">02</span><b>Retrieve</b><small>CockroachDB</small></div><div class="step" id="s2"><span class="num">03</span><b>Reason</b><small>Bedrock</small></div><div class="step" id="s3"><span class="num">04</span><b>Consequence</b><small>Auditable receipt</small></div></section>
<section class="workspace"><div class="panel"><div class="bar"><span>Pull request diff</span><span>PR #5</span></div><textarea id="diff" spellcheck="false"></textarea><div class="actions"><button id="run">Run Trace</button><button class="secondary" id="preset">Reset</button><span id="status">READY</span></div></div>
<div class="panel result"><div class="bar"><span>Review signal</span><span>Live receipt</span></div><div class="idle" id="idle"><div><div class="orb"></div>AWAITING DIFF</div></div><section id="result"><span class="badge" id="mode"></span><h2 id="verdict"></h2><div id="summary"></div><div class="consequence" id="counterfactual"></div><div id="stageRows"></div></section><details id="receipt"><summary>Execution receipt</summary><pre id="json"></pre></details></div></section>
<footer><span>BEDROCK → COCKROACHDB → BEDROCK</span><span><a href="https://github.com/vivekyarra/Trace/pull/4">MEMORY PR</a> · <a href="https://github.com/vivekyarra/Trace/pull/5">CONFLICT PR</a> · <a href="https://github.com/vivekyarra/Trace">SOURCE</a></span></footer>
<script>const preset={preset};const diff=document.querySelector('#diff');const run=document.querySelector('#run');const status=document.querySelector('#status');const steps=[0,1,2,3].map(i=>document.querySelector('#s'+i));document.querySelector('#preset').onclick=()=>{{diff.value=preset}};diff.value=preset;run.onclick=async()=>{{run.disabled=true;steps.forEach(x=>x.className='step');steps[0].classList.add('on');status.textContent='RUNNING';try{{const response=await fetch('api/run',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{diff:diff.value}})}});const data=await response.json();if(!response.ok)throw data;steps.forEach(x=>x.className='step done');document.querySelector('#idle').style.display='none';document.querySelector('#result').style.display='block';document.querySelector('#mode').textContent=data.mode+' · '+data.total_elapsed_ms+' MS';document.querySelector('#verdict').textContent=data.judgment.classification+' · '+data.judgment.severity;document.querySelector('#summary').textContent=data.judgment.summary;document.querySelector('#counterfactual').textContent=data.memory_consequence_receipt.counterfactual;document.querySelector('#stageRows').innerHTML=data.stages.map(s=>'<span>'+s.name.toUpperCase()+' · '+s.elapsed_ms+' MS</span>').join('');document.querySelector('#json').textContent=JSON.stringify(data,null,2);status.textContent='VERIFIED LIVE'}}catch(error){{steps.forEach(x=>x.className='step');status.textContent='LIVE UNAVAILABLE';document.querySelector('#idle').innerHTML='<div><div class="orb"></div>NO RESULT FABRICATED</div>'}}finally{{run.disabled=false}}}};</script></main></body></html>"""


def _rate_limited() -> bool:
    limit = max(1, min(int(os.environ.get("TRACE_REQUESTS_PER_MINUTE", "12")), 60))
    cutoff = monotonic() - 60
    with _RATE_LOCK:
        while _REQUEST_TIMES and _REQUEST_TIMES[0] < cutoff:
            _REQUEST_TIMES.popleft()
        if len(_REQUEST_TIMES) >= limit:
            return True
        _REQUEST_TIMES.append(monotonic())
        return False


def _response(status: int, body: str, content_type: str) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type": content_type,
            "cache-control": "no-store",
            "content-security-policy": (
                "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
            ),
            "x-content-type-options": "nosniff",
            "referrer-policy": "no-referrer",
        },
        "body": body,
    }


def handler(event: dict[str, Any], _context: object) -> dict[str, Any]:
    path = str(event.get("rawPath", "/")).rstrip("/") or "/"
    method = str(event.get("requestContext", {}).get("http", {}).get("method", "GET")).upper()
    if path == "/" and method == "GET":
        return _response(200, _html(), "text/html; charset=utf-8")
    if path == "/healthz" and method == "GET":
        return _response(200, json.dumps({"status": "ok", "primary_mode": "live-read-only"}), "application/json")
    if path == "/api/status" and method == "GET":
        status = {
            "status": "ready",
            "primary_mode": "live-read-only",
            "live_stages": ["bedrock-embedding", "cockroachdb-retrieval", "bedrock-classification"],
            "write_routes": 0,
            "replay_mode": False,
            "rate_limit_per_warm_instance_per_minute": max(
                1, min(int(os.environ.get("TRACE_REQUESTS_PER_MINUTE", "12")), 60)
            ),
        }
        return _response(200, json.dumps(status), "application/json")
    if path == "/api/run" and method == "POST":
        if _rate_limited():
            response = _response(
                429,
                json.dumps({"error": "Live demo rate limit reached; retry in one minute.", "mode": "NOT_RUN"}),
                "application/json",
            )
            response["headers"]["retry-after"] = "60"
            return response
        try:
            raw_body = str(event.get("body", ""))
            if event.get("isBase64Encoded"):
                raw_body = base64.b64decode(raw_body).decode("utf-8")
            payload = json.loads(raw_body or "{}")
            result = _live_run(str(payload.get("diff", "")))
            return _response(200, json.dumps(result, default=str), "application/json")
        except (ValueError, json.JSONDecodeError) as error:
            return _response(400, json.dumps({"error": str(error), "mode": "NOT_RUN"}), "application/json")
        except Exception as error:
            _LOGGER.exception("live Trace run failed")
            error_response = getattr(error, "response", {})
            error_code = error_response.get("Error", {}).get("Code") if isinstance(error_response, dict) else None
            return _response(
                503,
                json.dumps(
                    {
                        "error": "A live dependency did not complete. No result was fabricated.",
                        "dependency_error": error_code or type(error).__name__,
                        "mode": "NOT_RUN",
                    }
                ),
                "application/json",
            )
    return _response(404, json.dumps({"error": "not found"}), "application/json")
