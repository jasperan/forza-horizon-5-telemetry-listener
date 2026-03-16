"""Tests for the FastAPI REST and WebSocket endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.api.routes import create_app


@pytest.fixture
def client():
    """TestClient with hub=None (graceful-degradation mode)."""
    app = create_app(hub=None, db_pool=None)
    return TestClient(app)


def test_status_endpoint(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "db_connected" in body
    assert body["db_connected"] is False
    assert body["packet_count"] == 0
    assert body["ws_clients"] == {}
    assert body["current_session"] is None


def test_sessions_endpoint(client):
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_cars_endpoint(client):
    resp = client.get("/api/cars")
    assert resp.status_code == 200
    assert resp.json() == []


def test_websocket_telemetry(client):
    with client.websocket_connect("/ws/telemetry") as ws:
        ws.send_text("ping")
        # Connection accepted without error; close cleanly.


def test_websocket_coach(client):
    with client.websocket_connect("/ws/coach") as ws:
        ws.send_text("ping")
