import asyncio
import logging
import hmac
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse

from config import WEBHOOK_SECRET, PORT
from agents.tracekeeper import run_tracekeeper
from agents.guardkeeper import run_guardkeeper
from agents.specforge import run_specforge, run_spec_compliance, handle_spec_approval
from agents.tracecast import run_tracecast

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Trace server starting up")
    yield
    logger.info("Trace server shutting down")


app = FastAPI(
    title="Trace",
    description="Multi-agent GitLab automation for institutional memory",
    version="1.0.0",
    lifespan=lifespan
)


def verify_webhook_secret(token: str) -> bool:
    """Verify the GitLab webhook secret token."""
    if not WEBHOOK_SECRET:
        return True
    return hmac.compare_digest(token or "", WEBHOOK_SECRET)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "Trace"}


@app.post("/webhook")
async def webhook(
    request: Request,
    x_gitlab_event: str = Header(None),
    x_gitlab_token: str = Header(None),
):
    """
    Main webhook receiver. Routes all GitLab events to the correct agent.
    """
    if not verify_webhook_secret(x_gitlab_token):
        logger.warning("Webhook received with invalid secret token")
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    payload = await request.json()
    logger.info("Received GitLab event: %s", x_gitlab_event)

    try:
        if x_gitlab_event == "Merge Request Hook":
            action = payload.get("object_attributes", {}).get("action")
            logger.info("MR action: %s", action)

            if action == "merge":
                logger.info("Routing to Tracekeeper")
                await run_tracekeeper(payload)

            elif action == "open":
                logger.info("Routing to GUARDKEEPER and SPECFORGE compliance")
                await asyncio.gather(
                    run_guardkeeper(payload),
                    run_spec_compliance(payload),
                )

            else:
                logger.info("MR action '%s' — no agent handles this", action)

        elif x_gitlab_event == "Note Hook":
            note_body = (payload.get("object_attributes", {}).get("note") or "").lower()
            noteable_type = payload.get("object_attributes", {}).get("noteable_type", "")
            logger.info("Note on %s: %s", noteable_type, note_body[:80])

            if noteable_type == "MergeRequest":
                if "trace: intentional" in note_body:
                    logger.info("Routing to GUARDKEEPER reply handler — intentional")
                    await run_guardkeeper(payload, reply_type="intentional")
                elif "trace: accidental" in note_body:
                    logger.info("Routing to GUARDKEEPER reply handler — accidental")
                    await run_guardkeeper(payload, reply_type="accidental")
                elif "trace: discuss" in note_body:
                    logger.info("Routing to GUARDKEEPER reply handler — discuss")
                    await run_guardkeeper(payload, reply_type="discuss")

            elif noteable_type == "Issue":
                if "trace: spec approved" in note_body or note_body.strip() == "approved":
                    logger.info("Routing to SPECFORGE spec approval")
                    await handle_spec_approval(payload)
                if "trace health" in note_body or "@trace health" in note_body:
                    logger.info("Routing to Tracecast (triggered by @trace health)")
                    await run_tracecast()

        elif x_gitlab_event == "Issue Hook":
            issue_body = payload.get("object_attributes", {}).get("description", "") or ""
            title = payload.get("object_attributes", {}).get("title", "") or ""
            if "@trace" in issue_body or "@trace" in title:
                logger.info("Routing to SPECFORGE")
                await run_specforge(payload)
            if "trace health" in (issue_body + " " + title).lower() or "@trace health" in (issue_body + title):
                logger.info("Routing to Tracecast (triggered by @trace health in issue)")
                await run_tracecast()

        else:
            logger.info("Unhandled event type: %s", x_gitlab_event)

    except Exception as e:
        logger.error("Error processing webhook: %s", e, exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"status": "error", "message": str(e)},
        )

    return JSONResponse(status_code=200, content={"status": "received"})


@app.post("/tracecast")
async def trigger_tracecast():
    """
    On-demand trigger for Tracecast health report.
    Hit this endpoint manually or for demo purposes.
    """
    logger.info("Tracecast triggered manually via /tracecast endpoint")
    try:
        await run_tracecast()
        return JSONResponse(status_code=200, content={"status": "tracecast complete"})
    except Exception as e:
        logger.error("Tracecast failed: %s", e, exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)