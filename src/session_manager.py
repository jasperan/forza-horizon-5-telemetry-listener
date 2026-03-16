"""SessionManager: tracks race sessions and lap transitions from telemetry state changes."""

import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


class SessionManager:
    """Detects race start/end and lap transitions from streaming telemetry updates.

    Properties:
        current_session: dict with session metadata while a race is active, None otherwise.
        current_lap: the current lap number (0 when no race is active).
        lap_just_completed: True if the most recent update() triggered a lap transition.
        completed_laps: list of dicts for every completed lap across all sessions.
        ended_sessions: list of dicts for every session that has ended.
        current_lap_positions: list of (x, y, z) tuples recorded during the current lap.
    """

    def __init__(self) -> None:
        self._current_session: Optional[dict] = None
        self._current_lap: int = 0
        self._lap_just_completed: bool = False
        self._completed_laps: list[dict] = []
        self._ended_sessions: list[dict] = []
        self._current_lap_positions: list[tuple[float, float, float]] = []
        self._prev_is_race_on: int = 0
        self._lap_start_timestamp_ms: int = 0
        self._lap_start_distance: float = 0.0

    # -- public properties ---------------------------------------------------

    @property
    def current_session(self) -> Optional[dict]:
        return self._current_session

    @property
    def current_lap(self) -> int:
        return self._current_lap

    @property
    def lap_just_completed(self) -> bool:
        return self._lap_just_completed

    @property
    def completed_laps(self) -> list[dict]:
        return list(self._completed_laps)

    @property
    def ended_sessions(self) -> list[dict]:
        return list(self._ended_sessions)

    @property
    def current_lap_positions(self) -> list[tuple[float, float, float]]:
        return list(self._current_lap_positions)

    # -- core update ----------------------------------------------------------

    def update(
        self,
        *,
        is_race_on: int,
        lap_number: int,
        timestamp_ms: int,
        car_ordinal: int,
        car_class: int,
        car_performance_index: int,
        drivetrain_type: int,
        distance_traveled: float,
        position_x: float,
        position_y: float,
        position_z: float,
        **kwargs,
    ) -> None:
        """Process a single telemetry tick and update session/lap state."""
        # Reset per-tick flags
        self._lap_just_completed = False

        # -- race start: 0 -> 1 ----------------------------------------------
        if is_race_on and not self._prev_is_race_on:
            self._start_session(
                timestamp_ms=timestamp_ms,
                car_ordinal=car_ordinal,
                car_class=car_class,
                car_performance_index=car_performance_index,
                drivetrain_type=drivetrain_type,
            )
            self._current_lap = lap_number
            self._lap_start_timestamp_ms = timestamp_ms
            self._lap_start_distance = distance_traveled
            self._current_lap_positions = []
            logger.info("Race started. Session %s, lap %d", self._current_session["session_id"], lap_number)

        # -- race end: 1 -> 0 ------------------------------------------------
        if not is_race_on and self._prev_is_race_on:
            self._end_session(timestamp_ms=timestamp_ms)
            self._prev_is_race_on = is_race_on
            return

        # -- mid-race processing ----------------------------------------------
        if is_race_on and self._current_session is not None:
            # Lap transition
            if lap_number != self._current_lap:
                self._complete_lap(
                    lap_no=self._current_lap,
                    end_timestamp_ms=timestamp_ms,
                    end_distance=distance_traveled,
                )
                self._current_lap = lap_number
                self._lap_start_timestamp_ms = timestamp_ms
                self._lap_start_distance = distance_traveled
                self._current_lap_positions = []

            # Track position
            self._current_lap_positions.append((position_x, position_y, position_z))

        self._prev_is_race_on = is_race_on

    # -- internal helpers -----------------------------------------------------

    def _start_session(
        self,
        *,
        timestamp_ms: int,
        car_ordinal: int,
        car_class: int,
        car_performance_index: int,
        drivetrain_type: int,
    ) -> None:
        self._current_session = {
            "session_id": str(uuid.uuid4()),
            "start_timestamp_ms": timestamp_ms,
            "car_ordinal": car_ordinal,
            "car_class": car_class,
            "car_performance_index": car_performance_index,
            "drivetrain_type": drivetrain_type,
            "total_laps": 0,
        }
        self._completed_laps = []

    def _end_session(self, *, timestamp_ms: int) -> None:
        if self._current_session is None:
            return
        self._current_session["end_timestamp_ms"] = timestamp_ms
        logger.info(
            "Race ended. Session %s, total laps: %d",
            self._current_session["session_id"],
            self._current_session["total_laps"],
        )
        self._ended_sessions.append(self._current_session)
        self._current_session = None
        self._current_lap = 0
        self._current_lap_positions = []

    def _complete_lap(
        self,
        *,
        lap_no: int,
        end_timestamp_ms: int,
        end_distance: float,
    ) -> None:
        lap_time_ms = end_timestamp_ms - self._lap_start_timestamp_ms
        lap_distance = end_distance - self._lap_start_distance
        lap_record = {
            "lap_no": lap_no,
            "lap_time_ms": lap_time_ms,
            "lap_distance": lap_distance,
            "positions": list(self._current_lap_positions),
        }
        self._completed_laps.append(lap_record)
        if self._current_session is not None:
            self._current_session["total_laps"] += 1
        self._lap_just_completed = True
        logger.info("Lap %d completed in %d ms (%.1f m)", lap_no, lap_time_ms, lap_distance)
