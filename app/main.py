import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, Query, HTTPException
from fastapi.responses import PlainTextResponse
from app.config.settings import settings
from app.db.database import init_db
from app.api.health import health_router
from app.platforms.factory import PlatformAdapterFactory
from app.sessions.manager import SessionManager

# Configure Logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("hirelens-ai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing HireLens AI Database...")
    init_db()
    logger.info(f"HireLens AI Bot Ready! Configured Model: {settings.GEMINI_MODEL}")
    yield
    logger.info("Shutting down HireLens AI service.")


app = FastAPI(
    title="HireLens AI — Backend AI Resume Screening Bot",
    version="1.0 MVP",
    description="Multi-platform AI recruitment screening bot powered by Google Gemini API.",
    lifespan=lifespan
)

app.include_router(health_router)
session_manager = SessionManager()


# ------------------------------------------------------------------
# Telegram Webhook Endpoint
# ------------------------------------------------------------------
@app.post("/webhooks/telegram")
async def telegram_webhook(request: Request):
    payload = await request.json()
    adapter = PlatformAdapterFactory.get_adapter("telegram")
    unified_msg = await adapter.handle_event(payload)
    if unified_msg:
        response_text = await session_manager.handle_message(unified_msg)
        await adapter.send_message(unified_msg.user_id, unified_msg.conversation_id, response_text)
    return {"status": "ok"}


# ------------------------------------------------------------------
# Discord Webhook Endpoint
# ------------------------------------------------------------------
@app.post("/webhooks/discord")
async def discord_webhook(request: Request):
    payload = await request.json()
    adapter = PlatformAdapterFactory.get_adapter("discord")
    unified_msg = await adapter.handle_event(payload)
    if unified_msg:
        response_text = await session_manager.handle_message(unified_msg)
        await adapter.send_message(unified_msg.user_id, unified_msg.conversation_id, response_text)
    return {"status": "ok"}


# ------------------------------------------------------------------
# WhatsApp Cloud API Webhook Endpoints
# ------------------------------------------------------------------
@app.get("/webhooks/whatsapp")
async def whatsapp_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verification successful.")
        return PlainTextResponse(content=hub_challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Verification token mismatch")


@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    payload = await request.json()
    adapter = PlatformAdapterFactory.get_adapter("whatsapp")
    unified_msg = await adapter.handle_event(payload)
    if unified_msg:
        response_text = await session_manager.handle_message(unified_msg)
        await adapter.send_message(unified_msg.user_id, unified_msg.conversation_id, response_text)
    return {"status": "ok"}


# ------------------------------------------------------------------
# Slack Webhook Endpoint
# ------------------------------------------------------------------
@app.post("/webhooks/slack")
async def slack_webhook(request: Request):
    payload = await request.json()
    # Handle Slack URL verification challenge
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    adapter = PlatformAdapterFactory.get_adapter("slack")
    unified_msg = await adapter.handle_event(payload)
    if unified_msg:
        response_text = await session_manager.handle_message(unified_msg)
        await adapter.send_message(unified_msg.user_id, unified_msg.conversation_id, response_text)
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
