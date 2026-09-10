import os
import logging
from app.documents.pdf_parser import extract_text_from_pdf
from app.documents.docx_parser import extract_text_from_docx

logger = logging.getLogger(__name__)


def extract_text_from_file(file_path: str, original_filename: str = "") -> str:
    """
    Extract text content from a PDF, DOCX, or TXT file.
    """
    ext = os.path.splitext(original_filename or file_path)[1].lower()
    
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return extract_text_from_docx(file_path)
    elif ext == ".txt":
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip()
        except Exception as e:
            raise ValueError(f"Failed to read TXT document: {str(e)}")
    else:
        raise ValueError(f"Unsupported file format '{ext}'. Supported formats: PDF, DOCX, TXT.")
