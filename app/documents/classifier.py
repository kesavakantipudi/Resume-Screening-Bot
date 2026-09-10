import re
import logging
from typing import Literal

logger = logging.getLogger(__name__)

DocType = Literal["job_description", "resume", "uncertain"]


class DocumentClassifier:
    @staticmethod
    def classify(text: str, filename: str = "", caption: str = "") -> DocType:
        """
        Classify document content into 'job_description', 'resume', or 'uncertain'.
        """
        combined_meta = f"{filename} {caption}".lower()

        # 1. Check explicit override in caption/filename
        if "/jd" in combined_meta or "job_description" in combined_meta or "job description" in combined_meta or "/job" in combined_meta:
            return "job_description"
        if "/resume" in combined_meta or "resume" in combined_meta or "/cv" in combined_meta or "curriculum_vitae" in combined_meta:
            return "resume"

        # 2. Content Heuristics Scoring
        raw_text_lower = text.lower()

        jd_score = 0
        resume_score = 0

        jd_keywords = [
            "job description", "job title", "role overview", "key responsibilities",
            "what we are looking for", "minimum qualifications", "required skills",
            "preferred skills", "job requirements", "position summary", "about the role",
            "about the company", "mandatory requirements", "reporting to", "responsibilities:",
            "requirements:", "qualifications:"
        ]

        resume_keywords = [
            "curriculum vitae", "work experience", "employment history", "professional experience",
            "education", "academic background", "personal summary", "github.com",
            "linkedin.com", "references available", "objective:", "career summary",
            "projects:", "certifications:"
        ]

        for kw in jd_keywords:
            if kw in raw_text_lower:
                jd_score += 2

        for kw in resume_keywords:
            if kw in raw_text_lower:
                resume_score += 2

        # Check contact info patterns (strong indicators of a resume)
        has_email = bool(re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text))
        has_phone = bool(re.search(r"(\+\d{1,3}[-  ]?)?\(?\d{3}\)?[-  ]?\d{3}[-  ]?\d{4}", text))

        if has_email:
            resume_score += 3
        if has_phone:
            resume_score += 2

        logger.info(f"Document classification scores for '{filename}': JD score={jd_score}, Resume score={resume_score}")

        if jd_score > resume_score and jd_score >= 3:
            return "job_description"
        elif resume_score > jd_score and resume_score >= 3:
            return "resume"
        elif jd_score == 0 and resume_score == 0:
            return "uncertain"
        else:
            # If close tie, return uncertain to avoid misclassification
            if abs(jd_score - resume_score) <= 1:
                return "uncertain"
            return "job_description" if jd_score > resume_score else "resume"
