from abc import ABC, abstractmethod
from typing import Dict, Any, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseAIProvider(ABC):
    @abstractmethod
    async def generate_json(self, prompt: str, schema_cls: Type[T]) -> T:
        """
        Send a prompt to the AI provider and receive a validated Pydantic model response.
        """
        pass

    @abstractmethod
    async def generate_text(self, prompt: str) -> str:
        """
        Send a prompt to the AI provider and receive a plain text response.
        """
        pass
