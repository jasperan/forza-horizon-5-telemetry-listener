"""Optional Ollama-powered LLM coaching: generates natural language tips from batched alerts."""

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

SYSTEM_PROMPT = (
    "You are a racing engineer. Given these telemetry alerts and lap data, "
    "give ONE specific coaching tip in under 30 words. Be direct."
)


class LLMCoach:
    """Sends batched alerts to a local Ollama instance and returns a coaching tip."""

    def __init__(
        self,
        enabled: bool = False,
        model: str = "qwen3.5:35b-a3b",
        ollama_url: str = "http://localhost:11434",
    ) -> None:
        self.enabled = enabled
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")

    def _build_prompt(self, alerts: list[dict], lap_stats: dict) -> str:
        """Format alerts and lap stats into a text prompt for the LLM."""
        lines = ["Telemetry alerts:"]
        for alert in alerts:
            lines.append(f"- [{alert.get('rule', 'unknown')}] {alert.get('message', '')}")

        lines.append("")
        lines.append("Lap stats:")
        for key, value in lap_stats.items():
            lines.append(f"- {key}: {value}")

        return "\n".join(lines)

    def generate_tip(self, alerts: list[dict], lap_stats: dict) -> dict | None:
        """Generate a coaching tip from alerts and lap data via Ollama.

        Returns None when disabled, when there are no alerts, when httpx is
        unavailable, or on any network/parsing failure (graceful degradation).
        """
        if not self.enabled or not alerts:
            return None

        if httpx is None:
            return None

        prompt = self._build_prompt(alerts, lap_stats)

        try:
            response = httpx.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": SYSTEM_PROMPT,
                    "stream": False,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            message = data.get("response", "").strip()
            if not message:
                return None
            return {"type": "llm_tip", "message": message}
        except Exception:
            return None
