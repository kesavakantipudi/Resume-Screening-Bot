import json
import enum
import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, String, DateTime, Text, Float, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
from app.db.database import Base


class DecisionEnum(str, enum.Enum):
    STRONG_SHORTLIST = "STRONG_SHORTLIST"
    SHORTLIST = "SHORTLIST"
    REVIEW = "REVIEW"
    REJECT = "REJECT"


class ATSScoreBreakdown(BaseModel):
    required_skills: float = Field(default=0.0, ge=0.0, le=35.0, description="Max 35 points")
    experience: float = Field(default=0.0, ge=0.0, le=20.0, description="Max 20 points")
    responsibilities: float = Field(default=0.0, ge=0.0, le=15.0, description="Max 15 points")
    education: float = Field(default=0.0, ge=0.0, le=10.0, description="Max 10 points")
    preferred_skills: float = Field(default=0.0, ge=0.0, le=10.0, description="Max 10 points")
    projects: float = Field(default=0.0, ge=0.0, le=5.0, description="Max 5 points")
    certifications: float = Field(default=0.0, ge=0.0, le=5.0, description="Max 5 points")
    overall: float = Field(default=0.0, ge=0.0, le=100.0, description="Total score out of 100")


class EvidenceItem(BaseModel):
    item: str
    matched: bool
    evidence: str


class CandidateAnalysisResult(BaseModel):
    candidate_id: str = Field(default="")
    candidate_name: str = Field(default="Candidate")
    score: ATSScoreBreakdown = Field(default_factory=ATSScoreBreakdown)
    decision: DecisionEnum = Field(default=DecisionEnum.REVIEW)
    mandatory_failed: bool = Field(default=False)
    mandatory_failure_reason: Optional[str] = Field(default=None)
    overall_summary: str = Field(default="")
    matching_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    experience_analysis: str = Field(default="")
    education_analysis: str = Field(default="")
    responsibilities_match: str = Field(default="")
    relevant_projects: List[str] = Field(default_factory=list)
    certifications_analysis: str = Field(default="")
    strengths: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    potential_red_flags: List[str] = Field(default_factory=list)
    recruiter_recommendation: str = Field(default="")
    evidence_notes: List[EvidenceItem] = Field(default_factory=list)
    model_used: str = Field(default="gemini-3.8-flash", description="Gemini model used for analysis")


class CandidateAnalysisDB(Base):
    __tablename__ = "analyses"

    id = Column(String(64), primary_key=True, index=True)
    candidate_id = Column(String(64), ForeignKey("candidates.id"), nullable=False, unique=True, index=True)
    score = Column(Float, nullable=False, default=0.0)
    decision = Column(SQLEnum(DecisionEnum), default=DecisionEnum.REVIEW, nullable=False)
    mandatory_failed = Column(Boolean, default=False)
    mandatory_failure_reason = Column(Text, nullable=True)
    analysis_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    candidate = relationship("CandidateDB", back_populates="analysis")

    @property
    def result(self) -> CandidateAnalysisResult:
        try:
            data = json.loads(self.analysis_json)
            return CandidateAnalysisResult(**data)
        except Exception:
            return CandidateAnalysisResult()
