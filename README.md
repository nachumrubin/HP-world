# Hogwarts From Above

A Harry Potter fan project: fly a broom freely over a living Hogwarts — the castle and grounds, the Forbidden
Forest, the Black Lake and the Quidditch pitch — full of students, magical creatures and canon details.

- **Engine:** Unreal Engine 5.4+ (World Partition, Nanite, Lumen, Mass AI)
- **Assets:** Blender (modular castle kit, creatures, props)

## Status
**M0 – Flight prototype** in progress: broom flight, chase camera and a greybox Hogwarts.
See [docs/M0_FLIGHT_PROTOTYPE.md](docs/M0_FLIGHT_PROTOTYPE.md) for setup, controls and tuning.

## Docs
- [Game Design Document](docs/GAME_DESIGN.md)
- [Lore & Detail Checklist](docs/LORE_CHECKLIST.md)
- [M0 Flight Prototype](docs/M0_FLIGHT_PROTOTYPE.md)

## Layout
- `HPWorld.uproject`, `Config/`, `Source/` – Unreal project (`HPWorld` game module, `HPFlight` broom flight module)
- `Tests/FlightModel/` – unit tests for the engine-agnostic flight model
- `Tools/` – greybox layout data, the Unreal Python level builder, and the flight-pacing report

## Disclaimer
Non-commercial fan project. Harry Potter and related names are trademarks of Warner Bros. Entertainment Inc.
All assets in this repository are original; no assets are extracted from films or official games.
