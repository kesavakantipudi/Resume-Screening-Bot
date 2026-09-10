import logging
from typing import Type, TypeVar, Optional
from pydantic import BaseModel
from app.ai.base import BaseAIProvider
from app.ai.gemini import GeminiProvider
from app.ai.groq_provider import GroqProvider

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class FallbackAIProvider(BaseAIProvider):
    """
    Composite AI provider that routes requests to Google Gemini primary provider,
    and automatically falls back to Groq API if Gemini encounters recoverable errors
    (rate limits, quota exhaustion, 429, timeouts, 503 service unavailable, etc.).
    """

    def __init__(
        self,
        gemini_provider: Optional[GeminiProvider] = None,
        groq_provider: Optional[GroqProvider] = None
    ):
        self.gemini_provider = gemini_provider or GeminiProvider()
        self.groq_provider = groq_provider or GroqProvider()
        self.last_used_provider: str = "gemini"
        self.last_used_model: str = self.gemini_provider.primary_model

    async def generate_text(self, prompt: str) -> str:
        try:
            logger.info("[LLM] Dispatching request to primary provider: Gemini")
            res = await self.gemini_provider.generate_text(prompt)
            self.last_used_provider = "gemini"
            self.last_used_model = getattr(self.gemini_provider, "last_used_model", self.gemini_provider.primary_model)
            return res
        except Exception as gemini_err:
            logger.warning(
                f"[LLM Fallback Triggered] Gemini primary provider failed: {type(gemini_err).__name__}: {str(gemini_err)}. "
                f"Falling back to Groq API..."
            )

            try:
                logger.info("[LLM] Dispatching fallback request to secondary provider: Groq")
                res = await self.groq_provider.generate_text(prompt)
                self.last_used_provider = "groq"
                self.last_used_model = getattr(self.groq_provider, "last_used_model", self.groq_provider.model_name)
                return res
            except Exception as groq_err:
                logger.error(
                    f"[LLM Fallback Failed] Groq fallback provider also failed: {type(groq_err).__name__}: {str(groq_err)}."
                )
                raise RuntimeError(f"All LLM providers (Gemini & Groq) failed: Gemini ({gemini_err}), Groq ({groq_err})") from groq_err

    async def generate_json(self, prompt: str, schema_cls: Type[T]) -> T:
        try:
            logger.info(f"[LLM] Requesting structured JSON ({schema_cls.__name__}) from primary provider: Gemini")
            res = await self.gemini_provider.generate_json(prompt, schema_cls)
            self.last_used_provider = "gemini"
            self.last_used_model = getattr(self.gemini_provider, "last_used_model", self.gemini_provider.primary_model)
            return res
        except Exception as gemini_err:
            logger.warning(
                f"[LLM Fallback Triggered] Gemini provider failed for {schema_cls.__name__}: "
                f"{type(gemini_err).__name__}: {str(gemini_err)}. Initiating automatic fallback to Groq API..."
            )

            try:
                logger.info(f"[LLM] Requesting structured JSON ({schema_cls.__name__}) from fallback provider: Groq")
                res = await self.groq_provider.generate_json(prompt, schema_cls)
                self.last_used_provider = "groq"
                self.last_used_model = getattr(self.groq_provider, "last_used_model", self.groq_provider.model_name)
                return res
            except Exception as groq_err:
                logger.error(
                    f"[LLM Fallback Failed] Groq fallback provider failed for {schema_cls.__name__}: "
                    f"{type(groq_err).__name__}: {str(groq_err)}."
                )
                raise RuntimeError(
                    f"All LLM providers (Gemini & Groq) failed to generate {schema_cls.__name__}."
                ) from groq_err
