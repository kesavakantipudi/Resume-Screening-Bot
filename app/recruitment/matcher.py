import json
import logging
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field
from app.models.job import JobDescriptionData
from app.models.candidate import CandidateData
from app.models.analysis import EvidenceItem
from app.ai.base import BaseAIProvider
from app.ai.fallback_provider import FallbackAIProvider

logger = logging.getLogger(__name__)

MATCHING_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "matching.txt"
EVALUATION_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "evaluation.txt"


class MatchAnalysisSchema(BaseModel):
    matching_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    experience_analysis: str = Field(default="")
    education_analysis: str = Field(default="")
    responsibilities_match: str = Field(default="")
    relevant_projects: List[str] = Field(default_factory=list)
    certifications_analysis: str = Field(default="")
    evidence_notes: List[EvidenceItem] = Field(default_factory=list)


class EvaluationSchema(BaseModel):
    overall_summary: str = Field(default="")
    strengths: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    potential_red_flags: List[str] = Field(default_factory=list)
    recruiter_recommendation: str = Field(default="")


class CandidateMatcher:
    def __init__(self, ai_provider: BaseAIProvider = None):
        self.ai_provider = ai_provider or FallbackAIProvider()
        with open(MATCHING_PROMPT_PATH, "r", encoding="utf-8") as f:
            self.matching_template = f.read()
        with open(EVALUATION_PROMPT_PATH, "r", encoding="utf-8") as f:
            self.eval_template = f.read()

    async def match_and_evaluate(
        self, job_data: JobDescriptionData, candidate_data: CandidateData
    ) -> tuple[MatchAnalysisSchema, EvaluationSchema]:
        job_json = json.dumps(job_data.model_dump(), indent=2)
        cand_json = json.dumps(candidate_data.model_dump(), indent=2)

        match_prompt = self.matching_template.replace(
            "{job_json}", job_json
        ).replace(
            "{candidate_json}", cand_json
        )
        logger.info(f"Running candidate matching analysis for {candidate_data.candidate_name}...")
        
        # 1. Run Matching Analysis
        match_result = await self.ai_provider.generate_json(match_prompt, MatchAnalysisSchema)

        # Fallback keyword matching if Gemini returned empty lists in mock mode
        if not match_result.matching_skills and job_data.required_skills:
            cand_skills_lower = [s.lower() for s in candidate_data.skills]
            matched = []
            missing = []
            for req in job_data.required_skills:
                if any(req.lower() in s or s in req.lower() for s in cand_skills_lower):
                    matched.append(req)
                else:
                    missing.append(req)
            match_result.matching_skills = matched
            match_result.missing_skills = missing

        # 2. Run Recruiter Evaluation Analysis
        eval_prompt = self.eval_template.replace(
            "{matching_json}", json.dumps(match_result.model_dump(), indent=2)
        ).replace(
            "{job_title}", job_data.job_title
        ).replace(
            "{candidate_name}", candidate_data.candidate_name
        )
        logger.info(f"Running recruiter evaluation prompt for {candidate_data.candidate_name}...")
        eval_result = await self.ai_provider.generate_json(eval_prompt, EvaluationSchema)

        return match_result, eval_result
