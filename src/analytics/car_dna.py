"""Car DNA fingerprinting: collects per-car performance samples and creates
normalized vector embeddings for similarity search."""


class CarDNACollector:
    """Builds running-average performance profiles for each car and exposes
    a normalized 6-dimensional fingerprint vector suitable for vector search."""

    # Normalization ranges for each dimension
    _RANGES = {
        "max_speed": (0, 500),
        "max_lateral_g": (0, 3),
        "accel_time_0_100": (1, 10),
        "braking_distance_100_0": (10, 60),
        "power_at_peak_rpm": (0, 1_000_000),
        "car_class": (0, 7),
    }

    _VECTOR_KEYS = [
        "max_speed",
        "max_lateral_g",
        "accel_time_0_100",
        "braking_distance_100_0",
        "power_at_peak_rpm",
        "car_class",
    ]

    def __init__(self) -> None:
        self.profiles: dict[int, dict] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, sample: dict) -> None:
        """Ingest a single telemetry sample and update the running average
        for the car identified by *car_ordinal*."""

        car_id = sample["car_ordinal"]

        if car_id not in self.profiles:
            self.profiles[car_id] = {
                "car_ordinal": car_id,
                "samples": 0,
                "car_class": sample.get("car_class", 0),
                "drivetrain_type": sample.get("drivetrain_type", 0),
                "max_speed": 0.0,
                "max_lateral_g": 0.0,
                "accel_time_0_100": 0.0,
                "braking_distance_100_0": 0.0,
                "power_at_peak_rpm": 0.0,
            }

        profile = self.profiles[car_id]
        n = profile["samples"]
        n_new = n + 1

        # Incremental mean: new_avg = old_avg + (value - old_avg) / n_new
        for key in [
            "max_speed",
            "max_lateral_g",
            "accel_time_0_100",
            "braking_distance_100_0",
            "power_at_peak_rpm",
        ]:
            old = profile[key]
            profile[key] = old + (sample.get(key, 0) - old) / n_new

        # Overwrite categorical fields with the latest value
        profile["car_class"] = sample.get("car_class", profile["car_class"])
        profile["drivetrain_type"] = sample.get(
            "drivetrain_type", profile["drivetrain_type"]
        )
        profile["samples"] = n_new

    def get_fingerprint_vector(self, car_ordinal: int) -> list[float] | None:
        """Return a 6-dimensional normalized vector for the given car, or
        *None* if the car hasn't been seen yet."""

        if car_ordinal not in self.profiles:
            return None

        profile = self.profiles[car_ordinal]
        return [
            self._normalize(profile[key], *self._RANGES[key])
            for key in self._VECTOR_KEYS
        ]

    def get_profile(self, car_ordinal: int) -> dict | None:
        """Return the full profile dict (including the fingerprint vector)
        for the given car, or *None* if unknown."""

        if car_ordinal not in self.profiles:
            return None

        profile = dict(self.profiles[car_ordinal])  # shallow copy
        profile["fingerprint_vector"] = self.get_fingerprint_vector(car_ordinal)
        return profile

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(value: float, vmin: float, vmax: float) -> float:
        """Min-max normalization clamped to [0, 1]."""
        if vmax == vmin:
            return 0.0
        return max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
