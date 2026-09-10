# HireLens AI — AI Resume Screening Bot

**HireLens AI** is a backend-only AI recruitment screening bot built with **FastAPI**, **Google Gemini API**, and **SQLAlchemy**. It allows recruiters to upload a **Job Description (JD)** and **multiple candidate resumes** through messaging platforms (**Telegram**, **Discord**, **WhatsApp**, **Slack**).

HireLens AI automatically parses documents (PDF, DOCX, TXT), extracts structured information via Gemini, calculates explainable ATS-style compatibility scores, enforces mandatory requirement overrides, ranks candidates, and returns professional recruiter-ready reports directly to the originating platform.

---

## Key Features

- **Multi-Platform Adapter Layer**: Platform-agnostic architecture supporting Telegram, Discord, WhatsApp Cloud API, and Slack.
- **Google Gemini API Powered**: Structured JSON extraction for JD requirements, candidate resumes, evidence-based matching, and qualitative recruiter evaluations.
- **Deterministic ATS Scoring**: Weighted formula (Required Skills 35%, Experience 20%, Responsibilities 15%, Education 10%, Preferred Skills 10%, Projects 5%, Certifications 5%).
- **Mandatory Requirement Override Engine**: Flags candidate experience gaps or missing critical required skills, downgrading hiring recommendations regardless of raw numerical scores.
- **Asynchronous Batch Candidate Processing**: Parallel document processing with concurrency controls using `asyncio.Semaphore`.
- **SQLite Persistence**: Local relational database tracking sessions, jobs, candidate resumes, and analysis results.

---

## Directory Structure

```text
hirelens-ai/
├── app/
│   ├── main.py                     # FastAPI application & webhook routers
│   ├── config/
│   │   └── settings.py             # Pydantic Settings & environment variables
│   ├── db/
│   │   └── database.py             # SQLAlchemy engine & session setup
│   ├── models/                     # Pydantic & SQLAlchemy data models
│   │   ├── session.py
│   │   ├── job.py
│   │   ├── candidate.py
│   │   └── analysis.py
│   ├── platforms/                  # Platform Adapter Layer
│   │   ├── base.py                 # Abstract PlatformAdapter & UnifiedMessage
│   │   ├── telegram.py
│   │   ├── discord.py
│   │   ├── whatsapp.py
│   │   ├── slack.py
│   │   └── factory.py              # Platform Adapter Factory
│   ├── ai/                         # AI Provider Layer
│   │   ├── base.py
│   │   └── gemini.py               # Google Gemini SDK & JSON mode
│   ├── documents/                  # Document Parsers & File Handlers
│   │   ├── pdf_parser.py           # PyMuPDF parser
│   │   ├── docx_parser.py          # python-docx parser
│   │   ├── downloader.py           # Temp file storage & size validator
│   │   └── extractor.py
│   ├── recruitment/                # Recruitment & Scoring Pipeline
│   │   ├── jd_analyzer.py
│   │   ├── resume_analyzer.py
│   │   ├── matcher.py
│   │   ├── scorer.py               # Deterministic ATS Scorer & Overrides
│   │   ├── ranker.py               # Candidate Ranker
│   │   └── report.py               # Markdown Report Generator
│   ├── sessions/
│   │   └── manager.py              # Session State Machine & Orchestration
│   ├── api/
│   │   └── health.py               # Health Check endpoint
│   └── prompts/                    # Modular AI Prompt Templates
│       ├── jd_extraction.txt
│       ├── resume_extraction.txt
│       ├── matching.txt
│       ├── evaluation.txt
│       └── ranking.txt
├── tests/                          # Test Suite (pytest)
│   ├── test_document_parsers.py
│   ├── test_scorer.py
│   └── test_session_manager.py
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── Dockerfile
```

---

## Quick Start

### 1. Installation

Clone the repository and install dependencies:

```bash
python -m venv venv
venv\Scripts\activate  # On Windows
pip install -r requirements.txt
```

### 2. Environment Setup

Copy `.env.example` to `.env` and fill in your credentials:

```env
GEMINI_API_KEY=your_google_gemini_api_key
GEMINI_MODEL=gemini-3.8-flash
GEMINI_FALLBACK_MODELS=gemini-3.5-flash,gemini-3.5-flash-lite
GEMINI_MAX_RETRIES=1
GEMINI_RETRY_DELAY=2

TELEGRAM_BOT_TOKEN=your_telegram_bot_token
DISCORD_BOT_TOKEN=your_discord_bot_token
WHATSAPP_ACCESS_TOKEN=your_whatsapp_access_token
SLACK_BOT_TOKEN=your_slack_bot_token
```

### 3. Run Application

Start the FastAPI application locally:

```bash
uvicorn app.main:app --reload --port 8000
```

Access API health check at: [http://localhost:8000/health](http://localhost:8000/health)

### 4. Running Tests

Run the test suite with pytest:

```bash
pytest -v
```

---

## Bot Interaction Flow

1. Send `/start` to start a new screening session.
2. Upload the Job Description file (PDF, DOCX, TXT) or paste as plain text message.
3. Upload candidate resumes (PDF, DOCX, TXT).
4. Send `ANALYZE` to trigger candidate scoring and ranking.
5. Send `DETAIL 1` or `DETAIL <Candidate Name>` for an individual deep-dive candidate report.
