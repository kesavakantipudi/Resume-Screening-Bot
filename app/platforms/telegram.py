import logging
import httpx
from typing import Optional
from app.platforms.base import PlatformAdapter, UnifiedMessage, UnifiedAttachment
from app.config.settings import settings

logger = logging.getLogger(__name__)


class TelegramAdapter(PlatformAdapter):
    def __init__(self, bot_token: str = ""):
        self.token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.api_url = f"https://api.telegram.org/bot{self.token}"

    @property
    def platform_name(self) -> str:
        return "telegram"

    async def send_message(self, recipient_id: str, conversation_id: str, text: str) -> bool:
        chat_id = conversation_id or recipient_id
        if not self.token:
            logger.warning(f"[Mock Telegram] Would send to {chat_id}:\n{text}")
            return True

        url = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=10.0)
                if resp.status_code != 200:
                    # Fallback without Markdown if markdown syntax caused parse error
                    payload.pop("parse_mode", None)
                    resp = await client.post(url, json=payload, timeout=10.0)
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send_message failed: {e}")
            return False

    async def download_file(self, file_id: str) -> bytes:
        if not self.token:
            raise ValueError("Telegram Bot Token is not configured.")

        async with httpx.AsyncClient() as client:
            # 1. Get file path
            resp = await client.get(f"{self.api_url}/getFile", params={"file_id": file_id})
            resp.raise_for_status()
            file_path = resp.json()["result"]["file_path"]

            # 2. Download raw content
            download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            file_resp = await client.get(download_url)
            file_resp.raise_for_status()
            return file_resp.content

    async def handle_event(self, raw_event: dict) -> Optional[UnifiedMessage]:
        message = raw_event.get("message") or raw_event.get("edited_message")
        if not message:
            return None

        user_id = str(message.get("from", {}).get("id", ""))
        chat_id = str(message.get("chat", {}).get("id", ""))
        msg_id = str(message.get("message_id", ""))
        text = message.get("text") or message.get("caption") or ""

        attachments = []
        document = message.get("document")
        if document:
            filename = document.get("file_name", "document.pdf")
            file_id = document.get("file_id", "")
            file_size = document.get("file_size", 0)
            mime_type = document.get("mime_type", "")
            attachments.append(
                UnifiedAttachment(
                    filename=filename,
                    file_id=file_id,
                    file_size=file_size,
                    content_type=mime_type
                )
            )

        return UnifiedMessage(
            platform=self.platform_name,
            user_id=user_id,
            conversation_id=chat_id,
            message_id=msg_id,
            text=text,
            attachments=attachments
        )
