"""Lap analysis: sector times and performance vectors."""

from __future__ import annotations

import bisect


def compute_sector_times(
    timestamps: list[int], distances: list[float]
) -> list[float]:
    """Split a lap into 3 equal-distance sectors and return time per sector.

    Parameters
    ----------
    timestamps : list[int]
        Monotonically increasing timestamps (milliseconds or game ticks).
    distances : list[float]
        Cumulative distance at each timestamp.

    Returns
    -------
    list[float]
        Exactly 3 floats representing seconds spent in each sector.
    """
    if len(timestamps) < 3 or len(distances) < 3:
        total = 0.0
        if len(timestamps) >= 2:
            total = (timestamps[-1] - timestamps[0]) / 1000.0
        # Spread whatever time we have across 3 sectors
        return [total / 3.0, total / 3.0, total / 3.0]

    total_distance = distances[-1] - distances[0]
    if total_distance <= 0:
        total = (timestamps[-1] - timestamps[0]) / 1000.0
        return [total / 3.0, total / 3.0, total / 3.0]

    d_start = distances[0]
    boundary_1 = d_start + total_distance / 3.0
    boundary_2 = d_start + 2.0 * total_distance / 3.0

    def _interp_time(boundary: float) -> float:
        """Linearly interpolate the timestamp at a given distance."""
        idx = bisect.bisect_right(distances, boundary)
        if idx == 0:
            return float(timestamps[0])
        if idx >= len(distances):
            return float(timestamps[-1])
        d0, d1 = distances[idx - 1], distances[idx]
        t0, t1 = timestamps[idx - 1], timestamps[idx]
        if d1 == d0:
            return float(t0)
        frac = (boundary - d0) / (d1 - d0)
        return t0 + frac * (t1 - t0)

    t_start = float(timestamps[0])
    t_end = float(timestamps[-1])
    t1 = _interp_time(boundary_1)
    t2 = _interp_time(boundary_2)

    sector_1 = (t1 - t_start) / 1000.0
    sector_2 = (t2 - t1) / 1000.0
    sector_3 = (t_end - t2) / 1000.0

    return [sector_1, sector_2, sector_3]


def compute_performance_vector(
    sectors: list[float], lap_data: dict
) -> list[float]:
    """Build a 12-dimensional performance vector for a lap.

    Layout
    ------
    [0:3]  sector speed proxies   – inverse sector time, normalised so max = 1
    [3:6]  braking efficiencies   – from lap_data["braking_events"] per sector
    [6:9]  traction event counts  – normalised 0-1, capped at 10
    [9]    avg_tire_temp_delta    – from lap_data
    [10]   throttle_pct           – from lap_data
    [11]   line_deviation_score   – from lap_data
    """
    # --- sector speed proxies (inverse time, normalised) ---
    inv_times = []
    for s in sectors[:3]:
        inv_times.append(1.0 / s if s > 0 else 0.0)
    max_inv = max(inv_times) if inv_times else 1.0
    if max_inv == 0:
        max_inv = 1.0
    speed_proxies = [v / max_inv for v in inv_times]
    # Pad to 3 if fewer sectors provided
    while len(speed_proxies) < 3:
        speed_proxies.append(0.0)

    # --- braking efficiencies ---
    braking_raw = lap_data.get("braking_events", [0.0, 0.0, 0.0])
    braking = []
    for i in range(3):
        val = braking_raw[i] if i < len(braking_raw) else 0.0
        braking.append(max(0.0, min(1.0, float(val))))

    # --- traction event counts (normalised 0-1, cap 10) ---
    traction_raw = lap_data.get("traction_events", [0, 0, 0])
    traction = []
    for i in range(3):
        val = traction_raw[i] if i < len(traction_raw) else 0
        traction.append(min(float(val), 10.0) / 10.0)

    # --- scalar features ---
    avg_tire_temp_delta = float(lap_data.get("avg_tire_temp_delta", 0.0))
    throttle_pct = float(lap_data.get("throttle_pct", 0.0))
    line_deviation_score = float(lap_data.get("line_deviation_score", 0.0))

    return (
        speed_proxies[:3]
        + braking[:3]
        + traction[:3]
        + [avg_tire_temp_delta, throttle_pct, line_deviation_score]
    )
