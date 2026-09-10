import json
import logging
import asyncio
from typing import Type, TypeVar, Optional, Callable, List, Any
from pydantic import BaseModel
from app.config.settings import settings
from app.ai.base import BaseAIProvider

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


class GeminiProvider(BaseAIProvider):
    def __init__(self, api_key: str = "", model_name: str = ""):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.primary_model = model_name or settings.GEMINI_MODEL
        self.client = None
        self.last_used_model: str = self.primary_model
        
        # Override mock call hook for unit testing model fallbacks
        self._test_call_hook: Optional[Callable] = None

        if HAS_GENAI and self.api_key and not self.api_key.startswith("mock_"):
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"Initialized Gemini Provider with primary model: {self.primary_model}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Client: {e}")

    @property
    def model_chain(self) -> List[str]:
        chain = [self.primary_model]
        for m in settings.gemini_model_chain:
            if m not in chain:
                chain.append(m)
        return chain

    def _is_rate_limit_or_quota_error(self, exc: Exception) -> bool:
        """
        Identify if an exception is caused by rate-limiting, quota exhaustion, or 429 status code.
        Do NOT classify auth, invalid request, or schema errors as rate limit errors.
        """
        error_type = exc.__class__.__name__.lower()
        error_msg = str(exc).lower()

        # Auth or bad request errors should never trigger rate limit fallback
        if any(term in error_msg for term in ["401", "403", "unauthorized", "invalid api key", "invalid_api_key", "permissiondenied"]):
            return False
        if any(term in error_msg for term in ["400", "invalid argument", "bad request", "jsondecodeerror", "validationerror"]):
            return False

        # Quota/Rate limit/Temporary capacity markers
        quota_markers = [
            "429",
            "503",
            "rate limit",
            "ratelimit",
            "quota",
            "resourceexhausted",
            "resource_exhausted",
            "too many requests",
            "overloaded",
            "capacity",
            "exhausted",
            "unavailable",
            "high demand",
            "servererror",
            "temporarily"
        ]
        return any(marker in error_type or marker in error_msg for marker in quota_markers)

    async def _execute_with_fallback(self, call_fn: Callable[[str], asyncio.Future]) -> Any:
        """
        Centralized Gemini execution loop enforcing model chain fallback and retries.
        """
        models = self.model_chain
        last_error = None

        for model_idx, model in enumerate(models):
            max_retries = settings.GEMINI_MAX_RETRIES
            retry_delay = settings.GEMINI_RETRY_DELAY

            for attempt in range(max_retries + 1):
                logger.info(f"[Gemini] Trying model: {model}")
                try:
                    if self._test_call_hook:
                        result = await self._test_call_hook(model)
                    else:
                        result = await call_fn(model)

                    self.last_used_model = model
                    logger.info(f"[Gemini] Request completed using {model}")
                    return result

                except Exception as e:
                    last_error = e
                    if self._is_rate_limit_or_quota_error(e):
                        logger.warning(f"[Gemini] Rate limit/quota reached on {model}: {str(e)}")
                        if attempt < max_retries:
                            logger.info(f"[Gemini] Retrying {model} after {retry_delay}s backoff...")
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            if model_idx < len(models) - 1:
                                next_model = models[model_idx + 1]
                                logger.warning(f"[Gemini] Falling back to {next_model}")
                                break  # Break inner attempt loop to proceed to next model in outer loop
                            else:
                                logger.error("[Gemini] All models in fallback chain failed due to rate/quota limits.")
                                raise RuntimeError("All Gemini models in fallback chain failed due to rate limits or quota exhaustion.") from e
                    else:
                        logger.error(f"[Gemini] Non-retryable error encountered on {model}: {str(e)}")
                        raise e

        if last_error:
            raise last_error

    async def generate_text(self, prompt: str) -> str:
        if not self.client and not self._test_call_hook:
            logger.warning("Gemini Client not initialized or running in mock mode.")
            self.last_used_model = self.model_chain[0]
            return "Analysis completed successfully."

        async def _call(model_name: str) -> str:
            loop = asyncio.get_running_loop()
            def _sync_call():
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                return response.text
            return await loop.run_in_executor(None, _sync_call)

        return await self._execute_with_fallback(_call)

    async def generate_json(self, prompt: str, schema_cls: Type[T]) -> T:
        if not self.client and not self._test_call_hook:
            logger.warning(f"Using fallback heuristic generator for schema {schema_cls.__name__}")
            self.last_used_model = self.model_chain[0]
            return self._mock_fallback(prompt, schema_cls)

        async def _call(model_name: str) -> T:
            loop = asyncio.get_running_loop()
            def _sync_call():
                config = types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
                return response.text

            raw_text = await loop.run_in_executor(None, _sync_call)
            cleaned_text = self._clean_json_markdown(raw_text)
            data = json.loads(cleaned_text)
            return schema_cls(**data)

        return await self._execute_with_fallback(_call)

    def _clean_json_markdown(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _mock_fallback(self, prompt: str, schema_cls: Type[T]) -> T:
        """
        Fallback mock data generator for testing environments without live Gemini API keys.
        """
        name = schema_cls.__name__
        if name == "JobDescriptionData":
            return schema_cls(
                job_title="Software Engineer",
                required_skills=["Python", "FastAPI", "SQL", "Machine Learning"],
                preferred_skills=["AWS", "Docker", "LLM", "Kubernetes"],
                required_experience_years=2.0,
                education_requirements=["B.Tech", "Computer Science"],
                responsibilities=["Design backend services", "Build ML screening models"],
                certifications=["AWS Certified Developer"],
                domain_requirements=["Backend Development", "AI/ML"],
                keywords=["Python", "FastAPI", "ML", "SQL"]
            )
        elif name == "CandidateData":
            candidate_name = "John Doe"
            if "RESUME TEXT:" in prompt:
                text_part = prompt.split("RESUME TEXT:")[1].strip()
                lines = [l.strip() for l in text_part.split("\n") if l.strip() and l.strip() != "---"]
                if lines:
                    candidate_name = lines[0]

            return schema_cls(
                candidate_name=candidate_name,
                email="candidate@example.com",
                phone="+1-555-0199",
                location="San Francisco, CA",
                total_experience_years=3.5,
                skills=["Python", "FastAPI", "SQL", "Machine Learning", "Docker"],
                projects=["Built AI Resume Parser API", "Created SQL Query Optimizer"],
                certifications=["AWS Certified Cloud Practitioner"],
                achievements=["Improved API throughput by 40%"],
                job_titles=["Software Engineer", "Backend Developer"],
                companies=["Tech Corp", "Data AI Inc"],
                keywords=["Python", "FastAPI", "Docker", "SQL"]
            )
        elif name in ["EvidenceMatchingSchema", "EvidenceNotes", "MatchAnalysisSchema", "EvaluationSchema"]:
            return schema_cls()
        
        try:
            return schema_cls()
        except Exception:
            raise ValueError(f"Unable to generate fallback mock for schema {schema_cls}")
