from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field


class UnifiedAttachment(BaseModel):
    filename: str
    file_id: str
    file_size: int = 0
    content_type: str = ""
    data_bytes: Optional[bytes] = None


class UnifiedMessage(BaseModel):
    platform: str = Field(description="telegram, discord, whatsapp, slack")
    user_id: str
    conversation_id: str
    message_id: str = ""
    text: str = ""
    attachments: List[UnifiedAttachment] = Field(default_factory=list)


class UnifiedResponse(BaseModel):
    recipient_id: str
    conversation_id: str
    text: str


class PlatformAdapter(ABC):
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Name identifier of the messaging platform."""
        pass

    @abstractmethod
    async def send_message(self, recipient_id: str, conversation_id: str, text: str) -> bool:
        """Send a outbound message to the recipient on this platform."""
        pass

    @abstractmethod
    async def download_file(self, file_id: str) -> bytes:
        """Download an attachment file by file_id."""
        pass

    @abstractmethod
    async def handle_event(self, raw_event: dict) -> Optional[UnifiedMessage]:
        """Convert a platform-specific incoming webhook/event payload into a UnifiedMessage."""
        pass
