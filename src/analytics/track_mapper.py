"""Track mapping: position downsampling and deterministic track hashing."""

from __future__ import annotations

import hashlib
import math


def downsample_positions(
    positions: list[tuple], target: int = 50
) -> list[tuple]:
    """Evenly downsample *positions* to *target* points.

    The first and last positions are always preserved. If there are
    fewer positions than *target*, the original list is returned as-is.
    """
    n = len(positions)
    if n <= target:
        return list(positions)
    if target <= 1:
        return [positions[0]] if positions else []

    # Pick evenly spaced indices, always including 0 and n-1
    indices = set()
    indices.add(0)
    indices.add(n - 1)
    for i in range(target):
        idx = round(i * (n - 1) / (target - 1))
        indices.add(idx)
    sorted_indices = sorted(indices)

    # If rounding produced extras, trim from the middle
    while len(sorted_indices) > target:
        # Remove the index closest to the midpoint (excluding first/last)
        mid = len(sorted_indices) // 2
        sorted_indices.pop(mid)

    return [positions[i] for i in sorted_indices]


def compute_track_hash(
    positions: list[tuple], sample_size: int = 50
) -> str:
    """Compute a deterministic SHA-256 hash for a track.

    Steps:
    1. Downsample to *sample_size* points.
    2. Round coordinates to 1 decimal place.
    3. Use only X (index 0) and Z (index 2), ignoring Y/height.
    4. Return the hex digest.
    """
    sampled = downsample_positions(positions, target=sample_size)

    # Build a canonical string: "x,z|x,z|..."
    parts: list[str] = []
    for pos in sampled:
        x = round(float(pos[0]), 1)
        # Use index 2 for Z; fall back to index 1 if tuple only has 2 elements
        z_idx = 2 if len(pos) > 2 else 1
        z = round(float(pos[z_idx]), 1)
        parts.append(f"{x},{z}")

    canonical = "|".join(parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
