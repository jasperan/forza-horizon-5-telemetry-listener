"""TelemetryHub: async pipeline tying UDP reception, parsing, session tracking,
WebSocket broadcasting, coaching, and DB writing together."""

import asyncio
import logging

from src.data_packet import ForzaDataPacket
from src.session_manager import SessionManager
from src.ws_manager import WSManager
from src.db_writer import BatchedDBWriter

logger = logging.getLogger(__name__)

# Fields that SessionManager.update() needs from a parsed packet dict.
_SESSION_FIELD_MAP = {
    "is_race_on": "is_race_on",
    "lap_no": "lap_number",
    "timestamp_ms": "timestamp_ms",
    "car_ordinal": "car_ordinal",
    "car_class": "car_class",
    "car_performance_index": "car_performance_index",
    "drivetrain_type": "drivetrain_type",
    "dist_traveled": "distance_traveled",
    "position_x": "position_x",
    "position_y": "position_y",
    "position_z": "position_z",
}


class UDPProtocol(asyncio.DatagramProtocol):
    """Thin asyncio datagram protocol that forwards raw bytes to the hub."""

    def __init__(self, hub: "TelemetryHub") -> None:
        self.hub = hub

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        asyncio.ensure_future(self.hub.on_packet(data))

    def error_received(self, exc: Exception) -> None:
        logger.error("UDP protocol error: %s", exc)


class TelemetryHub:
    """Central pipeline: UDP -> parse -> session -> broadcast -> coach -> DB."""

    def __init__(
        self,
        udp_port: int = 65530,
        db_pool=None,
        batch_size: int = 60,
        mode: str = "race",
    ) -> None:
        self.udp_port = udp_port
        self.mode = mode

        self.session_mgr = SessionManager()
        self.ws_mgr = WSManager()
        self.db_writer = BatchedDBWriter(pool=db_pool, batch_size=batch_size)

        self.coach_engine = None  # set externally (CoachEngine instance)
        self.car_dna = None       # set externally (CarDNA instance)
        self.llm_coach = None     # set externally (LLMCoach instance)
        self.packet_count: int = 0
        self._recent_alerts: list = []

    # -- packet parsing -------------------------------------------------------

    def process_packet(self, data: bytes) -> dict | None:
        """Parse raw bytes via ForzaDataPacket, return dict or None on error."""
        try:
            pkt = ForzaDataPacket(data)
            return pkt.to_dict()
        except Exception:
            return None

    # -- session field extraction ---------------------------------------------

    @staticmethod
    def _session_fields(packet: dict) -> dict:
        """Extract the keyword args that SessionManager.update() expects."""
        return {
            target_key: packet[src_key]
            for src_key, target_key in _SESSION_FIELD_MAP.items()
            if src_key in packet
        }

    # -- main async pipeline --------------------------------------------------

    async def on_packet(self, data: bytes) -> None:
        """Full pipeline: parse -> session -> broadcast -> coach -> DB."""
        packet = self.process_packet(data)
        if packet is None:
            return

        session_fields = self._session_fields(packet)

        # In race mode, if the race flag is off we still feed session_mgr
        # (so it can detect race-end transitions) but skip everything else.
        if self.mode == "race" and packet["is_race_on"] == 0:
            self.session_mgr.update(**session_fields)
            return

        self.packet_count += 1

        # Update session / lap state
        self.session_mgr.update(**session_fields)

        # Inject session_id when a session is active
        if self.session_mgr.current_session is not None:
            packet["session_id"] = self.session_mgr.current_session["session_id"]

        # Broadcast raw telemetry
        await self.ws_mgr.broadcast("telemetry", packet)

        # Coaching alerts
        if self.coach_engine is not None:
            alerts = self.coach_engine.evaluate(packet, self.session_mgr)
            if alerts:
                self._recent_alerts.extend(alerts)
                await self.ws_mgr.broadcast("coach", {"type": "alerts", "alerts": alerts})

        # Buffer for DB
        self.db_writer.add(packet)

        # Lap completion handling
        if self.session_mgr.lap_just_completed:
            last_lap = self.session_mgr.completed_laps[-1]
            lap_doc = {
                "session_id": packet.get("session_id"),
                "lap": last_lap,
            }
            self.db_writer.save_document("completed_laps", lap_doc)
            await self.ws_mgr.broadcast(
                "coach",
                {"type": "lap_complete", "lap": last_lap},
            )

            # LLM coaching tip on lap completion
            if hasattr(self, 'llm_coach') and self.llm_coach and self.llm_coach.enabled:
                tip = await self.llm_coach.generate_tip(
                    alerts=self._recent_alerts,
                    lap_stats={"lap_no": last_lap["lap_no"], "lap_time": last_lap.get("lap_time", last_lap.get("lap_time_ms", 0))},
                )
                if tip:
                    await self.ws_mgr.broadcast("coach", tip)
            self._recent_alerts = []

    # -- UDP server -----------------------------------------------------------

    async def start_udp(self) -> asyncio.DatagramTransport:
        """Create and return an asyncio datagram endpoint on 0.0.0.0:udp_port."""
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: UDPProtocol(self),
            local_addr=("0.0.0.0", self.udp_port),
        )
        logger.info("UDP listener started on 0.0.0.0:%d", self.udp_port)
        return transport
