"""Tests for the AI coach heuristic rule engine."""

import pytest
from src.session_manager import SessionManager
from src.coach.engine import CoachEngine


def _base_packet(**overrides) -> dict:
    """Build a minimal telemetry packet with sensible defaults."""
    pkt = {
        "is_race_on": 1,
        "timestamp_ms": 1000,
        "tire_temp_FL": 180.0,
        "tire_temp_FR": 180.0,
        "tire_temp_RL": 180.0,
        "tire_temp_RR": 180.0,
        "tire_combined_slip_FL": 0.3,
        "tire_combined_slip_FR": 0.3,
        "tire_combined_slip_RL": 0.3,
        "tire_combined_slip_RR": 0.3,
        "current_engine_rpm": 6000.0,
        "engine_max_rpm": 8000.0,
        "speed": 45.0,
        "accel": 200,
        "brake": 0,
        "norm_suspension_travel_FL": 0.5,
        "norm_suspension_travel_FR": 0.5,
        "norm_suspension_travel_RL": 0.5,
        "norm_suspension_travel_RR": 0.5,
    }
    pkt.update(overrides)
    return pkt


def _start_session(mgr: SessionManager) -> None:
    """Push one race-on packet so the session manager has an active session."""
    mgr.update(
        is_race_on=1,
        lap_number=1,
        timestamp_ms=1000,
        car_ordinal=42,
        car_class=5,
        car_performance_index=800,
        drivetrain_type=2,
        distance_traveled=0.0,
        position_x=0.0,
        position_y=0.0,
        position_z=0.0,
    )


# ---------------------------------------------------------------------------
# Tire overheat
# ---------------------------------------------------------------------------

def test_tire_overheat_alert():
    mgr = SessionManager()
    _start_session(mgr)
    engine = CoachEngine()

    all_alerts = []
    # First, establish a baseline with normal temps across all tires
    for i in range(5):
        pkt = _base_packet(
            timestamp_ms=1000 + i * 16,
            tire_temp_FL=180.0,
            tire_temp_FR=180.0,
            tire_temp_RL=180.0,
            tire_temp_RR=180.0,
        )
        alerts = engine.evaluate(pkt, mgr)
        all_alerts.extend(alerts)

    # Now spike FL to 250 (well above 105% of ~180 average) for 10 packets
    for i in range(10):
        pkt = _base_packet(
            timestamp_ms=1080 + i * 16,
            tire_temp_FL=250.0,  # significantly hotter than running avg
            tire_temp_FR=180.0,
            tire_temp_RL=180.0,
            tire_temp_RR=180.0,
        )
        alerts = engine.evaluate(pkt, mgr)
        all_alerts.extend(alerts)

    overheat_alerts = [a for a in all_alerts if a["rule"] == "tire_overheat"]
    assert len(overheat_alerts) >= 1
    assert "FL" in overheat_alerts[0]["message"]


# ---------------------------------------------------------------------------
# Traction loss
# ---------------------------------------------------------------------------

def test_traction_loss_alert():
    mgr = SessionManager()
    _start_session(mgr)
    engine = CoachEngine()

    all_alerts = []
    for i in range(5):
        pkt = _base_packet(
            timestamp_ms=1000 + i * 16,
            tire_combined_slip_RL=1.5,
            tire_combined_slip_RR=1.5,
        )
        alerts = engine.evaluate(pkt, mgr)
        all_alerts.extend(alerts)

    traction_alerts = [a for a in all_alerts if a["rule"] == "traction_loss"]
    assert len(traction_alerts) >= 1


# ---------------------------------------------------------------------------
# Cooldown prevents spam
# ---------------------------------------------------------------------------

def test_cooldown_prevents_spam():
    mgr = SessionManager()
    _start_session(mgr)
    engine = CoachEngine()

    all_alerts = []
    # 20 packets spanning 320ms total (well within the 10s cooldown)
    for i in range(20):
        pkt = _base_packet(
            timestamp_ms=1000 + i * 16,
            tire_combined_slip_RL=1.5,
            tire_combined_slip_RR=1.5,
        )
        alerts = engine.evaluate(pkt, mgr)
        all_alerts.extend(alerts)

    traction_alerts = [a for a in all_alerts if a["rule"] == "traction_loss"]
    assert len(traction_alerts) <= 1


# ---------------------------------------------------------------------------
# No alerts when no session is active
# ---------------------------------------------------------------------------

def test_no_alerts_without_session():
    mgr = SessionManager()
    engine = CoachEngine()

    pkt = _base_packet(tire_combined_slip_RL=1.5)
    alerts = engine.evaluate(pkt, mgr)
    assert alerts == []
