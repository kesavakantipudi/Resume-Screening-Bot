from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import get_db
from app.config.settings import settings

router = APIRouter()
health_router = router


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "ok",
        "app_name": "HireLens AI",
        "version": "1.0 MVP",
        "environment": settings.APP_ENV,
        "database": db_status,
        "ai_provider": "google-gemini",
        "gemini_model": settings.GEMINI_MODEL,
        "supported_platforms": ["telegram", "discord", "whatsapp", "slack"]
    }
