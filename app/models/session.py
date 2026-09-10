import enum
import datetime
from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from pydantic import BaseModel, ConfigDict
from app.db.database import Base


class SessionState(str, enum.Enum):
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    WAITING_FOR_JD = "WAITING_FOR_JD"
    COLLECTING_RESUMES = "COLLECTING_RESUMES"
    READY_FOR_ANALYSIS = "READY_FOR_ANALYSIS"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RecruitmentSession(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True, index=True)
    platform = Column(String(32), nullable=False, index=True)  # telegram, discord, whatsapp, slack
    user_id = Column(String(128), nullable=False, index=True)
    conversation_id = Column(String(128), nullable=False, index=True)
    status = Column(SQLEnum(SessionState), default=SessionState.WAITING_FOR_INPUT, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    job_description = relationship("JobDescriptionDB", back_populates="session", uselist=False, cascade="all, delete-orphan")
    candidates = relationship("CandidateDB", back_populates="session", cascade="all, delete-orphan")

    @property
    def jd_received(self) -> bool:
        return self.job_description is not None

    @property
    def resume_count(self) -> int:
        return len(self.candidates) if self.candidates else 0


class SessionSchema(BaseModel):
    id: str
    platform: str
    user_id: str
    conversation_id: str
    status: SessionState
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

