import pytest
from app.db.database import Base, engine, init_db
from app.platforms.base import UnifiedMessage, UnifiedAttachment
from app.sessions.manager import SessionManager


@pytest.mark.asyncio
async def test_resumes_provided_before_jd_flow():
    Base.metadata.drop_all(bind=engine)
    init_db()
    manager = SessionManager()

    # 1. Start session
    await manager.handle_message(
        UnifiedMessage(platform="telegram", user_id="u1", conversation_id="c1", text="/start")
    )

    # 2. Upload 2 candidate resumes BEFORE JD
    resume_msg1 = UnifiedMessage(
        platform="telegram",
        user_id="u1",
        conversation_id="c1",
        attachments=[
            UnifiedAttachment(
                filename="alice_resume.txt",
                file_id="1",
                data_bytes=b"Alice Smith\nWork Experience: 3 years Python developer\nEducation: BS CS\nemail: alice@example.com"
            ),
            UnifiedAttachment(
                filename="bob_resume.txt",
                file_id="2",
                data_bytes=b"Bob Jones\nWork Experience: 4 years FastAPI engineer\nEducation: MS CS\nemail: bob@example.com"
            )
        ]
    )
    resp1 = await manager.handle_message(resume_msg1)
    assert "I received 2 resumes, but I don't have a Job Description yet" in resp1

    # 3. Attempt ANALYZE before uploading JD
    analyze_msg = UnifiedMessage(platform="telegram", user_id="u1", conversation_id="c1", text="ANALYZE")
    resp_analyze_fail = await manager.handle_message(analyze_msg)
    assert "I don't have a Job Description for this screening session yet" in resp_analyze_fail

    # 4. Upload Job Description
    jd_msg = UnifiedMessage(
        platform="telegram",
        user_id="u1",
        conversation_id="c1",
        attachments=[
            UnifiedAttachment(
                filename="senior_python_jd.txt",
                file_id="3",
                data_bytes=b"Job Description: Senior Python Engineer\nKey Responsibilities: Design backend services\nRequired Skills: Python, FastAPI, SQL\nMinimum Qualifications: 2+ years experience"
            )
        ]
    )
    resp2 = await manager.handle_message(jd_msg)
    assert "Job Description received successfully" in resp2
    assert "You have 2 resumes ready for analysis" in resp2

    # 5. Trigger ANALYZE now that both JD and Resumes exist
    resp_analyze_success = await manager.handle_message(analyze_msg)
    assert "HIRING SCREENING REPORT" in resp_analyze_success


@pytest.mark.asyncio
async def test_analyze_validation_empty_session():
    Base.metadata.drop_all(bind=engine)
    init_db()
    manager = SessionManager()

    analyze_msg = UnifiedMessage(platform="telegram", user_id="u2", conversation_id="c2", text="ANALYZE")
    resp = await manager.handle_message(analyze_msg)
    assert "Please provide a Job Description and at least one candidate resume before starting the analysis." in resp


@pytest.mark.asyncio
async def test_analyze_validation_jd_only():
    Base.metadata.drop_all(bind=engine)
    init_db()
    manager = SessionManager()

    jd_msg = UnifiedMessage(
        platform="telegram",
        user_id="u3",
        conversation_id="c3",
        text="Job Description: Backend Lead\nRequired Skills: Python, SQL\nResponsibilities: Lead technical architecture"
    )
    await manager.handle_message(jd_msg)

    analyze_msg = UnifiedMessage(platform="telegram", user_id="u3", conversation_id="c3", text="ANALYZE")
    resp = await manager.handle_message(analyze_msg)
    assert "Please upload at least one candidate resume before starting the analysis." in resp
