# forza-horizon-5-telemetry-listener

## Purpose
Real-time telemetry platform for Forza Horizon 4/5. Listens for UDP packets from the game, stores data in Oracle Autonomous JSON Database, and serves an F1-style browser dashboard with an AI driving coach, track mapping, car DNA fingerprinting, and WebSocket streaming.

## Stack
- **Language**: Python 3
- **Web framework**: FastAPI + Uvicorn (HTTP + WebSocket)
- **Database**: Oracle Autonomous JSON Database via `python-oracledb` (thick mode, wallet-based TLS)
- **Dashboard**: Vanilla JS/CSS/HTML (`dashboard/`)
- **LLM coaching**: Ollama (optional, default model `qwen3.5:35b-a3b`)
- **Config**: `config.yaml` (DB credentials + wallet path)
- **Container**: Docker + Docker Compose

## Commands

### Run
```bash
# No database (dashboard + coach only)
python app.py --no-db

# With Oracle DB
python app.py --verbose

# With LLM coaching
python app.py --no-db --enable-llm
```

### Test
```bash
pytest tests/
pytest tests/test_coach_rules.py  # single module
```

### Docker
```bash
docker build -t forza-telemetry .
docker run -p 65530:65530/udp -p 8080:8080 forza-telemetry --no-db
docker compose up  # full stack with DB support
```

## Layout
```
app.py                  # entrypoint: CLI args, wires all components, starts Uvicorn
listener.py             # UDP listener task
src/
  data_packet.py        # 84-field struct parser (DataPacket)
  telemetry_hub.py      # central bus: fan-out to DB, coach, WS, analytics
  session_manager.py    # lap/sector/session lifecycle
  db_writer.py          # Oracle insert logic
  ws_manager.py         # WebSocket connection manager
  coach/                # AI coaching rules + optional LLM batching
  analytics/            # track mapping, car DNA fingerprinting
  api/                  # FastAPI routers (REST endpoints)
dashboard/
  index.html / app.js / style.css   # browser UI (full + compact OBS modes)
tests/                  # pytest suite, one file per module
wallet/                 # Oracle DB wallet files (not committed)
config.yaml             # DB credentials (not committed)
```

## Conventions
- UDP telemetry arrives on port **65530**; dashboard/API on port **8080** (both configurable via CLI).
- `DataPacket` in `src/data_packet.py` is the canonical struct — all consumers import from there.
- Oracle wallet path in `config.yaml` is relative to `$HOME`; Docker path is `/home/appuser/wallets/Wallet_forza`.
- `--no-db` bypasses all Oracle imports; no `oracledb` calls are made in that path.
- Tests use `pytest-asyncio`; async test functions are decorated with `@pytest.mark.asyncio`.
- No frontend build step — dashboard is plain HTML/JS served statically by FastAPI.
