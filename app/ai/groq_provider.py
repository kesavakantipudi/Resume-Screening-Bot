import json
import logging
import asyncio
from typing import Type, TypeVar, Optional, Callable
from pydantic import BaseModel
from app.config.settings import settings
from app.ai.base import BaseAIProvider

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False


class GroqProvider(BaseAIProvider):
    def __init__(self, api_key: str = "", model_name: str = ""):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model_name = model_name or settings.GROQ_MODEL
        self.client = None
        self.last_used_model: str = self.model_name
        self._test_call_hook: Optional[Callable] = None

        if HAS_GROQ and self.api_key and not self.api_key.startswith("mock_"):
            try:
                self.client = Groq(api_key=self.api_key)
                logger.info(f"Initialized Groq Provider with model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Groq Client: {e}")

    async def generate_text(self, prompt: str) -> str:
        if self._test_call_hook:
            return await self._test_call_hook(self.model_name, prompt)

        if not self.client:
            logger.warning("Groq Client not initialized or running in mock mode.")
            return "Analysis completed via Groq fallback."

        loop = asyncio.get_running_loop()

        def _sync_call():
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content

        return await loop.run_in_executor(None, _sync_call)

    async def generate_json(self, prompt: str, schema_cls: Type[T]) -> T:
        if self._test_call_hook:
            res = await self._test_call_hook(self.model_name, prompt)
            if isinstance(res, schema_cls):
                return res
            cleaned_text = self._clean_json_markdown(str(res))
            return schema_cls(**json.loads(cleaned_text))

        if not self.client:
            logger.warning(f"[Groq] Using fallback mock generator for schema {schema_cls.__name__}")
            return self._mock_fallback(prompt, schema_cls)

        loop = asyncio.get_running_loop()

        def _sync_call():
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert recruitment screening AI. Return ONLY a valid JSON object matching the requested schema."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content

        raw_text = await loop.run_in_executor(None, _sync_call)
        cleaned_text = self._clean_json_markdown(raw_text)
        data = json.loads(cleaned_text)
        return schema_cls(**data)

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
        Fallback mock data generator when running without a live Groq API Key.
        """
        name = schema_cls.__name__
        if name == "JobDescriptionData":
            return schema_cls(
                job_title="Software Engineer",
                required_skills=["Python", "FastAPI", "SQL"],
                preferred_skills=["Docker", "AWS"],
                required_experience_years=2.0,
                education_requirements=["B.Tech"],
                responsibilities=["Backend Service Design"],
                certifications=[],
                domain_requirements=["Backend Development"],
                keywords=["Python", "FastAPI"]
            )
        elif name == "CandidateData":
            candidate_name = "Candidate (Groq Fallback)"
            if "RESUME TEXT:" in prompt:
                text_part = prompt.split("RESUME TEXT:")[1].strip()
                lines = [l.strip() for l in text_part.split("\n") if l.strip() and l.strip() != "---"]
                if lines:
                    candidate_name = lines[0]

            return schema_cls(
                candidate_name=candidate_name,
                email="candidate_groq@example.com",
                total_experience_years=3.0,
                skills=["Python", "FastAPI", "SQL"],
                projects=["Resume Screening Platform"],
                certifications=[],
                achievements=[],
                job_titles=["Backend Developer"],
                companies=["Tech Corp"],
                keywords=["Python", "FastAPI"]
            )
        elif name in ["EvidenceMatchingSchema", "EvidenceNotes", "MatchAnalysisSchema", "EvaluationSchema"]:
            return schema_cls()

        try:
            return schema_cls()
        except Exception:
            raise ValueError(f"Unable to generate Groq mock fallback for schema {schema_cls}")
