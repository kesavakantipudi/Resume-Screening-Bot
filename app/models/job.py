import json
import datetime
from typing import List, Optional
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
from app.db.database import Base


class JobDescriptionData(BaseModel):
    job_title: str = Field(default="Position", description="Title of the position")
    required_skills: List[str] = Field(default_factory=list, description="Mandatory required skills")
    preferred_skills: List[str] = Field(default_factory=list, description="Nice-to-have preferred skills")
    required_experience_years: float = Field(default=0.0, description="Minimum mandatory experience in years")
    education_requirements: List[str] = Field(default_factory=list, description="Required education levels/degrees")
    responsibilities: List[str] = Field(default_factory=list, description="Key duties and responsibilities")
    certifications: List[str] = Field(default_factory=list, description="Required or preferred certifications")
    domain_requirements: List[str] = Field(default_factory=list, description="Domain specific knowledge requirements")
    keywords: List[str] = Field(default_factory=list, description="Key technical/domain keywords")


class JobDescriptionDB(Base):
    __tablename__ = "jobs"

    id = Column(String(64), primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("sessions.id"), nullable=False, index=True)
    title = Column(String(256), nullable=False, default="Job Position")
    raw_text = Column(Text, nullable=False)
    structured_data_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("RecruitmentSession", back_populates="job_description")

    @property
    def structured_data(self) -> JobDescriptionData:
        try:
            data = json.loads(self.structured_data_json)
            return JobDescriptionData(**data)
        except Exception:
            return JobDescriptionData()
