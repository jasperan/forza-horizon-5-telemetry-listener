# forza-horizon-5-telemetry-listener

Real-time telemetry platform for Forza Horizon 4/5. Live dashboard, AI driving coach, track mapping, car DNA fingerprinting.

![telemetry](https://static.gosunoob.com/img/1/2021/11/Telemetry-Forza-Horizon-5-How-to-Turn-on-Telemetry.jpg?raw=true)

## What's New (v2.0)

The old listener just piped UDP packets into a database. v2.0 bolts on a complete telemetry platform:

- **F1-style browser dashboard** with full and compact (OBS overlay) modes
- **AI driving coach** with heuristic alerts: tire temps, traction loss, gear selection, suspension bottoming
- **Optional LLM coaching** via Ollama (sends batched alerts, gets back natural-language tips)
- **Track auto-mapping** from position telemetry with deterministic track hashing
- **Car DNA fingerprinting**: 6-dimensional performance vectors for similarity search
- **Session and lap tracking** with 3-sector analysis and performance vectors
- **WebSocket streaming** for telemetry and coach channels
- **REST API** for sessions, cars, and platform status
- **Works without Oracle DB** (`--no-db` mode): just the dashboard, coach, and analytics

## Quick Start

```bash
# Clone and install
git clone https://github.com/jasperan/forza-horizon-5-telemetry-listener.git
cd forza-horizon-5-telemetry-listener
pip install -r requirements.txt

# Run without database (dashboard only)
python app.py --no-db

# Open dashboard
# http://localhost:8080
```

Point your Forza Horizon telemetry output to your machine's IP on port **65530** (UDP). Data starts flowing the moment you hit the track.

## With Oracle Database

For persistence, history, and vector search you'll want Oracle Autonomous JSON Database backing the platform. It's the official storage layer.

Don't have one? Sign up for Oracle Cloud and create an **Always Free** Autonomous DB: 1 OCPU, 1TB storage, free forever.

### Setup

1. Download your database wallet and drop the contents into the `./wallet` directory.

2. Edit `sqlnet.ora` inside the wallet to point at the correct directory. If running via Docker:
   ```
   DIRECTORY="/home/appuser/wallets/Wallet_forza"
   ```
   If running locally, use the wallet's actual path on your machine.

3. Create `config.yaml` in the project root:
   ```yaml
   db:
     username: xxxx
     password: xxxx
     dsn: xxxx
   WALLET_DIR: directory_for_wallet_uncompressed
   ```
   `WALLET_DIR` is relative to your `$HOME`. For example, if the wallet lives at `/home/you/wallets/my_wallet`:
   ```yaml
   WALLET_DIR: wallets/my_wallet
   ```

4. Run:
   ```bash
   python app.py --verbose
   ```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `65530` | UDP listen port for telemetry data |
| `--web-port` | `8080` | HTTP/WebSocket port for dashboard and API |
| `--mode` | `race` | `race` = only process when IsRaceOn=1; `always` = process all packets |
| `--verbose` | off | Enable debug logging |
| `--no-db` | off | Run without Oracle DB (dashboard, coach, and analytics still work) |
| `--enable-llm` | off | Enable Ollama LLM coaching (requires Ollama running locally) |
| `--config` | `config.yaml` | Path to database config file |

## Dashboard

The browser dashboard at `http://localhost:8080` has two modes:

**Full mode** shows everything: RPM and speed gauges (canvas-rendered), live track map, tire temperatures, suspension travel, lap times, and the AI coach feed. It's the whole pit wall in a browser tab.

**Compact mode** strips it down to gear, speed, throttle/brake bars, lap delta, and coach messages. Built for OBS overlays on stream.

Toggle between them by pressing **M** on your keyboard, or load compact mode directly with `?mode=compact` in the URL.

## AI Coach

The coach engine runs 4 heuristic rules against every telemetry packet:

| Rule | What it catches |
|------|----------------|
| **Tire overheat** | Any tire exceeding 105% of its running average temp for 5+ consecutive packets |
| **Traction loss** | Combined tire slip > 1.0 for 3+ consecutive packets (you're sliding) |
| **Gear selection** | Upshift detected below 80% of max RPM (leaving power on the table) |
| **Suspension bottoming** | Normalized suspension travel > 0.95 (you're slamming into the bump stops) |

Alerts stream to the dashboard in real time via WebSocket. Each rule has a cooldown so you don't get spammed.

### LLM Coaching

Pass `--enable-llm` to send batched alerts to a local Ollama instance. The LLM (default model: `qwen3.5:35b-a3b`) acts as a racing engineer, returning a single coaching tip in under 30 words. Requires [Ollama](https://ollama.com/) running on `localhost:11434`.

## API Endpoints

### REST

| Method | Path | Returns |
|--------|------|---------|
| `GET` | `/api/status` | Platform status: packet count, DB connection, active session, WS client count |
| `GET` | `/api/sessions` | List of ended race sessions |
| `GET` | `/api/sessions/{id}` | Detail for a specific session |
| `GET` | `/api/cars` | All car DNA profiles collected this run |
| `GET` | `/api/cars/{ordinal}` | DNA profile for a specific car (by CarOrdinal) |

### WebSocket

| Path | Channel |
|------|---------|
| `/ws/telemetry` | Full telemetry packet stream (every parsed UDP packet) |
| `/ws/coach` | AI coach alerts and LLM tips |

Connect any WebSocket client to consume data. The dashboard uses these same channels.

## Docker

```bash
docker build -t forza-telemetry .
docker run -p 65530:65530/udp -p 8080:8080 forza-telemetry --mode race
```

The container ships with Oracle Instant Client for thick-mode DB connections. Pass `--no-db` if you don't need persistence:

```bash
docker run -p 65530:65530/udp -p 8080:8080 forza-telemetry --no-db
```

## Data Structure

The Forza telemetry packet contains 84 fields. Here's the full layout:

- s32 IsRaceOn; // = 1 when race is on. = 0 when in menus/race stopped
- u32 TimestampMS; //Can overflow to 0 eventually
- f32 EngineMaxRpm;
- f32 EngineIdleRpm;
- f32 CurrentEngineRpm;
- f32 AccelerationX; //In the car's local space; X = right, Y = up, Z = forward
- f32 AccelerationY;
- f32 AccelerationZ;
- f32 VelocityX; //In the car's local space; X = right, Y = up, Z = forward
- f32 VelocityY;
- f32 VelocityZ;
- f32 AngularVelocityX; //In the car's local space; X = pitch, Y = yaw, Z = roll
- f32 AngularVelocityY;
- f32 AngularVelocityZ;
- f32 Yaw;
- f32 Pitch;
- f32 Roll;
- f32 NormalizedSuspensionTravelFrontLeft; // Suspension travel normalized: 0.0f = max stretch; 1.0 = max compression
- f32 NormalizedSuspensionTravelFrontRight;
- f32 NormalizedSuspensionTravelRearLeft;
- f32 NormalizedSuspensionTravelRearRight;
- f32 TireSlipRatioFrontLeft; // Tire normalized slip ratio, = 0 means 100% grip and |ratio| > 1.0 means loss of grip.
- f32 TireSlipRatioFrontRight;
- f32 TireSlipRatioRearLeft;
- f32 TireSlipRatioRearRight;
- f32 WheelRotationSpeedFrontLeft; // Wheel rotation speed radians/sec.
- f32 WheelRotationSpeedFrontRight;
- f32 WheelRotationSpeedRearLeft;
- f32 WheelRotationSpeedRearRight;
- s32 WheelOnRumbleStripFrontLeft; // = 1 when wheel is on rumble strip, = 0 when off.
- s32 WheelOnRumbleStripFrontRight;
- s32 WheelOnRumbleStripRearLeft;
- s32 WheelOnRumbleStripRearRight;
- f32 WheelInPuddleDepthFrontLeft; // = from 0 to 1, where 1 is the deepest puddle
- f32 WheelInPuddleDepthFrontRight;
- f32 WheelInPuddleDepthRearLeft;
- f32 WheelInPuddleDepthRearRight;
- f32 SurfaceRumbleFrontLeft; // Non-dimensional surface rumble values passed to controller force feedback
- f32 SurfaceRumbleFrontRight;
- f32 SurfaceRumbleRearLeft;
- f32 SurfaceRumbleRearRight;
- f32 TireSlipAngleFrontLeft; // Tire normalized slip angle, = 0 means 100% grip and |angle| > 1.0 means loss of grip.
- f32 TireSlipAngleFrontRight;
- f32 TireSlipAngleRearLeft;
- f32 TireSlipAngleRearRight;
- f32 TireCombinedSlipFrontLeft; // Tire normalized combined slip, = 0 means 100% grip and |slip| > 1.0 means loss of grip.
- f32 TireCombinedSlipFrontRight;
- f32 TireCombinedSlipRearLeft;
- f32 TireCombinedSlipRearRight;
- f32 SuspensionTravelMetersFrontLeft; // Actual suspension travel in meters
- f32 SuspensionTravelMetersFrontRight;
- f32 SuspensionTravelMetersRearLeft;
- f32 SuspensionTravelMetersRearRight;
- s32 CarOrdinal; //Unique ID of the car make/model
- s32 CarClass; //Between 0 (D -- worst cars) and 7 (X class -- best cars) inclusive
- s32 CarPerformanceIndex; //Between 100 (slowest car) and 999 (fastest car) inclusive
- s32 DrivetrainType; //Corresponds to EDrivetrainType; 0 = FWD, 1 = RWD, 2 = AWD
- s32 NumCylinders; //Number of cylinders in the engine
- f32 PositionX; //Position (meters)
- f32 PositionY;
- f32 PositionZ;
- f32 Speed; // meters per second
- f32 Power; // watts
- f32 Torque; // newton meter
- f32 TireTempFrontLeft;
- f32 TireTempFrontRight;
- f32 TireTempRearLeft;
- f32 TireTempRearRight;
- f32 Boost;
- f32 Fuel;
- f32 DistanceTraveled;
- f32 BestLap;
- f32 LastLap;
- f32 CurrentLap;
- f32 CurrentRaceTime;
- u16 LapNumber;
- u8 RacePosition;
- u8 Accel;
- u8 Brake;
- u8 Clutch;
- u8 HandBrake;
- u8 Gear;
- s8 Steer;
- s8 NormalizedDrivingLine;
- s8 NormalizedAIBrakeDifference;

## Useful Repositories and Credits

For visualizing the data present here, you can use [this repo](https://github.com/austinbaccus/forza-map-visualization).
Inspired by [nettrom's repository](https://github.com/nettrom/forza_motorsport) for initial support of his DataPacket class which I later modified.
