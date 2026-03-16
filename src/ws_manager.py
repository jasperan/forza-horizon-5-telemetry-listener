"""WebSocket connection manager for multi-channel telemetry broadcasting."""

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class WSManager:
    """Manages WebSocket connections across multiple named channels.

    Channels isolate different data streams (e.g. 'telemetry', 'coach')
    so broadcasts only reach subscribers of that specific channel.
    """

    def __init__(self) -> None:
        self.connections: dict[str, list] = defaultdict(list)

    async def connect(self, websocket: Any, channel: str = "telemetry") -> None:
        """Register a websocket on the given channel."""
        self.connections[channel].append(websocket)
        logger.info(
            "Client connected to channel '%s' (total: %d)",
            channel,
            len(self.connections[channel]),
        )

    async def disconnect(self, websocket: Any, channel: str = "telemetry") -> None:
        """Remove a websocket from the given channel."""
        try:
            self.connections[channel].remove(websocket)
        except ValueError:
            pass
        logger.info(
            "Client disconnected from channel '%s' (total: %d)",
            channel,
            len(self.connections[channel]),
        )

    async def broadcast(self, channel: str, data: dict) -> None:
        """Send data to every connection on a channel, pruning dead ones."""
        dead: list = []
        for ws in self.connections[channel]:
            try:
                await ws.send_json(data)
            except Exception:
                logger.warning("Removing dead connection from channel '%s'", channel)
                dead.append(ws)
        for ws in dead:
            self.connections[channel].remove(ws)

    @property
    def client_count(self) -> dict[str, int]:
        """Return a dict of channel name to active connection count."""
        return {ch: len(conns) for ch, conns in self.connections.items()}
