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


import asyncio
import httpx

async def _telegram_polling_loop():
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or token.startswith("mock_"):
        logger.info("Telegram Poller disabled (no valid bot token configured).")
        return

    adapter = PlatformAdapterFactory.get_adapter("telegram")
    api_url = f"https://api.telegram.org/bot{token}"
    logger.info("Starting Telegram Bot API Poller...")

    # Delete any existing webhook so getUpdates works cleanly
    try:
        async with httpx.AsyncClient() as client:
            await client.get(f"{api_url}/deleteWebhook?drop_pending_updates=false")
    except Exception as e:
        logger.warning(f"Failed to delete Telegram webhook: {e}")

    offset = 0
    while True:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{api_url}/getUpdates",
                    params={"offset": offset, "timeout": 10},
                    timeout=15.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        unified_msg = await adapter.handle_event(update)
                        if unified_msg:
                            response_text = await session_manager.handle_message(unified_msg)
                            await adapter.send_message(unified_msg.user_id, unified_msg.conversation_id, response_text)
        except asyncio.CancelledError:
            logger.info("Telegram Poller task cancelled.")
            break
        except Exception as e:
            logger.error(f"Telegram polling error: {e}")
            await asyncio.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing HireLens AI Database...")
    init_db()
    poller_task = asyncio.create_task(_telegram_polling_loop())
    logger.info(f"HireLens AI Bot Ready! Configured Model: {settings.GEMINI_MODEL}")
    yield
    poller_task.cancel()
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
