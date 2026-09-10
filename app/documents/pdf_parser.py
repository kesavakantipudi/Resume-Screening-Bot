import pymupdf as fitz
import logging

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract raw text from a PDF file using PyMuPDF (fitz).
    """
    text_chunks = []
    try:
        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if text:
                text_chunks.append(text.strip())
        doc.close()
    except Exception as e:
        logger.error(f"Error extracting text from PDF file {file_path}: {e}")
        raise ValueError(f"Failed to parse PDF document: {str(e)}")

    full_text = "\n\n".join(text_chunks)
    if not full_text.strip():
        raise ValueError("PDF document contains no readable text (might be scanned/image-only).")
    
    return full_text
