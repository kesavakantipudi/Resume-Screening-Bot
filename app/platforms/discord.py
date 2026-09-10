import logging
import httpx
from typing import Optional
from app.platforms.base import PlatformAdapter, UnifiedMessage, UnifiedAttachment
from app.config.settings import settings

logger = logging.getLogger(__name__)


class DiscordAdapter(PlatformAdapter):
    def __init__(self, bot_token: str = ""):
        self.token = bot_token or settings.DISCORD_BOT_TOKEN
        self.api_url = "https://discord.com/api/v10"

    @property
    def platform_name(self) -> str:
        return "discord"

    async def send_message(self, recipient_id: str, conversation_id: str, text: str) -> bool:
        channel_id = conversation_id or recipient_id
        if not self.token:
            logger.warning(f"[Mock Discord] Would send to channel {channel_id}:\n{text}")
            return True

        url = f"{self.api_url}/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json"
        }
        
        # Split message if exceeds Discord 2000 character limit
        chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]
        try:
            async with httpx.AsyncClient() as client:
                for chunk in chunks:
                    resp = await client.post(url, json={"content": chunk}, headers=headers, timeout=10.0)
                    resp.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Discord send_message failed: {e}")
            return False

    async def download_file(self, file_id: str) -> bytes:
        # file_id for Discord can be the direct attachment URL
        async with httpx.AsyncClient() as client:
            resp = await client.get(file_id, timeout=30.0)
            resp.raise_for_status()
            return resp.content

    async def handle_event(self, raw_event: dict) -> Optional[UnifiedMessage]:
        # Handles Discord message create event or webhook payload
        user = raw_event.get("author", {})
        user_id = str(user.get("id", ""))
        channel_id = str(raw_event.get("channel_id", ""))
        msg_id = str(raw_event.get("id", ""))
        content = raw_event.get("content", "")

        attachments = []
        for att in raw_event.get("attachments", []):
            filename = att.get("filename", "attachment.pdf")
            url = att.get("url", "")
            size = att.get("size", 0)
            content_type = att.get("content_type", "")
            attachments.append(
                UnifiedAttachment(
                    filename=filename,
                    file_id=url,  # Direct URL used as file_id for Discord
                    file_size=size,
                    content_type=content_type
                )
            )

        return UnifiedMessage(
            platform=self.platform_name,
            user_id=user_id,
            conversation_id=channel_id,
            message_id=msg_id,
            text=content,
            attachments=attachments
        )
