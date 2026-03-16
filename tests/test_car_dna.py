"""Tests for the Car DNA fingerprinting system."""

import sys
import os

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "src")
)

from analytics.car_dna import CarDNACollector


def _make_sample(**overrides) -> dict:
    """Return a default telemetry sample, with any field overrides applied."""
    base = {
        "car_ordinal": 1,
        "car_class": 3,
        "drivetrain_type": 1,
        "max_speed": 300.0,
        "max_lateral_g": 1.5,
        "accel_time_0_100": 4.0,
        "braking_distance_100_0": 30.0,
        "power_at_peak_rpm": 500_000.0,
    }
    base.update(overrides)
    return base


def test_record_sample():
    collector = CarDNACollector()
    collector.record(_make_sample())

    assert 1 in collector.profiles
    assert collector.profiles[1]["samples"] == 1


def test_multiple_samples_average():
    collector = CarDNACollector()
    for speed in [300, 310, 320]:
        collector.record(_make_sample(max_speed=speed))

    profile = collector.profiles[1]
    assert profile["samples"] == 3
    assert abs(profile["max_speed"] - 310.0) < 1e-9


def test_fingerprint_vector():
    collector = CarDNACollector()
    collector.record(_make_sample())

    vec = collector.get_fingerprint_vector(1)
    assert vec is not None
    assert len(vec) == 6
    assert all(isinstance(v, float) for v in vec)
    # All values should be in [0, 1]
    assert all(0.0 <= v <= 1.0 for v in vec)


def test_get_profile_dict():
    collector = CarDNACollector()
    collector.record(_make_sample())

    profile = collector.get_profile(1)
    assert profile is not None
    assert profile["car_ordinal"] == 1
    assert "fingerprint_vector" in profile
    assert len(profile["fingerprint_vector"]) == 6


def test_unknown_car_returns_none():
    collector = CarDNACollector()
    assert collector.get_fingerprint_vector(999) is None
    assert collector.get_profile(999) is None


def test_normalize_clamps():
    assert CarDNACollector._normalize(600, 0, 500) == 1.0
    assert CarDNACollector._normalize(-10, 0, 500) == 0.0
    assert abs(CarDNACollector._normalize(250, 0, 500) - 0.5) < 1e-9
