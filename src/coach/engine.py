"""CoachEngine: runs heuristic rules against telemetry packets and manages alert cooldowns."""

from src.coach.rules import ALL_RULES

# Minimum milliseconds between repeated alerts of the same rule.
COOLDOWN_MS = 10_000


class CoachEngine:
    """Evaluates telemetry packets against coaching rules with per-rule cooldown."""

    def __init__(self) -> None:
        self.state: dict = {}
        self._last_alert_time: dict[str, int] = {}

    def evaluate(self, packet: dict, session_mgr) -> list[dict]:
        """Run all rules against *packet* and return alerts that pass cooldown.

        Returns an empty list when no session is active.
        """
        if session_mgr.current_session is None:
            return []

        timestamp = packet.get("timestamp_ms", 0)
        alerts: list[dict] = []

        for rule_fn in ALL_RULES:
            alert = rule_fn(packet, self.state)
            if alert is None:
                continue

            rule_name = alert["rule"]
            last_time = self._last_alert_time.get(rule_name)

            if last_time is None or (timestamp - last_time) >= COOLDOWN_MS:
                self._last_alert_time[rule_name] = timestamp
                alerts.append(alert)

        return alerts
