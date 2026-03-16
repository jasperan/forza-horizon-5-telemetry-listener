"""Forza Telemetry Platform - entry point."""
import argparse
import asyncio
import logging
import sys

import uvicorn

from src.db_writer import create_pool
from src.telemetry_hub import TelemetryHub
from src.coach.engine import CoachEngine
from src.coach.llm_coach import LLMCoach
from src.analytics.car_dna import CarDNACollector
from src.api.routes import create_app


def parse_args():
    p = argparse.ArgumentParser(description="Forza Telemetry Platform")
    p.add_argument("--port", type=int, default=65530, help="UDP listen port (default: 65530)")
    p.add_argument("--web-port", type=int, default=8080, help="HTTP/WS port (default: 8080)")
    p.add_argument("--mode", choices=["race", "always"], default="race",
                   help="'race' = log only during races, 'always' = log everything")
    p.add_argument("--verbose", action="store_true", help="Enable debug logging")
    p.add_argument("--no-db", action="store_true", help="Run without Oracle DB")
    p.add_argument("--enable-llm", action="store_true", help="Enable Ollama LLM coaching")
    p.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    return p.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    logger = logging.getLogger("forza")

    # DB pool
    db_pool = None
    if not args.no_db:
        db_pool = create_pool(config_path=args.config)
        if db_pool:
            logger.info("Oracle DB connected")
        else:
            logger.warning("Oracle DB unavailable, running in dashboard-only mode")

    # Core hub
    hub = TelemetryHub(udp_port=args.port, db_pool=db_pool, mode=args.mode)
    hub.coach_engine = CoachEngine()
    hub.car_dna = CarDNACollector()
    hub.llm_coach = LLMCoach(enabled=args.enable_llm)

    # FastAPI app
    app = create_app(hub=hub, db_pool=db_pool)

    @app.on_event("startup")
    async def startup():
        hub._udp_transport = await hub.start_udp()
        logger.info("Forza Telemetry Platform running")
        logger.info("  UDP listener: port %d", args.port)
        logger.info("  Dashboard:    http://localhost:%d", args.web_port)
        logger.info("  WebSocket:    ws://localhost:%d/ws/telemetry", args.web_port)
        logger.info("  Mode:         %s", args.mode)
        logger.info("  DB:           %s", "connected" if db_pool else "disabled")
        logger.info("  LLM Coach:    %s", "enabled" if args.enable_llm else "disabled")

    @app.on_event("shutdown")
    async def shutdown():
        if hub._udp_transport:
            hub._udp_transport.close()
        if db_pool:
            db_pool.close()

    uvicorn.run(app, host="0.0.0.0", port=args.web_port, log_level="info")


if __name__ == "__main__":
    main()
