import pytest
import asyncio
from app.ai.gemini import GeminiProvider
from app.models.job import JobDescriptionData
from app.config.settings import settings


@pytest.mark.asyncio
async def test_primary_model_succeeds_no_fallback():
    provider = GeminiProvider(api_key="mock_key", model_name="gemini-2.5-flash")
    attempted_models = []

    async def mock_call(model_name: str):
        attempted_models.append(model_name)
        return JobDescriptionData(job_title="AI Engineer")

    provider._test_call_hook = mock_call

    res = await provider.generate_json("Test prompt", JobDescriptionData)
    assert res.job_title == "AI Engineer"
    assert provider.last_used_model == "gemini-2.5-flash"
    assert attempted_models == ["gemini-2.5-flash"]


@pytest.mark.asyncio
async def test_primary_hits_429_fallback_to_secondary():
    provider = GeminiProvider(api_key="mock_key", model_name="gemini-2.5-flash")
    attempted_models = []

    async def mock_call(model_name: str):
        attempted_models.append(model_name)
        if model_name == "gemini-2.5-flash":
            raise Exception("429 ResourceExhausted: Quota exceeded for gemini-2.5-flash")
        return JobDescriptionData(job_title="Backend Developer")

    provider._test_call_hook = mock_call

    res = await provider.generate_json("Test prompt", JobDescriptionData)
    assert res.job_title == "Backend Developer"
    assert provider.last_used_model == "gemini-2.5-flash-lite"
    assert "gemini-2.5-flash" in attempted_models
    assert "gemini-2.5-flash-lite" in attempted_models


@pytest.mark.asyncio
async def test_primary_and_fallback1_hit_quota_fallback_to_tertiary():
    provider = GeminiProvider(api_key="mock_key", model_name="gemini-2.5-flash")
    attempted_models = []

    async def mock_call(model_name: str):
        attempted_models.append(model_name)
        if model_name in ["gemini-2.5-flash", "gemini-2.5-flash-lite"]:
            raise Exception("Rate limit reached. Status code 429.")
        return JobDescriptionData(job_title="Data Scientist")

    provider._test_call_hook = mock_call

    res = await provider.generate_json("Test prompt", JobDescriptionData)
    assert res.job_title == "Data Scientist"
    assert provider.last_used_model == "gemini-1.5-flash"
    assert attempted_models.count("gemini-2.5-flash") == settings.GEMINI_MAX_RETRIES + 1
    assert attempted_models.count("gemini-2.5-flash-lite") == settings.GEMINI_MAX_RETRIES + 1
    assert "gemini-1.5-flash" in attempted_models


@pytest.mark.asyncio
async def test_all_models_fail_clean_error():
    provider = GeminiProvider(api_key="mock_key", model_name="gemini-2.5-flash")

    async def mock_call(model_name: str):
        raise Exception("429 Too Many Requests: Rate limit exceeded")

    provider._test_call_hook = mock_call

    with pytest.raises(RuntimeError, match="All Gemini models in fallback chain failed due to rate limits or quota exhaustion"):
        await provider.generate_json("Test prompt", JobDescriptionData)


@pytest.mark.asyncio
async def test_non_retryable_auth_error_no_fallback():
    provider = GeminiProvider(api_key="mock_key", model_name="gemini-2.5-flash")
    attempted_models = []

    async def mock_call(model_name: str):
        attempted_models.append(model_name)
        raise Exception("401 Unauthorized: Invalid API Key")

    provider._test_call_hook = mock_call

    with pytest.raises(Exception, match="401 Unauthorized"):
        await provider.generate_json("Test prompt", JobDescriptionData)

    # Must NOT attempt fallback models for authentication failures
    assert attempted_models == ["gemini-2.5-flash"]
