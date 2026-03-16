"""Tests for ForzaDataPacket."""
import struct
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.data_packet import ForzaDataPacket


def _build_packet(is_race_on=1, timestamp_ms=1000,
                  engine_max_rpm=8000.0, engine_idle_rpm=800.0,
                  current_engine_rpm=5000.0):
    """Build a full 323-byte dash packet with known values in the first 5 fields.

    Layout: 232 bytes sled + 12 bytes gap + 79 bytes dash-extra = 323 bytes.
    The constructor patches out the 12-byte gap before unpacking with dash_format.
    """
    # dash_format: '<iIfffffffffffffffffffffffffffffffffffffffffffffffffffiiiiifffffffffffffffffHBBBBBBbbb'
    # 85 fields total: 58 sled + 27 dash
    # Sled portion (58 fields): i I f*51 i*5
    #   Field 0: is_race_on (i)
    #   Field 1: timestamp_ms (I)
    #   Field 2: engine_max_rpm (f)
    #   Field 3: engine_idle_rpm (f)
    #   Field 4: current_engine_rpm (f)
    #   Fields 5-52: floats (48 zeros)
    #   Fields 53-57: ints (5 zeros) -> car_ordinal, car_class, car_performance_index, drivetrain_type, num_cylinders

    sled_values = [is_race_on, timestamp_ms,
                   engine_max_rpm, engine_idle_rpm, current_engine_rpm]
    # Remaining 48 floats in sled portion
    sled_values += [0.0] * 48
    # 5 ints at end of sled
    sled_values += [0] * 5

    sled_format = '<iIfffffffffffffffffffffffffffffffffffffffffffffffffffiiiii'
    sled_bytes = struct.pack(sled_format, *sled_values)
    assert len(sled_bytes) == 232

    # 12-byte gap (ignored by constructor)
    gap = b'\x00' * 12

    # Dash-extra portion (27 fields): f*17 H B*6 b*3
    # 17 floats + 1 unsigned short + 6 unsigned bytes + 3 signed bytes
    dash_extra_format = '<fffffffffffffffffHBBBBBBbbb'
    dash_extra_values = [0.0] * 17 + [0] * 10  # 17 floats + 1H + 6B + 3b = 10 ints
    dash_extra_bytes = struct.pack(dash_extra_format, *dash_extra_values)

    raw_packet = sled_bytes + gap + dash_extra_bytes
    assert len(raw_packet) == 323
    return raw_packet


class TestForzaDataPacket:

    def test_sled_packet_parsing(self):
        """Parse a packet with known values and verify attributes."""
        data = _build_packet(
            is_race_on=1,
            timestamp_ms=1000,
            engine_max_rpm=8000.0,
            engine_idle_rpm=800.0,
            current_engine_rpm=5000.0,
        )
        pkt = ForzaDataPacket(data)

        assert pkt.is_race_on == 1
        assert pkt.timestamp_ms == 1000
        assert abs(pkt.engine_max_rpm - 8000.0) < 0.01
        assert abs(pkt.engine_idle_rpm - 800.0) < 0.01
        assert abs(pkt.current_engine_rpm - 5000.0) < 0.01
        # Zeroed fields
        assert pkt.acceleration_x == 0.0
        assert pkt.car_ordinal == 0

    def test_to_dict(self):
        """to_dict() returns a dict with correct keys and values."""
        data = _build_packet(is_race_on=1, timestamp_ms=2000,
                             engine_max_rpm=9000.0)
        pkt = ForzaDataPacket(data)
        d = pkt.to_dict()

        assert isinstance(d, dict)
        assert d['is_race_on'] == 1
        assert d['timestamp_ms'] == 2000
        assert abs(d['engine_max_rpm'] - 9000.0) < 0.01
        # All props should be present as keys
        for prop in ForzaDataPacket.get_props():
            assert prop in d, f"Missing key: {prop}"

    def test_get_props(self):
        """get_props() returns a list of property names with expected length."""
        props = ForzaDataPacket.get_props()
        assert isinstance(props, list)
        assert len(props) == 85
        assert 'is_race_on' in props
        assert 'timestamp_ms' in props
        assert 'current_engine_rpm' in props
        assert 'speed' in props
        assert 'norm_ai_brake_diff' in props

    def test_repr(self):
        """__repr__ returns a readable string representation."""
        data = _build_packet(is_race_on=1, timestamp_ms=3000,
                             current_engine_rpm=6500.0)
        pkt = ForzaDataPacket(data)
        r = repr(pkt)
        assert 'ForzaDataPacket' in r
        assert '6500' in r
        assert '3000' in r
