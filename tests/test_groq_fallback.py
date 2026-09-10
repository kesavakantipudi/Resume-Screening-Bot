import pytest
import asyncio
from app.ai.gemini import GeminiProvider
from app.ai.groq_provider import GroqProvider
from app.ai.fallback_provider import FallbackAIProvider
from app.models.job import JobDescriptionData
from app.models.candidate import CandidateData


@pytest.mark.asyncio
async def test_gemini_succeeds_groq_not_called():
    """
    Scenario 1: Gemini succeeds on primary attempt.
    Groq MUST NOT be called.
    """
    gemini = GeminiProvider(api_key="mock_key", model_name="gemini-3.5-flash-lite")
    groq = GroqProvider(api_key="mock_key", model_name="llama-3.3-70b-versatile")

    gemini_calls = []
    groq_calls = []

    async def mock_gemini_call(model, *args):
        gemini_calls.append((model, args))
        return JobDescriptionData(job_title="Primary Gemini Title")

    async def mock_groq_call(model, prompt):
        groq_calls.append((model, prompt))
        return JobDescriptionData(job_title="Fallback Groq Title")

    gemini._test_call_hook = mock_gemini_call
    groq._test_call_hook = mock_groq_call

    fallback = FallbackAIProvider(gemini_provider=gemini, groq_provider=groq)
    res = await fallback.generate_json("Test prompt", JobDescriptionData)

    assert res.job_title == "Primary Gemini Title"
    assert fallback.last_used_provider == "gemini"
    assert len(gemini_calls) == 1
    assert len(groq_calls) == 0


@pytest.mark.asyncio
async def test_gemini_rate_limit_429_triggers_groq_fallback():
    """
    Scenario 2: Gemini encounters 429 quota error.
    Groq fallback is triggered and returns successful result.
    """
    gemini = GeminiProvider(api_key="mock_key", model_name="gemini-3.5-flash-lite")
    groq = GroqProvider(api_key="mock_key", model_name="llama-3.3-70b-versatile")

    groq_calls = []

    async def mock_gemini_call(model):
        raise Exception("429 ResourceExhausted: Quota exceeded for Gemini model")

    async def mock_groq_call(model, prompt):
        groq_calls.append((model, prompt))
        return JobDescriptionData(job_title="Groq Fallback Title")

    gemini._test_call_hook = mock_gemini_call
    groq._test_call_hook = mock_groq_call

    fallback = FallbackAIProvider(gemini_provider=gemini, groq_provider=groq)
    res = await fallback.generate_json("Same Prompt Text", JobDescriptionData)

    assert res.job_title == "Groq Fallback Title"
    assert fallback.last_used_provider == "groq"
    assert len(groq_calls) == 1
    assert groq_calls[0][1] == "Same Prompt Text"


@pytest.mark.asyncio
async def test_gemini_timeout_triggers_groq_fallback():
    """
    Scenario 3: Gemini times out or encounters a temporary server error (503).
    Groq fallback is triggered and returns successful result.
    """
    gemini = GeminiProvider(api_key="mock_key", model_name="gemini-3.5-flash-lite")
    groq = GroqProvider(api_key="mock_key", model_name="llama-3.3-70b-versatile")

    async def mock_gemini_call(model):
        raise TimeoutError("503 Service Unavailable: Request timed out")

    async def mock_groq_call(model, prompt):
        return CandidateData(candidate_name="Alice Smith (Groq)")

    gemini._test_call_hook = mock_gemini_call
    groq._test_call_hook = mock_groq_call

    fallback = FallbackAIProvider(gemini_provider=gemini, groq_provider=groq)
    res = await fallback.generate_json("Resume prompt", CandidateData)

    assert res.candidate_name == "Alice Smith (Groq)"
    assert fallback.last_used_provider == "groq"


@pytest.mark.asyncio
async def test_both_gemini_and_groq_fail():
    """
    Scenario 4: Both Gemini and Groq fail.
    Clean exception is raised to trigger user-friendly error message.
    """
    gemini = GeminiProvider(api_key="mock_key", model_name="gemini-3.5-flash-lite")
    groq = GroqProvider(api_key="mock_key", model_name="llama-3.3-70b-versatile")

    async def mock_gemini_call(model):
        raise Exception("429 Too Many Requests")

    async def mock_groq_call(model, prompt):
        raise Exception("500 Internal Server Error in Groq API")

    gemini._test_call_hook = mock_gemini_call
    groq._test_call_hook = mock_groq_call

    fallback = FallbackAIProvider(gemini_provider=gemini, groq_provider=groq)

    with pytest.raises(RuntimeError, match=r"All LLM providers \(Gemini & Groq\) failed"):
        await fallback.generate_json("Test prompt", JobDescriptionData)


@pytest.mark.asyncio
async def test_multiple_resumes_processed_independently():
    """
    Scenario 5: Multiple candidate resumes processed concurrently.
    Each request maintains independent state without shared-state corruption.
    """
    gemini = GeminiProvider(api_key="mock_key", model_name="gemini-3.5-flash-lite")
    groq = GroqProvider(api_key="mock_key", model_name="llama-3.3-70b-versatile")

    processed = []

    async def mock_gemini_call(model):
        raise Exception("429 Quota Exceeded")

    async def mock_groq_call(model, prompt):
        name = "Candidate 1" if "Cand1" in prompt else "Candidate 2"
        processed.append(name)
        return CandidateData(candidate_name=name)

    gemini._test_call_hook = mock_gemini_call
    groq._test_call_hook = mock_groq_call

    fallback = FallbackAIProvider(gemini_provider=gemini, groq_provider=groq)

    t1 = fallback.generate_json("RESUME TEXT: Cand1", CandidateData)
    t2 = fallback.generate_json("RESUME TEXT: Cand2", CandidateData)

    res1, res2 = await asyncio.gather(t1, t2)

    assert res1.candidate_name == "Candidate 1"
    assert res2.candidate_name == "Candidate 2"
    assert set(processed) == {"Candidate 1", "Candidate 2"}
