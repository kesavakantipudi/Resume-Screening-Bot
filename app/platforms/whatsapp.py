import logging
import httpx
from typing import Optional
from app.platforms.base import PlatformAdapter, UnifiedMessage, UnifiedAttachment
from app.config.settings import settings

logger = logging.getLogger(__name__)


class WhatsAppAdapter(PlatformAdapter):
    def __init__(self, access_token: str = "", phone_number_id: str = ""):
        self.token = access_token or settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
        self.api_url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"

    @property
    def platform_name(self) -> str:
        return "whatsapp"

    async def send_message(self, recipient_id: str, conversation_id: str, text: str) -> bool:
        to_phone = recipient_id or conversation_id
        if not self.token or not self.phone_number_id:
            logger.warning(f"[Mock WhatsApp] Would send to {to_phone}:\n{text}")
            return True

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        # WhatsApp limits text messages to 4096 chars
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        try:
            async with httpx.AsyncClient() as client:
                for chunk in chunks:
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": to_phone,
                        "type": "text",
                        "text": {"body": chunk}
                    }
                    resp = await client.post(self.api_url, json=payload, headers=headers, timeout=10.0)
                    resp.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"WhatsApp send_message failed: {e}")
            return False

    async def download_file(self, file_id: str) -> bytes:
        if not self.token:
            raise ValueError("WhatsApp Access Token is not configured.")

        headers = {"Authorization": f"Bearer {self.token}"}
        async with httpx.AsyncClient() as client:
            # 1. Get media URL
            media_url = f"https://graph.facebook.com/v18.0/{file_id}"
            resp = await client.get(media_url, headers=headers)
            resp.raise_for_status()
            download_url = resp.json()["url"]

            # 2. Download media bytes
            media_resp = await client.get(download_url, headers=headers)
            media_resp.raise_for_status()
            return media_resp.content

    async def handle_event(self, raw_event: dict) -> Optional[UnifiedMessage]:
        # Handle Meta WhatsApp Webhook payload format
        try:
            entry = raw_event.get("entry", [])[0]
            changes = entry.get("changes", [])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return None

            msg = messages[0]
            user_id = msg.get("from", "")
            msg_id = msg.get("id", "")
            msg_type = msg.get("type", "text")
            text = ""

            attachments = []
            if msg_type == "text":
                text = msg.get("text", {}).get("body", "")
            elif msg_type == "document":
                doc = msg.get("document", {})
                file_id = doc.get("id", "")
                filename = doc.get("filename", "resume.pdf")
                mime_type = doc.get("mime_type", "")
                text = msg.get("caption", "")
                attachments.append(
                    UnifiedAttachment(
                        filename=filename,
                        file_id=file_id,
                        file_size=0,
                        content_type=mime_type
                    )
                )

            return UnifiedMessage(
                platform=self.platform_name,
                user_id=user_id,
                conversation_id=user_id,  # Phone number is conversation_id in WhatsApp
                message_id=msg_id,
                text=text,
                attachments=attachments
            )
        except Exception as e:
            logger.error(f"Failed parsing WhatsApp webhook payload: {e}")
            return None
