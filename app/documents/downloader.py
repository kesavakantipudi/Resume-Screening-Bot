import os
import uuid
import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def validate_file(filename: str, file_size_bytes: int) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file format '{ext}'. Allowed formats: PDF, DOCX, TXT.")
    
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise ValueError(f"File size exceeds limit of {settings.MAX_FILE_SIZE_MB}MB.")
    
    return ext


def save_temp_file(file_bytes: bytes, filename: str) -> str:
    ext = validate_file(filename, len(file_bytes))
    os.makedirs(settings.TEMP_FILE_DIR, exist_ok=True)
    
    safe_id = uuid.uuid4().hex
    temp_path = os.path.join(settings.TEMP_FILE_DIR, f"{safe_id}{ext}")
    
    with open(temp_path, "wb") as f:
        f.write(file_bytes)
        
    return temp_path


def cleanup_file(file_path: str) -> None:
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup temp file {file_path}: {e}")
