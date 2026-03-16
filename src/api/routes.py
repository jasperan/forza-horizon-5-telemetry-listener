"""FastAPI application factory with REST endpoints and WebSocket handlers."""

import os
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

# Resolve dashboard path relative to the project root (two levels up from this file).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DASHBOARD_DIR = os.path.join(_PROJECT_ROOT, "dashboard")


def create_app(hub=None, db_pool=None) -> FastAPI:
    """Build and return a configured FastAPI application.

    Parameters
    ----------
    hub : TelemetryHub | None
        The central telemetry pipeline. When *None* the API still works but
        returns empty/default data for every endpoint.
    db_pool : object | None
        An Oracle DB connection pool (unused directly by routes, but kept for
        status reporting).
    """

    app = FastAPI(title="Forza Telemetry Platform", version="2.0.0")

    # -- REST endpoints -------------------------------------------------------

    @app.get("/api/status")
    async def status():
        if hub is None:
            return {
                "status": "ok",
                "db_connected": db_pool is not None,
                "packet_count": 0,
                "ws_clients": {},
                "current_session": None,
            }
        return {
            "status": "ok",
            "db_connected": db_pool is not None,
            "packet_count": hub.packet_count,
            "ws_clients": hub.ws_mgr.client_count,
            "current_session": hub.session_mgr.current_session,
        }

    @app.get("/api/sessions")
    async def sessions():
        if hub is None:
            return []
        return hub.session_mgr.ended_sessions

    @app.get("/api/sessions/{session_id}")
    async def session_detail(session_id: str):
        if hub is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        for s in hub.session_mgr.ended_sessions:
            if s.get("session_id") == session_id:
                return s
        return JSONResponse({"error": "not found"}, status_code=404)

    @app.get("/api/cars")
    async def cars():
        if hub is None or hub.car_dna is None:
            return []
        return list(hub.car_dna.profiles.values())

    @app.get("/api/cars/{ordinal}")
    async def car_detail(ordinal: int):
        if hub is None or hub.car_dna is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        profile = hub.car_dna.get_profile(ordinal)
        if profile is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return profile

    # -- WebSocket endpoints --------------------------------------------------

    @app.websocket("/ws/telemetry")
    async def ws_telemetry(websocket: WebSocket):
        await websocket.accept()
        if hub is not None:
            await hub.ws_mgr.connect(websocket, "telemetry")
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            if hub is not None:
                await hub.ws_mgr.disconnect(websocket, "telemetry")

    @app.websocket("/ws/coach")
    async def ws_coach(websocket: WebSocket):
        await websocket.accept()
        if hub is not None:
            await hub.ws_mgr.connect(websocket, "coach")
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            if hub is not None:
                await hub.ws_mgr.disconnect(websocket, "coach")

    # -- Static dashboard -----------------------------------------------------

    if os.path.isdir(_DASHBOARD_DIR):

        @app.get("/")
        async def dashboard_root():
            index = os.path.join(_DASHBOARD_DIR, "index.html")
            return FileResponse(index)

        app.mount("/dashboard", StaticFiles(directory=_DASHBOARD_DIR), name="dashboard")

    return app
