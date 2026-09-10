from typing import Dict
from app.platforms.base import PlatformAdapter
from app.platforms.telegram import TelegramAdapter
from app.platforms.discord import DiscordAdapter
from app.platforms.whatsapp import WhatsAppAdapter
from app.platforms.slack import SlackAdapter


class PlatformAdapterFactory:
    _adapters: Dict[str, PlatformAdapter] = {}

    @classmethod
    def get_adapter(cls, platform_name: str) -> PlatformAdapter:
        name = platform_name.lower().strip()
        if name not in cls._adapters:
            if name == "telegram":
                cls._adapters[name] = TelegramAdapter()
            elif name == "discord":
                cls._adapters[name] = DiscordAdapter()
            elif name == "whatsapp":
                cls._adapters[name] = WhatsAppAdapter()
            elif name == "slack":
                cls._adapters[name] = SlackAdapter()
            else:
                raise ValueError(f"Unsupported platform '{platform_name}'. Supported: telegram, discord, whatsapp, slack.")
        return cls._adapters[name]
