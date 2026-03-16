"""Tests for the optional Ollama LLM coaching module."""

from unittest.mock import patch, MagicMock

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

def test_llm_coach_disabled_by_default():
    coach = LLMCoach()
    assert coach.enabled is False
    result = coach.generate_tip(SAMPLE_ALERTS, SAMPLE_LAP_STATS)
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

@patch("src.coach.llm_coach.httpx")
def test_llm_coach_calls_ollama(mock_httpx):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": "Ease off the throttle earlier in Turn 3 to save your front-left tire."
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx.post.return_value = mock_response

    coach = LLMCoach(enabled=True, model="qwen3.5:35b-a3b", ollama_url="http://localhost:11434")
    result = coach.generate_tip(SAMPLE_ALERTS, SAMPLE_LAP_STATS)

    assert result is not None
    assert result["type"] == "llm_tip"
    assert "throttle" in result["message"]

    # Verify the post was called with the correct URL
    call_args = mock_httpx.post.call_args
    assert "/api/generate" in call_args[0][0]
    assert call_args[1]["json"]["model"] == "qwen3.5:35b-a3b"
    assert call_args[1]["json"]["stream"] is False


# ---------------------------------------------------------------------------
# Graceful degradation on failure
# ---------------------------------------------------------------------------

@patch("src.coach.llm_coach.httpx")
def test_llm_coach_handles_ollama_failure(mock_httpx):
    mock_httpx.post.side_effect = Exception("Connection refused")

    coach = LLMCoach(enabled=True)
    result = coach.generate_tip(SAMPLE_ALERTS, SAMPLE_LAP_STATS)

    assert result is None
