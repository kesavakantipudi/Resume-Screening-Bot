import logging
import httpx
from typing import Optional
from app.platforms.base import PlatformAdapter, UnifiedMessage, UnifiedAttachment
from app.config.settings import settings

logger = logging.getLogger(__name__)


class SlackAdapter(PlatformAdapter):
    def __init__(self, bot_token: str = ""):
        self.token = bot_token or settings.SLACK_BOT_TOKEN
        self.api_url = "https://slack.com/api"

    @property
    def platform_name(self) -> str:
        return "slack"

    async def send_message(self, recipient_id: str, conversation_id: str, text: str) -> bool:
        channel = conversation_id or recipient_id
        if not self.token:
            logger.warning(f"[Mock Slack] Would send to channel {channel}:\n{text}")
            return True

        url = f"{self.api_url}/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        payload = {
            "channel": channel,
            "text": text
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=10.0)
                resp.raise_for_status()
                data = resp.json()
                return data.get("ok", False)
        except Exception as e:
            logger.error(f"Slack send_message failed: {e}")
            return False

    async def download_file(self, file_id: str) -> bytes:
        # For Slack, file_id is private download URL or file object ID
        if not self.token:
            raise ValueError("Slack Bot Token is not configured.")

        headers = {"Authorization": f"Bearer {self.token}"}
        url = file_id if file_id.startswith("http") else f"{self.api_url}/files.info?file={file_id}"
        
        async with httpx.AsyncClient() as client:
            if not file_id.startswith("http"):
                info_resp = await client.get(url, headers=headers)
                info_resp.raise_for_status()
                url = info_resp.json()["file"]["url_private_download"]

            file_resp = await client.get(url, headers=headers)
            file_resp.raise_for_status()
            return file_resp.content

    async def handle_event(self, raw_event: dict) -> Optional[UnifiedMessage]:
        # Handle Slack Event API payload
        event = raw_event.get("event") or raw_event
        user_id = str(event.get("user", ""))
        channel_id = str(event.get("channel", ""))
        msg_id = str(event.get("ts", ""))
        text = str(event.get("text", ""))

        attachments = []
        for file_info in event.get("files", []):
            filename = file_info.get("name", "document.pdf")
            download_url = file_info.get("url_private_download", file_info.get("id", ""))
            size = file_info.get("size", 0)
            mimetype = file_info.get("mimetype", "")
            attachments.append(
                UnifiedAttachment(
                    filename=filename,
                    file_id=download_url,
                    file_size=size,
                    content_type=mimetype
                )
            )

        return UnifiedMessage(
            platform=self.platform_name,
            user_id=user_id,
            conversation_id=channel_id,
            message_id=msg_id,
            text=text,
            attachments=attachments
        )
