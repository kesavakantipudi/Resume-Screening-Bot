import pytest
from app.db.database import Base, engine, init_db
from app.platforms.base import UnifiedMessage, UnifiedAttachment
from app.sessions.manager import SessionManager


@pytest.mark.asyncio
async def test_session_manager_flow():
    Base.metadata.drop_all(bind=engine)
    init_db()
    manager = SessionManager()

    # 1. Send /start
    start_msg = UnifiedMessage(
        platform="telegram",
        user_id="user_123",
        conversation_id="chat_456",
        text="/start"
    )
    resp = await manager.handle_message(start_msg)
    assert "HireLens AI" in resp

    # 2. Upload Job Description text
    jd_msg = UnifiedMessage(
        platform="telegram",
        user_id="user_123",
        conversation_id="chat_456",
        text="Job Title: Python Engineer\nRequired Skills: Python, SQL, FastAPI\nExperience: 2+ years"
    )
    resp = await manager.handle_message(jd_msg)
    assert "Job Description received successfully" in resp

    # 3. Upload Candidate Resume
    resume_msg = UnifiedMessage(
        platform="telegram",
        user_id="user_123",
        conversation_id="chat_456",
        attachments=[
            UnifiedAttachment(
                filename="john_doe_resume.txt",
                file_id="txt_1",
                file_size=500,
                content_type="text/plain",
                data_bytes=b"John Doe\nPython & FastAPI Developer\n3.5 years experience at Tech Corp\nSkills: Python, FastAPI, SQL, Docker"
            )
        ]
    )
    resp = await manager.handle_message(resume_msg)
    assert "resumes received" in resp

    # 4. Trigger ANALYZE
    analyze_msg = UnifiedMessage(
        platform="telegram",
        user_id="user_123",
        conversation_id="chat_456",
        text="ANALYZE"
    )
    resp = await manager.handle_message(analyze_msg)
    assert "HIRING SCREENING REPORT" in resp
    assert "John Doe" in resp

    # 5. Detail view
    detail_msg = UnifiedMessage(
        platform="telegram",
        user_id="user_123",
        conversation_id="chat_456",
        text="DETAIL 1"
    )
    resp = await manager.handle_message(detail_msg)
    assert "CANDIDATE SCREENING REPORT" in resp
    assert "ATS Score:" in resp


@pytest.mark.asyncio
async def test_duplicate_resume_upload_deduplicated():
    Base.metadata.drop_all(bind=engine)
    init_db()
    manager = SessionManager()

    # 1. Upload candidate resume attachment
    resume_msg1 = UnifiedMessage(
        platform="telegram",
        user_id="user_dup",
        conversation_id="chat_dup",
        attachments=[
            UnifiedAttachment(
                filename="alice_resume.txt",
                file_id="a1",
                data_bytes=b"Alice Smith\nPython Developer\nExperience: 3 years"
            )
        ]
    )
    resp1 = await manager.handle_message(resume_msg1)
    assert "resumes received" in resp1

    # 2. Upload identical resume attachment again
    resp2 = await manager.handle_message(resume_msg1)
    assert "Updated 1 existing candidate resume" in resp2
