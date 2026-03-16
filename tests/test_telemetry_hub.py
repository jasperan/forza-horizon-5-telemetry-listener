"""Tests for TelemetryHub: packet parsing, async pipeline, and session integration."""

import asyncio
import struct
import pytest

from src.telemetry_hub import TelemetryHub, UDPProtocol
from src.data_packet import ForzaDataPacket


# ---------------------------------------------------------------------------
# Helpers: build a valid 323-byte Forza packet
# ---------------------------------------------------------------------------

# dash_format unpacks to 311 bytes (232 sled + 79 dash-extra fields).
# Raw packet is 323 bytes: 232 (sled) + 12 (gap, ignored) + 79 (dash-extra).
_SLED_FMT = ForzaDataPacket.sled_format   # 232 bytes
_DASH_FMT = ForzaDataPacket.dash_format   # 311 bytes total

# The extra fields beyond sled: 'fffffffffffffffffHBBBBBBbbb' = 79 bytes
_DASH_EXTRA_FMT = "<fffffffffffffffffHBBBBBBbbb"
_DASH_EXTRA_SIZE = struct.calcsize(_DASH_EXTRA_FMT)  # 79
_SLED_SIZE = struct.calcsize(_SLED_FMT)              # 232
_GAP_SIZE = 12


def _make_packet(
    is_race_on: int = 1,
    timestamp_ms: int = 1000,
    lap_no: int = 1,
    car_ordinal: int = 100,
    car_class: int = 5,
    car_pi: int = 800,
    drivetrain_type: int = 1,
    position_x: float = 0.0,
    position_y: float = 0.0,
    position_z: float = 0.0,
    speed: float = 50.0,
    dist_traveled: float = 100.0,
) -> bytes:
    """Build a valid 323-byte telemetry packet with controllable fields."""

    # -- sled portion (232 bytes) --
    # Format: <iIfffffffffffffffffffffffffffffffffffffffffffffffffffiiiii
    # 58 items: 1(i) + 1(I) + 51(f) + 5(i) = 58
    sled_values = [
        is_race_on,       # is_race_on (i)
        timestamp_ms,     # timestamp_ms (I)
    ]
    # 51 floats: engine_max_rpm .. suspension_travel_meters_RR
    sled_values.extend([0.0] * 51)
    # 5 ints: car_ordinal, car_class, car_performance_index, drivetrain_type, num_cylinders
    sled_values.extend([car_ordinal, car_class, car_pi, drivetrain_type, 6])

    sled_bytes = struct.pack(_SLED_FMT, *sled_values)
    assert len(sled_bytes) == _SLED_SIZE

    # -- 12-byte gap (ignored by parser) --
    gap_bytes = b"\x00" * _GAP_SIZE

    # -- dash-extra portion (79 bytes) --
    # Format: <fffffffffffffffffHBBBBBBbbb
    # Fields (27): position_x, position_y, position_z, speed, power, torque,
    #   tire_temp x4, boost, fuel, dist_traveled, best_lap_time, last_lap_time,
    #   cur_lap_time, cur_race_time, lap_no(H), race_pos(B), accel(B), brake(B),
    #   clutch(B), handbrake(B), gear(B), steer(b), norm_driving_line(b),
    #   norm_ai_brake_diff(b)
    dash_extra_values = [
        position_x,       # position_x
        position_y,       # position_y
        position_z,       # position_z
        speed,            # speed
        0.0,              # power
        0.0,              # torque
        0.0, 0.0, 0.0, 0.0,  # tire temps
        0.0,              # boost
        0.0,              # fuel
        dist_traveled,    # dist_traveled
        0.0,              # best_lap_time
        0.0,              # last_lap_time
        0.0,              # cur_lap_time
        0.0,              # cur_race_time
        lap_no,           # lap_no (H = unsigned short)
        1,                # race_pos (B)
        0,                # accel (B)
        0,                # brake (B)
        0,                # clutch (B)
        0,                # handbrake (B)
        3,                # gear (B)
        0,                # steer (b)
        0,                # norm_driving_line (b)
        0,                # norm_ai_brake_diff (b)
    ]

    dash_extra_bytes = struct.pack(_DASH_EXTRA_FMT, *dash_extra_values)
    assert len(dash_extra_bytes) == _DASH_EXTRA_SIZE

    raw = sled_bytes + gap_bytes + dash_extra_bytes
    assert len(raw) == 323
    return raw


# ---------------------------------------------------------------------------
# Hub creation
# ---------------------------------------------------------------------------

