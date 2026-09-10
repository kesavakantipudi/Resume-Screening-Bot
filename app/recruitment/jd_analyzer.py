import os
import logging
from pathlib import Path
from app.models.job import JobDescriptionData
from app.ai.gemini import GeminiProvider

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "jd_extraction.txt"


class JobDescriptionAnalyzer:
    def __init__(self, ai_provider: GeminiProvider = None):
        self.ai_provider = ai_provider or GeminiProvider()
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            self.prompt_template = f.read()

    async def analyze(self, raw_text: str) -> JobDescriptionData:
        if not raw_text or not raw_text.strip():
            raise ValueError("Job description text cannot be empty.")

        prompt = self.prompt_template.replace("{job_description_text}", raw_text.strip())
        logger.info("Extracting structured Job Description with Gemini...")
        
        return await self.ai_provider.generate_json(prompt, JobDescriptionData)
