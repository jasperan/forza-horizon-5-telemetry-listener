"""End-to-end tests: send fake packets through TelemetryHub, verify pipeline."""

import struct
import asyncio
import pytest
from fastapi.testclient import TestClient

from src.telemetry_hub import TelemetryHub
from src.coach.engine import CoachEngine
from src.analytics.car_dna import CarDNACollector
from src.api.routes import create_app
from src.data_packet import ForzaDataPacket


# ---------------------------------------------------------------------------
# Packet construction helper
# ---------------------------------------------------------------------------

# The dash format expected after patching (data[:232] + data[244:323])
_DASH_FORMAT = ForzaDataPacket.dash_format  # '<iIffff...HBBBBBBbbb'  311 bytes
_SLED_PROPS = ForzaDataPacket.sled_props    # 57 fields
_DASH_PROPS = ForzaDataPacket.dash_props    # 27 fields
_ALL_PROPS = _SLED_PROPS + _DASH_PROPS      # 84 fields total


def _make_packet(
    is_race_on: int = 1,
    timestamp_ms: int = 1000,
    current_engine_rpm: float = 5000.0,
    speed: float = 30.0,
    lap_no: int = 1,
    car_ordinal: int = 100,
    car_class: int = 3,
    car_performance_index: int = 700,
    drivetrain_type: int = 1,
    num_cylinders: int = 6,
    position_x: float = 10.0,
    position_y: float = 0.0,
    position_z: float = 20.0,
    dist_traveled: float = 500.0,
    accel: int = 200,
    brake: int = 0,
    gear: int = 3,
    steer: int = 0,
) -> bytes:
    """Build a valid 323-byte Forza Horizon 5 telemetry packet.

    The raw packet is 323 bytes: 232 sled + 12-byte gap + 79 dash extension.
    ForzaDataPacket patches it to 311 bytes by stripping the 12-byte gap.
    """

    # Build the values dict keyed by property name with sensible defaults
    values = {prop: 0 for prop in _ALL_PROPS}

    # Sled section overrides
    values["is_race_on"] = is_race_on
    values["timestamp_ms"] = timestamp_ms
    values["engine_max_rpm"] = 8000.0
    values["engine_idle_rpm"] = 800.0
    values["current_engine_rpm"] = current_engine_rpm
    values["car_ordinal"] = car_ordinal
    values["car_class"] = car_class
    values["car_performance_index"] = car_performance_index
    values["drivetrain_type"] = drivetrain_type
    values["num_cylinders"] = num_cylinders

    # Dash section overrides
    values["position_x"] = position_x
    values["position_y"] = position_y
    values["position_z"] = position_z
    values["speed"] = speed
    values["power"] = 150000.0
    values["torque"] = 400.0
    values["dist_traveled"] = dist_traveled
    values["lap_no"] = lap_no
    values["race_pos"] = 1
    values["accel"] = accel
    values["brake"] = brake
    values["gear"] = gear
    values["steer"] = steer

    # Pack the 311 bytes (patched layout)
    ordered_values = [values[p] for p in _ALL_PROPS]
    patched = struct.pack(_DASH_FORMAT, *ordered_values)
    assert len(patched) == 311

    # Insert the 12-byte gap (zeros) between sled (232) and dash (79) to get 323 bytes
    raw_packet = patched[:232] + b"\x00" * 12 + patched[232:]
    assert len(raw_packet) == 323
    return raw_packet


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hub():
    """TelemetryHub with no DB, in race mode."""
    h = TelemetryHub(db_pool=None, mode="race")
    h.coach_engine = CoachEngine()
    return h


@pytest.fixture
def hub_all_mode():
    """TelemetryHub with no DB, mode='all' (no race filtering)."""
    h = TelemetryHub(db_pool=None, mode="all")
    h.coach_engine = CoachEngine()
    return h