class TestHubCreation:
    def test_default_creation(self):
        hub = TelemetryHub(udp_port=65530, db_pool=None)
        assert hub.udp_port == 65530
        assert hub.session_mgr is not None
        assert hub.ws_mgr is not None
        assert hub.db_writer is not None
        assert hub.coach_engine is None
        assert hub.car_dna is None
        assert hub.packet_count == 0

    def test_custom_params(self):
        hub = TelemetryHub(udp_port=12345, db_pool=None, batch_size=10, mode="free")
        assert hub.udp_port == 12345
        assert hub.mode == "free"
        assert hub.db_writer.batch_size == 10


# ---------------------------------------------------------------------------
# Packet parsing
# ---------------------------------------------------------------------------

class TestProcessPacket:
    def test_valid_packet(self):
        hub = TelemetryHub(udp_port=65530, db_pool=None)
        data = _make_packet(is_race_on=1, timestamp_ms=1000)
        result = hub.process_packet(data)
        assert result is not None
        assert result["is_race_on"] == 1
        assert result["timestamp_ms"] == 1000

    def test_packet_fields(self):
        hub = TelemetryHub(udp_port=65530, db_pool=None)
        data = _make_packet(
            is_race_on=1, timestamp_ms=5000,
            lap_no=3, car_ordinal=200, speed=120.0,
            position_x=1.5, position_y=2.5, position_z=3.5,
        )
        result = hub.process_packet(data)
        assert result["lap_no"] == 3
        assert result["car_ordinal"] == 200
        assert abs(result["speed"] - 120.0) < 0.01
        assert abs(result["position_x"] - 1.5) < 0.01
        assert abs(result["position_y"] - 2.5) < 0.01
        assert abs(result["position_z"] - 3.5) < 0.01

    def test_garbage_returns_none(self):
        hub = TelemetryHub(udp_port=65530, db_pool=None)
        result = hub.process_packet(b"\x00\x01\x02")
        assert result is None

    def test_empty_bytes_returns_none(self):
        hub = TelemetryHub(udp_port=65530, db_pool=None)
        result = hub.process_packet(b"")
        assert result is None


# ---------------------------------------------------------------------------
# Session field extraction
# ---------------------------------------------------------------------------

class TestSessionFields:
    def test_extracts_correct_keys(self):
        hub = TelemetryHub(udp_port=65530, db_pool=None)
        data = _make_packet(
            is_race_on=1, timestamp_ms=2000, lap_no=2,
            car_ordinal=50, car_class=3, car_pi=700,
            drivetrain_type=2, dist_traveled=500.0,
            position_x=10.0, position_y=20.0, position_z=30.0,
        )
        packet = hub.process_packet(data)
        fields = hub._session_fields(packet)

        assert fields["is_race_on"] == 1
        assert fields["lap_number"] == 2
        assert fields["timestamp_ms"] == 2000
        assert fields["car_ordinal"] == 50
        assert fields["car_class"] == 3
        assert fields["car_performance_index"] == 700
        assert fields["drivetrain_type"] == 2
        assert abs(fields["distance_traveled"] - 500.0) < 0.01
        assert abs(fields["position_x"] - 10.0) < 0.01
        assert abs(fields["position_y"] - 20.0) < 0.01
        assert abs(fields["position_z"] - 30.0) < 0.01


# ---------------------------------------------------------------------------
# Async pipeline (on_packet)
# ---------------------------------------------------------------------------

