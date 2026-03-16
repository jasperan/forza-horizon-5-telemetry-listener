import pytest
from src.session_manager import SessionManager

def test_new_session_on_race_start():
    mgr = SessionManager()
    assert mgr.current_session is None
    mgr.update(is_race_on=1, lap_number=1, timestamp_ms=1000,
               car_ordinal=42, car_class=5, car_performance_index=800,
               drivetrain_type=2, distance_traveled=0.0,
               position_x=0.0, position_y=0.0, position_z=0.0)
    assert mgr.current_session is not None
    assert mgr.current_session["car_ordinal"] == 42
    assert mgr.current_session["total_laps"] == 0
    assert mgr.current_lap == 1

def test_lap_transition():
    mgr = SessionManager()
    mgr.update(is_race_on=1, lap_number=1, timestamp_ms=1000,
               car_ordinal=42, car_class=5, car_performance_index=800,
               drivetrain_type=2, distance_traveled=0.0,
               position_x=0.0, position_y=0.0, position_z=0.0)
    assert mgr.lap_just_completed is False
    mgr.update(is_race_on=1, lap_number=2, timestamp_ms=62000,
               car_ordinal=42, car_class=5, car_performance_index=800,
               drivetrain_type=2, distance_traveled=4500.0,
               position_x=10.0, position_y=0.0, position_z=20.0)
    assert mgr.lap_just_completed is True
    assert mgr.current_session["total_laps"] == 1
    assert len(mgr.completed_laps) == 1
    assert mgr.completed_laps[0]["lap_no"] == 1

def test_session_ends_on_race_stop():
    mgr = SessionManager()
    mgr.update(is_race_on=1, lap_number=1, timestamp_ms=1000,
               car_ordinal=42, car_class=5, car_performance_index=800,
               drivetrain_type=2, distance_traveled=0.0,
               position_x=0.0, position_y=0.0, position_z=0.0)
    session_id = mgr.current_session["session_id"]
    mgr.update(is_race_on=0, lap_number=1, timestamp_ms=65000,
               car_ordinal=42, car_class=5, car_performance_index=800,
               drivetrain_type=2, distance_traveled=4500.0,
               position_x=0.0, position_y=0.0, position_z=0.0)
    assert mgr.current_session is None
    assert len(mgr.ended_sessions) == 1
    assert mgr.ended_sessions[0]["session_id"] == session_id

def test_position_tracking_per_lap():
    mgr = SessionManager()
    mgr.update(is_race_on=1, lap_number=1, timestamp_ms=1000,
               car_ordinal=42, car_class=5, car_performance_index=800,
               drivetrain_type=2, distance_traveled=0.0,
               position_x=100.0, position_y=5.0, position_z=200.0)
    mgr.update(is_race_on=1, lap_number=1, timestamp_ms=1016,
               car_ordinal=42, car_class=5, car_performance_index=800,
               drivetrain_type=2, distance_traveled=10.0,
               position_x=110.0, position_y=5.0, position_z=210.0)
    assert len(mgr.current_lap_positions) == 2
    assert mgr.current_lap_positions[0] == (100.0, 5.0, 200.0)
