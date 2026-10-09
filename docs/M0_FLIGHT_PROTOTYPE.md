# M0 — Flight Prototype

**Goal:** prove that flying a broom is fun before anything else gets built.
**Gate to M1:** three playtesters each fly for 10+ minutes without being asked to, and say the broom "feels right".

## What's in M0

| Piece | Where | Notes |
|---|---|---|
| Flight model | `Source/HPFlight/Public/BroomFlightModel.h`, `Private/BroomFlightModel.cpp` | Plain C++ with no engine dependency, so it can be unit-tested and tuned outside Unreal |
| Movement component | `Source/HPFlight/.../BroomMovementComponent.*` | Feeds the model input and a ground/water trace, then sweeps the pawn and reports collisions back |
| Broom pawn | `Source/HPFlight/.../BroomPawn.*` | Greybox broom and rider, chase camera, input, speed effects |
| Game mode | `Source/HPWorld/.../HPFlightGameMode.*` | Spawns the player on a broom at the PlayerStart |
| Greybox world | `Tools/greybox_layout.json` + `Tools/Unreal/build_greybox_m0.py` | Castle, grounds, forest, lake, pitch, Hogsmeade and mountains, built from engine shapes (~890 actors) |
| Tests | `Tests/FlightModel/` | 19 flight-model unit tests (run in CI) |
| Pacing check | `Tools/layout_report.py` | Checks that the forest, lake and pitch are each 30–60 s from the castle at cruise speed |

## Getting started

1. Install **Unreal Engine 5.4** and a C++ toolchain: Visual Studio 2022 on Windows, Xcode on macOS.
2. Right-click `HPWorld.uproject`, choose **Generate Visual Studio project files** (on macOS: **Generate Xcode project**), then build the `HPWorldEditor` target.
3. Open the project. The `M0_Greybox` map doesn't exist yet, so the editor opens an empty level.
4. Build the greybox: **Tools → Execute Python Script…** → `Tools/Unreal/build_greybox_m0.py`.
   The map is saved to `/Game/HPW/Maps/M0_Greybox`. You can run the script again after editing the layout JSON; it replaces only what it built.
5. Press **Play**. You start hovering beside the broom shed at the Quidditch pitch, facing the castle.

> **Note:** the C++ in this milestone was written without an Unreal install available, so it has not been compiled
> against the engine yet. The flight model itself is compiled and tested in CI. If the first editor build reports
> errors, they will be small API mismatches in `BroomPawn.cpp` or `BroomMovementComponent.cpp`.

## Controls

| Action | Keyboard & mouse | Gamepad |
|---|---|---|
| Steer | Mouse (or A/D, arrow keys) | Left stick |
| Throttle / brake | W / S | Right trigger / left trigger |
| Hover up / down | Space / Left Ctrl | A / B |
| Boost (Firebolt dive) | Left Shift | L3 or RB |
| Look around | — | Right stick |
| Reset to start | R | View / Back |

Stick pitch is flight-sim style (push forward to dive); change it with `bInvertStickPitch` on the pawn. While hovering, pitching up or down raises or lowers the broom.

## How the broom flies

- **Hover → flight:** below about 4.5 m/s the broom hovers. It pivots on the spot and moves up and down directly. Above that speed it flies: it banks into turns and pitch takes effect.
- **Coasting:** with no throttle the broom settles at cruise speed (25 m/s). Brake to a stop and it stays hovering.
- **Dive for speed:** diving trades height for speed and climbing loses speed. A boosted dive reaches about 60 m/s.
- **Automatic pull-up:** close to the ground or water the nose lifts on its own, and it starts earlier the faster you are falling. A full-speed dive becomes a swoop over the grass or lake instead of a crash. You can never get closer than 1.2 m to the surface.
- **Momentum:** velocity follows the nose slightly late, so turns have some drift (`VelocityGrip`).
- **World edge:** beyond 3 km from the castle, a magical wind turns you back. There is also a soft ceiling at 700 m.

## Tuning

Every value is under **BroomMovement → Settings** on the pawn, in m/s, metres and degrees, and can be edited live during Play-In-Editor. Camera feel is on the pawn itself:

| Setting | Default | What it changes |
|---|---|---|
| CruiseSpeed / MaxSpeed / BoostSpeed | 25 / 35 / 55 m/s | Overall pace |
| MaxTurnRate / MaxBankAngle | 65°/s / 55° | How tight turns are and how dramatic the bank looks |
| VelocityGrip | 3.5 | Lower = floatier, more drift |
| DiveGravityScale | 0.55 | How much speed a dive adds |
| PullUpLeadTime | 2 s | How early the ground pull-up starts |
| BaseFieldOfView / MaxFieldOfView | 80° / 105° | How strongly the view widens with speed |
| CameraBankFactor | 0.35 | How much of the bank the camera follows |
| MotionIntensity | 1 | Accessibility: scales FOV widening, shake and chromatic aberration |

To try a change outside the editor, edit the defaults in `FBroomTuning` and rerun the tests:

```sh
cmake -S Tests/FlightModel -B Tests/FlightModel/build && cmake --build Tests/FlightModel/build && ./Tests/FlightModel/build/FlightModelTests
python3 Tools/layout_report.py
```

## Effects hooks (art to add)

The pawn already drives these and does nothing while they are empty:

- **WindAudio:** assign a looping wind sound. Volume and pitch follow speed, and a `Speed` (0..1) parameter is sent for MetaSounds.
- **SpeedStreaks:** a Niagara system attached in front of the camera. It receives a `Speed` (0..1) user float and switches on above 35% speed.
- **WaterWake:** a Niagara spray under the broom, switched on while skimming the Black Lake (anything tagged `Water`).

Speed effects that need no assets are already active: chromatic fringing, vignette, FOV widening and camera shake under high G or on impact.

## Playtest checklist (M0 gate)

- [ ] The first 10 seconds are fun: take off from the broom shed and sweep toward the castle
- [ ] Banked turns around the Astronomy Tower feel controllable at cruise and at boost
- [ ] A full-speed dive into the Black Lake ends in a satisfying skim, not a crash
- [ ] You can thread the viaduct arches and the Quidditch hoops on purpose
- [ ] Mouse and gamepad both feel good; nobody asks for an inverted-controls option you don't have
- [ ] No motion sickness at `MotionIntensity = 1` after 10 minutes (otherwise lower the defaults)
- [ ] Flight times feel right: about 30–60 s from the castle to the forest, lake and pitch

## Next (M1)

Replace the greybox terrain with a sculpted Landscape (castle cliff, lakeshore, forest valley), set up World Partition, and confirm that landmarks are recognisable from the air at real scale.