class TestOnPacket:
    @pytest.mark.asyncio
    async def test_race_off_skips_broadcast_in_race_mode(self):
        hub = TelemetryHub(udp_port=65530, db_pool=None, mode="race")
        data = _make_packet(is_race_on=0, timestamp_ms=100)
        await hub.on_packet(data)
        assert hub.packet_count == 0
        assert hub.db_writer.pending == 0

    @pytest.mark.asyncio
    async def test_race_on_increments_count(self):
        hub = TelemetryHub(udp_port=65530, db_pool=None, mode="race")
        data = _make_packet(is_race_on=1, timestamp_ms=100)
        await hub.on_packet(data)
        assert hub.packet_count == 1

    @pytest.mark.asyncio
    async def test_packet_buffered_in_db_writer(self):
        hub = TelemetryHub(udp_port=65530, db_pool=None, mode="race")
        data = _make_packet(is_race_on=1, timestamp_ms=100)
        await hub.on_packet(data)
        assert hub.db_writer.pending == 1

    @pytest.mark.asyncio
    async def test_session_starts_on_first_race_packet(self):
        hub = TelemetryHub(udp_port=65530, db_pool=None, mode="race")
        data = _make_packet(is_race_on=1, timestamp_ms=500, car_ordinal=42)
        await hub.on_packet(data)
        session = hub.session_mgr.current_session
        assert session is not None
        assert session["car_ordinal"] == 42

    @pytest.mark.asyncio
    async def test_session_id_injected_into_packet(self):
        """After session starts, packet dict should contain session_id."""
        hub = TelemetryHub(udp_port=65530, db_pool=None, mode="race")
        data = _make_packet(is_race_on=1, timestamp_ms=500)
        await hub.on_packet(data)
        # The DB writer buffer should have the packet with session_id
        buffered = hub.db_writer._buffer
        assert len(buffered) == 1
        assert "session_id" in buffered[0]

    @pytest.mark.asyncio
    async def test_free_mode_processes_all_packets(self):
        """In 'free' mode, packets with is_race_on=0 still go through the pipeline."""
        hub = TelemetryHub(udp_port=65530, db_pool=None, mode="free")
        data = _make_packet(is_race_on=0, timestamp_ms=100)
        await hub.on_packet(data)
        assert hub.packet_count == 1
        assert hub.db_writer.pending == 1

    @pytest.mark.asyncio
    async def test_multiple_packets_increment_count(self):
        hub = TelemetryHub(udp_port=65530, db_pool=None, mode="race")
        for i in range(5):
            data = _make_packet(is_race_on=1, timestamp_ms=100 + i)
            await hub.on_packet(data)
        assert hub.packet_count == 5

    @pytest.mark.asyncio
    async def test_race_end_detected(self):
        hub = TelemetryHub(udp_port=65530, db_pool=None, mode="race")
        # Start race
        await hub.on_packet(_make_packet(is_race_on=1, timestamp_ms=100))
        assert hub.session_mgr.current_session is not None
        # End race
        await hub.on_packet(_make_packet(is_race_on=0, timestamp_ms=200))
        assert hub.session_mgr.current_session is None
        assert len(hub.session_mgr.ended_sessions) == 1


# ---------------------------------------------------------------------------
# Lap completion
# ---------------------------------------------------------------------------

class TestLapCompletion:
    @pytest.mark.asyncio
    async def test_lap_transition_triggers_save(self):
        hub = TelemetryHub(udp_port=65530, db_pool=None, mode="race")
        # Start race on lap 1
        await hub.on_packet(_make_packet(
            is_race_on=1, timestamp_ms=1000, lap_no=1, dist_traveled=0.0,
        ))
        # A few ticks on lap 1
        await hub.on_packet(_make_packet(
            is_race_on=1, timestamp_ms=2000, lap_no=1, dist_traveled=500.0,
        ))
        # Transition to lap 2
        await hub.on_packet(_make_packet(
            is_race_on=1, timestamp_ms=3000, lap_no=2, dist_traveled=1000.0,
        ))
        assert len(hub.session_mgr.completed_laps) == 1
        completed = hub.session_mgr.completed_laps[0]
        assert completed["lap_no"] == 1
        assert completed["lap_time_ms"] == 2000  # 3000 - 1000


# ---------------------------------------------------------------------------
# UDPProtocol
# ---------------------------------------------------------------------------

class TestUDPProtocol:
    def test_protocol_stores_hub_reference(self):
        hub = TelemetryHub(udp_port=65530, db_pool=None)
        proto = UDPProtocol(hub)
        assert proto.hub is hub

    def test_error_received_logs(self, caplog):
        """error_received should log and not raise."""
        hub = TelemetryHub(udp_port=65530, db_pool=None)
        proto = UDPProtocol(hub)
        import logging
        with caplog.at_level(logging.ERROR):
            proto.error_received(OSError("test error"))
        assert "test error" in caplog.text


# ---------------------------------------------------------------------------
# Coach integration
# ---------------------------------------------------------------------------

class TestCoachIntegration:
    @pytest.mark.asyncio
    async def test_coach_alerts_broadcast(self):
        """When coach_engine is set and returns alerts, they get broadcast."""
        hub = TelemetryHub(udp_port=65530, db_pool=None, mode="race")

        # Mock coach engine
        class MockCoach:
            def evaluate(self, packet, session_mgr):
                return [{"rule": "test_rule", "message": "Brake earlier!"}]

        hub.coach_engine = MockCoach()

        # We need a mock WS client to capture broadcasts
        broadcasts = []

        class FakeWS:
            async def send_json(self, data):
                broadcasts.append(data)

        ws = FakeWS()
        await hub.ws_mgr.connect(ws, "coach")
        await hub.ws_mgr.connect(ws, "telemetry")

        await hub.on_packet(_make_packet(is_race_on=1, timestamp_ms=500))

        # Should have telemetry broadcast + coach alert broadcast
        coach_msgs = [b for b in broadcasts if isinstance(b, dict) and b.get("type") == "alerts"]
        assert len(coach_msgs) == 1
        assert coach_msgs[0]["alerts"][0]["rule"] == "test_rule"
