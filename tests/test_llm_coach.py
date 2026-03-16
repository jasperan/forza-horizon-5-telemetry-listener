"""Tests for the optional Ollama LLM coaching module."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.coach.llm_coach import LLMCoach


SAMPLE_ALERTS = [
    {"rule": "tire_overheat", "message": "FL tire overheating (250F vs 180F avg)"},
    {"rule": "traction_loss", "message": "Rear traction loss detected"},
]

SAMPLE_LAP_STATS = {
    "lap_number": 3,
    "best_lap_time": 62.5,
    "last_lap_time": 64.1,
}


# ---------------------------------------------------------------------------
# Disabled by default
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_coach_disabled_by_default():
    coach = LLMCoach()
    assert coach.enabled is False
    result = await coach.generate_tip(SAMPLE_ALERTS, SAMPLE_LAP_STATS)
    assert result is None


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------

def test_llm_coach_formats_prompt():
    coach = LLMCoach(enabled=True)
    prompt = coach._build_prompt(SAMPLE_ALERTS, SAMPLE_LAP_STATS)

    # Alert messages should appear in the prompt
    assert "FL tire overheating" in prompt
    assert "Rear traction loss detected" in prompt
    assert "tire_overheat" in prompt
    assert "traction_loss" in prompt

    # Lap stats should appear in the prompt
    assert "lap_number" in prompt
    assert "62.5" in prompt
    assert "64.1" in prompt


# ---------------------------------------------------------------------------
# Successful Ollama call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("src.coach.llm_coach.httpx")
async def test_llm_coach_calls_ollama(mock_httpx):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": "Ease off the throttle earlier in Turn 3 to save your front-left tire."
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_httpx.AsyncClient.return_value = mock_client

    coach = LLMCoach(enabled=True, model="qwen3.5:35b-a3b", ollama_url="http://localhost:11434")
    result = await coach.generate_tip(SAMPLE_ALERTS, SAMPLE_LAP_STATS)

    assert result is not None
    assert result["type"] == "llm_tip"
    assert "throttle" in result["message"]

    # Verify the post was called with the correct URL
    call_args = mock_client.post.call_args
    assert "/api/generate" in call_args[0][0]
    assert call_args[1]["json"]["model"] == "qwen3.5:35b-a3b"
    assert call_args[1]["json"]["stream"] is False


# ---------------------------------------------------------------------------
# Graceful degradation on failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("src.coach.llm_coach.httpx")
async def test_llm_coach_handles_ollama_failure(mock_httpx):
    mock_client = AsyncMock()
    mock_client.post.side_effect = Exception("Connection refused")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_httpx.AsyncClient.return_value = mock_client

    coach = LLMCoach(enabled=True)
    result = await coach.generate_tip(SAMPLE_ALERTS, SAMPLE_LAP_STATS)

    assert result is None