# ---------------------------------------------------------------------------
# Test 1: Full pipeline (session lifecycle)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_pipeline(hub):
    """Race start -> mid-race packets -> race end: verify session lifecycle."""

    # Before anything, no session, zero packets
    assert hub.session_mgr.current_session is None
    assert hub.packet_count == 0

    # Race-start packet (is_race_on transitions from 0 -> 1)
    start_pkt = _make_packet(is_race_on=1, timestamp_ms=1000, lap_no=1, dist_traveled=0.0)
    await hub.on_packet(start_pkt)

    assert hub.session_mgr.current_session is not None
    assert hub.packet_count == 1
    session_id = hub.session_mgr.current_session["session_id"]
    assert session_id  # non-empty UUID string

    # 10 mid-race packets
    for i in range(10):
        pkt = _make_packet(
            is_race_on=1,
            timestamp_ms=2000 + i * 100,
            lap_no=1,
            speed=50.0 + i,
            dist_traveled=100.0 + i * 50,
            position_x=float(i),
        )
        await hub.on_packet(pkt)

    assert hub.packet_count == 11  # 1 start + 10 mid-race

    # Race-end packet (is_race_on transitions 1 -> 0)
    end_pkt = _make_packet(is_race_on=0, timestamp_ms=5000, lap_no=1, dist_traveled=600.0)
    await hub.on_packet(end_pkt)

    # Session should have ended
    assert hub.session_mgr.current_session is None
    assert len(hub.session_mgr.ended_sessions) == 1
    ended = hub.session_mgr.ended_sessions[0]
    assert ended["session_id"] == session_id
    assert ended["end_timestamp_ms"] == 5000

    # packet_count should NOT increment for the race-end packet (is_race_on=0)
    assert hub.packet_count == 11


# ---------------------------------------------------------------------------
# Test 2: API with hub
# ---------------------------------------------------------------------------

def test_api_with_hub():
    """FastAPI endpoints return correct data when backed by a TelemetryHub."""
    hub = TelemetryHub(db_pool=None, mode="all")
    app = create_app(hub=hub)
    client = TestClient(app)

    # GET /api/status
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["packet_count"] == 0

    # GET /api/sessions
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) == 0


# ---------------------------------------------------------------------------
# Test 3: Mode filtering (race mode skips is_race_on=0)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mode_filtering():
    """In race mode, packets with is_race_on=0 don't increment packet_count."""
    hub = TelemetryHub(db_pool=None, mode="race")

    # Send packet with race off
    off_pkt = _make_packet(is_race_on=0, timestamp_ms=500)
    await hub.on_packet(off_pkt)
    assert hub.packet_count == 0

    # Send packet with race on (first on-packet triggers session start)
    on_pkt = _make_packet(is_race_on=1, timestamp_ms=1000)
    await hub.on_packet(on_pkt)
    assert hub.packet_count == 1
    assert hub.session_mgr.current_session is not None


# ---------------------------------------------------------------------------
# Test 4: Lap completion flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lap_completion_flow(hub):
    """Lap transition triggers lap_just_completed and populates completed_laps."""

    # Start race on lap 1
    await hub.on_packet(_make_packet(
        is_race_on=1, timestamp_ms=1000, lap_no=1, dist_traveled=0.0,
    ))
    assert hub.session_mgr.current_session is not None
    assert hub.session_mgr.current_lap == 1
    assert len(hub.session_mgr.completed_laps) == 0

    # A few packets on lap 1
    for i in range(5):
        await hub.on_packet(_make_packet(
            is_race_on=1,
            timestamp_ms=2000 + i * 200,
            lap_no=1,
            dist_traveled=100.0 + i * 100,
            position_x=float(i * 10),
        ))

    assert hub.session_mgr.current_lap == 1
    assert len(hub.session_mgr.completed_laps) == 0

    # Transition to lap 2 -> triggers lap 1 completion
    await hub.on_packet(_make_packet(
        is_race_on=1, timestamp_ms=5000, lap_no=2, dist_traveled=800.0,
    ))

    assert hub.session_mgr.current_lap == 2
    assert hub.session_mgr.lap_just_completed is True
    assert len(hub.session_mgr.completed_laps) == 1

    completed = hub.session_mgr.completed_laps[0]
    assert completed["lap_no"] == 1
    assert completed["lap_time_ms"] == 5000 - 1000  # end_ts - start_ts
    assert completed["lap_distance"] == 800.0 - 0.0

    # Verify session total_laps counter incremented
    assert hub.session_mgr.current_session["total_laps"] == 1


# ---------------------------------------------------------------------------
# Test 5: API reflects session state after pipeline activity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_reflects_pipeline_state():
    """After running packets through the hub, API endpoints reflect the state."""
    hub = TelemetryHub(db_pool=None, mode="race")
    app = create_app(hub=hub)
    client = TestClient(app)

    # Start and end a session
    await hub.on_packet(_make_packet(is_race_on=1, timestamp_ms=1000, lap_no=1))
    await hub.on_packet(_make_packet(is_race_on=0, timestamp_ms=3000, lap_no=1))

    # Status should show packet count
    resp = client.get("/api/status")
    body = resp.json()
    assert body["packet_count"] == 1
    assert body["current_session"] is None  # ended

    # Sessions endpoint should list the ended session
    resp = client.get("/api/sessions")
    sessions = resp.json()
    assert len(sessions) == 1
    assert sessions[0]["start_timestamp_ms"] == 1000
    assert sessions[0]["end_timestamp_ms"] == 3000
