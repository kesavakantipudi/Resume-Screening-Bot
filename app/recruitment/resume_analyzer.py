import logging
from pathlib import Path
from app.models.candidate import CandidateData
from app.ai.gemini import GeminiProvider

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "resume_extraction.txt"


class ResumeAnalyzer:
    def __init__(self, ai_provider: GeminiProvider = None):
        self.ai_provider = ai_provider or GeminiProvider()
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            self.prompt_template = f.read()

    async def analyze(self, raw_text: str) -> CandidateData:
        if not raw_text or not raw_text.strip():
            raise ValueError("Resume text cannot be empty.")

        prompt = self.prompt_template.replace("{resume_text}", raw_text.strip())
        logger.info("Extracting structured candidate resume with Gemini...")

        return await self.ai_provider.generate_json(prompt, CandidateData)
