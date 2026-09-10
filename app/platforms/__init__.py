from app.platforms.base import PlatformAdapter, UnifiedMessage, UnifiedAttachment, UnifiedResponse
from app.platforms.telegram import TelegramAdapter
from app.platforms.discord import DiscordAdapter
from app.platforms.whatsapp import WhatsAppAdapter
from app.platforms.slack import SlackAdapter
from app.platforms.factory import PlatformAdapterFactory

__all__ = [
    "PlatformAdapter",
    "UnifiedMessage",
    "UnifiedAttachment",
    "UnifiedResponse",
    "TelegramAdapter",
    "DiscordAdapter",
    "WhatsAppAdapter",
    "SlackAdapter",
    "PlatformAdapterFactory",
]
