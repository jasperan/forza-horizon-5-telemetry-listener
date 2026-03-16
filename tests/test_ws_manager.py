import pytest
import asyncio
from unittest.mock import AsyncMock
from src.ws_manager import WSManager

@pytest.mark.asyncio
async def test_connect_and_disconnect():
    mgr = WSManager()
    ws = AsyncMock()
    await mgr.connect(ws, channel="telemetry")
    assert len(mgr.connections["telemetry"]) == 1
    await mgr.disconnect(ws, channel="telemetry")
    assert len(mgr.connections["telemetry"]) == 0

@pytest.mark.asyncio
async def test_broadcast_sends_to_all():
    mgr = WSManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await mgr.connect(ws1, channel="telemetry")
    await mgr.connect(ws2, channel="telemetry")
    data = {"type": "telemetry", "speed": 67.4}
    await mgr.broadcast("telemetry", data)
    ws1.send_json.assert_called_once_with(data)
    ws2.send_json.assert_called_once_with(data)

@pytest.mark.asyncio
async def test_broadcast_removes_dead_connections():
    mgr = WSManager()
    ws_alive = AsyncMock()
    ws_dead = AsyncMock()
    ws_dead.send_json.side_effect = Exception("connection closed")
    await mgr.connect(ws_alive, channel="telemetry")
    await mgr.connect(ws_dead, channel="telemetry")
    await mgr.broadcast("telemetry", {"speed": 50.0})
    assert len(mgr.connections["telemetry"]) == 1
    ws_alive.send_json.assert_called_once()

@pytest.mark.asyncio
async def test_separate_channels():
    mgr = WSManager()
    ws_tel = AsyncMock()
    ws_coach = AsyncMock()
    await mgr.connect(ws_tel, channel="telemetry")
    await mgr.connect(ws_coach, channel="coach")
    await mgr.broadcast("telemetry", {"speed": 50.0})
    ws_tel.send_json.assert_called_once()
    ws_coach.send_json.assert_not_called()
