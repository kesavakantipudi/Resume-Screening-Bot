import json
import datetime
from typing import List, Optional, Any
from sqlalchemy import Column, String, DateTime, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
from app.db.database import Base


class ExperienceItem(BaseModel):
    title: str = Field(default="Position")
    company: str = Field(default="Company")
    duration_years: float = Field(default=0.0)
    description: str = Field(default="")


class EducationItem(BaseModel):
    degree: str = Field(default="")
    institution: str = Field(default="")
    year: Optional[str] = Field(default="")


class CandidateData(BaseModel):
    candidate_name: str = Field(default="Unknown Candidate", description="Full name of candidate")
    email: Optional[str] = Field(default="NOT_FOUND")
    phone: Optional[str] = Field(default="NOT_FOUND")
    location: Optional[str] = Field(default="NOT_FOUND")
    education: List[EducationItem] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    total_experience_years: float = Field(default=0.0)
    skills: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    job_titles: List[str] = Field(default_factory=list)
    companies: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)


class CandidateDB(Base):
    __tablename__ = "candidates"

    id = Column(String(64), primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("sessions.id"), nullable=False, index=True)
    filename = Column(String(256), nullable=False)
    name = Column(String(256), nullable=False, default="Candidate")
    raw_text = Column(Text, nullable=False)
    structured_data_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("RecruitmentSession", back_populates="candidates")
    analysis = relationship("CandidateAnalysisDB", back_populates="candidate", uselist=False, cascade="all, delete-orphan")

    @property
    def structured_data(self) -> CandidateData:
        try:
            data = json.loads(self.structured_data_json)
            return CandidateData(**data)
        except Exception:
            return CandidateData()
