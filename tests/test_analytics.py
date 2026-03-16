"""Tests for the analytics module: lap_analyzer and track_mapper."""

import math
import sys
import os

# Ensure src is importable
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), os.pardir, "src"),
)

from analytics.lap_analyzer import compute_sector_times, compute_performance_vector
from analytics.track_mapper import downsample_positions, compute_track_hash


class TestSectorTimes:
    def test_sector_times_splits_into_thirds(self):
        """9 points with linear timestamps and distances produce 3 sectors."""
        # timestamps 0..8000 ms, distances 0..800 m (linear)
        timestamps = list(range(0, 9000, 1000))  # [0,1000,...,8000]
        distances = [float(i * 100) for i in range(9)]  # [0,100,...,800]

        sectors = compute_sector_times(timestamps, distances)

        assert len(sectors) == 3, f"Expected 3 sectors, got {len(sectors)}"
        # Each sector covers 1/3 of the distance and (linearly) 1/3 of
        # the total time = 8000 ms / 3 ~ 2.667 s
        expected = 8000.0 / 3.0 / 1000.0
        for i, s in enumerate(sectors):
            assert abs(s - expected) < 0.01, (
                f"Sector {i}: {s:.4f} != expected {expected:.4f}"
            )

    def test_sector_times_edge_few_points(self):
        """Fewer than 3 points still returns 3 floats."""
        sectors = compute_sector_times([0, 1000], [0.0, 100.0])
        assert len(sectors) == 3

    def test_sector_times_zero_distance(self):
        """Zero total distance returns 3 equal time slices."""
        sectors = compute_sector_times(
            [0, 1000, 2000], [0.0, 0.0, 0.0]
        )
        assert len(sectors) == 3
        assert all(s >= 0 for s in sectors)


class TestPerformanceVector:
    def test_performance_vector_shape(self):
        """Performance vector is always 12 floats."""
        sectors = [30.0, 28.5, 31.2]
        lap_data = {
            "braking_events": [0.8, 0.6, 0.7],
            "traction_events": [3, 5, 2],
            "avg_tire_temp_delta": 4.5,
            "throttle_pct": 0.72,
            "line_deviation_score": 0.15,
        }
        vec = compute_performance_vector(sectors, lap_data)

        assert len(vec) == 12, f"Expected 12 dims, got {len(vec)}"
        assert all(isinstance(v, float) for v in vec)

    def test_performance_vector_defaults(self):
        """Missing lap_data keys produce zeros, not errors."""
        vec = compute_performance_vector([10.0, 10.0, 10.0], {})
        assert len(vec) == 12
        # All speed proxies should be equal (1.0) since sectors are equal
        assert vec[0] == vec[1] == vec[2] == 1.0


class TestDownsamplePositions:
    def test_downsample_positions(self):
        """200 points down to 50: length 50, first and last preserved."""
        positions = [(float(i), float(i * 2), float(i * 3)) for i in range(200)]
        result = downsample_positions(positions, target=50)

        assert len(result) == 50, f"Expected 50 points, got {len(result)}"
        assert result[0] == positions[0], "First point not preserved"
        assert result[-1] == positions[-1], "Last point not preserved"

    def test_downsample_fewer_than_target(self):
        """If fewer points than target, return all of them."""
        positions = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
        result = downsample_positions(positions, target=50)
        assert len(result) == 2


class TestTrackHash:
    def test_track_hash_deterministic(self):
        """Same positions always produce the same hash, length 64."""
        positions = [(float(i), float(i + 1), float(i + 2)) for i in range(100)]
        h1 = compute_track_hash(positions)
        h2 = compute_track_hash(positions)

        assert h1 == h2, "Hash is not deterministic"
        assert len(h1) == 64, f"Expected 64-char hex, got {len(h1)}"

    def test_track_hash_different_for_different_tracks(self):
        """Different position sets produce different hashes."""
        pos_a = [(float(i), 0.0, float(i)) for i in range(100)]
        pos_b = [(float(i * 2), 0.0, float(i * 3)) for i in range(100)]

        hash_a = compute_track_hash(pos_a)
        hash_b = compute_track_hash(pos_b)

        assert hash_a != hash_b, "Different tracks should have different hashes"
