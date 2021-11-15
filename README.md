# forza-horizon-5-telemetry-listener
Telemetry Listener in Python for Forza Horizon 4 and Forza Horizon 5

![telemetry](https://static.gosunoob.com/img/1/2021/11/Telemetry-Forza-Horizon-5-How-to-Turn-on-Telemetry.jpg?raw=true)



## Requirements

You need an Oracle Autonomous JSON Database as the official supporting database for this project. We'll connect to the database using TLS instead of mutual-TLS which frees us from using a wallet to connect the database.

To connect to the database securely, you'll need a username, password and DSN. All this information shall be inside a config.yaml file. You will need this structure:

```yaml
db:
  username: xxxx
  password: xxxx
  dsn: xxxx
```

After having this YAML file and the database set up with TLS, we're good to go.

## I don't have an Autonomous DB, what can I do?

Don't worry. If you sign up for Oracle Cloud you can create an Always free Autonomous DB with 1 OCPU and 1TB storage for free **FOREVER**. 

## How to Run

### Manually

To only log data in a race, 
```
python listener.py --verbose --mode "race"
```

To log all data, whether or not in a race,
```
python listener.py --verbose --mode "always"
```

### Using Docker

First, you will need to build the image.

```
docker build --pull --rm -f Dockerfile -t fh5 .
```

To only log data in a race, 
```
docker run -p 65530:65530/udp --rm fh5:latest --verbose --mode "race"
```

To log all data, whether or not in a race,
```
docker run -p 65530:65530/udp --rm fh5:latest --verbose --mode "always"
```


## Data Structure

Data is output in the following structure:

- s32 IsRaceOn; // = 1 when race is on. = 0 when in menus/race stopped …
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

# How to Run