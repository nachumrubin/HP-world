# Hogwarts From Above — Game Design Document

## Vision
A free-roam broom-flying experience over a living Hogwarts — castle & grounds, Forbidden Forest, Black Lake and the
Quidditch pitch — built with **Blender (assets) + Unreal Engine 5 (world, gameplay)**. The player simply flies,
observes and discovers. The emphasis is fan-service detail: the world must feel inhabited and full of canon references.

**Assumptions (adjust if wrong):** UE 5.4+, solo/small indie team, PC first, film-inspired look blended with
book-only details as "Easter eggs", personal/non-commercial fan project (Warner Bros. IP — cannot be sold or
use extracted film/game assets; all assets made from scratch).

---

## 1. Core Experience
- **Pillars:** (1) *The joy of flight* — flying must feel great in the first 10 seconds. (2) *A living world* —
  everywhere you look, something is happening. (3) *Reward curiosity* — every corner hides a canon detail.
- **No fail state.** A relaxed, exploratory "magical tourism" game. Optional light goals (collectibles, "spot the
  creature" journal) give structure without pressure.
- **Session start:** player kicks off from the Quidditch pitch broom shed at golden hour; Madam Hooch-style
  whistle; first lift-off sweeps over the stands toward the castle (scripted "wow" reveal, then full control).

## 2. Flight System (UE5, C++ + Blueprint)
- Custom `UBroomMovementComponent` (not CharacterMovement): arcade-sim hybrid — momentum, banking, pitch, gentle
  auto-level, speed tiers (hover / cruise / boost "Firebolt dive").
- Feel: camera lag + FOV widening with speed, wind audio rising with velocity, robe/scarf cloth sim, Niagara
  speed streaks, dive-pull-up "Wronski Feint" G-force camera shake.
- Hover mode near ground/water: skim the Black Lake surface leaving a wake; touch treetops in the forest.
- Soft boundaries: beyond the map edge, mist thickens and a gentle wind pushes you back (in-world, not a wall).
- **Brooms (unlockable cosmetics + stats):** Cleansweep Seven, Comet 260, Nimbus 2000, Nimbus 2001, Firebolt.
- Input: gamepad first, keyboard/mouse, optional VR later (comfort vignette).
- Photo mode (free cam, filters: "Daily Prophet" B&W, moving-photo GIF capture).

## 3. World Layout (≈ 4×4 km World Partition map)
Use UE5 **World Partition + Nanite + Lumen**, Landscape with layered materials, PCG framework for foliage/rocks.

| Zone | Key landmarks |
|---|---|
| **Hogwarts Castle** | Great Hall (enchanted ceiling visible through windows at night), Astronomy Tower, Gryffindor/Ravenclaw towers, Clock Tower & courtyard, Viaduct, Covered Bridge, Boathouse, Owlery, Greenhouses, Hospital Wing, Entrance courtyard with fountain, Moving staircases glimpsed through windows |
| **Grounds** | Hagrid's hut + pumpkin patch + Fang, Whomping Willow, Stone Circle, Training grounds, Herbology gardens, Hogwarts gates with winged boars, Black Lake shore, Dumbledore's white tomb (optional, post-HBP setting toggle) |
| **Forbidden Forest** | Dense ancient canopy, Centaur glade, Aragog's hollow (spider webs, Acromantulas), unicorn clearing with silver blood pool, Thestral clearing, Ford Anglia lurking wild, Grawp's cave |
| **Black Lake** | Giant Squid, Grindylows, Merpeople village (visible near surface/underwater glimpse), Durmstrang ship (Triwizard setting toggle), Hogwarts boats with first-years |
| **Quidditch Pitch** | Tall house-coloured stands, hoops, team banners, live match |
| **Periphery** | Hogsmeade silhouette & station with Hogwarts Express steaming in, Shrieking Shack on the hill, mountains & Scottish highlands skybox, Beauxbatons carriage + Abraxan horses (Triwizard toggle) |

**Scale note:** canon Hogwarts is inconsistent; build a "film-truthful" scale (~ castle 600 m wide) tuned for flight
pacing — every landmark visible from altitude, ~30–60 s of flight between major zones.

## 4. A Living World — Systems
- **Mass Entity / MassAI** for crowds (students, owls, birds) — hundreds of agents cheaply; full Skeletal-mesh
  actors only near the player (LOD handoff).
- **Smart Objects** for activities (benches, chess tables, greenhouse beds); **State Trees** for creature behaviour.
- **Day/night + weather cycle** (accelerated, ~24 min = 1 day): schedules drive what NPCs do.
- **Seasons/Era presets** (selectable at start): Autumn term (Sept), Halloween (giant pumpkins, bats), Christmas
  (snow, 12 Great Hall trees, carollers), Triwizard year (ships, carriages, dragon enclosure), Spring exams.

### Students & Staff
- Students in house robes walking between castle & greenhouses, crossing the viaduct with books, sitting by the
  lake, wizard chess in the courtyard, Gobstones, practising Wingardium Leviosa (floating feathers), a group of
  first-years following a prefect, the Weasley twins setting off Filibuster fireworks, Neville chasing Trevor
  the toad, Luna barefoot looking for Nargles (lost shoes on a tree branch).
- Staff vignettes: Hagrid tending pumpkins / carrying a crossbow to the forest, Professor Sprout in the
  greenhouses (Mandrake pots), Filch & Mrs Norris patrolling, McGonagall as tabby cat on a wall, Dumbledore on
  the Astronomy Tower at night, Hooch refereeing.
- **Reactive:** students look up, point and wave as you fly low; occasional "Oi! Get down from there!" from Filch.

### Sky
- **Owls** — flocks commuting to/from the Owlery, morning post delivery swarm flying into the Great Hall, Hedwig
  (unique snowy owl) occasionally flies alongside the player, Errol crashing into a window.
- Thestrals pulling carriages (visible only after the "Thestral Clearing" collectible — canon nod to seeing death),
  Hippogriffs (Buckbeak flyby — bow to him to unlock a ride segment), the Flying Ford Anglia chase event,
  Hogwarts Express on the viaduct-style bridge (Glenfinnan-like), the Dark Mark / Fawkes rare events, Dementors
  over the lake in a "Prisoner of Azkaban" weather preset (frost spreads on the screen edges).
- Other broom-flyers: students practising, a lost Golden Snitch zipping past you anywhere in the world.

### Forbidden Forest
- Centaurs (Firenze, Bane) — patrol and stargaze in their glade; firing a warning arrow if you fly too low.
- Unicorns (adult silver, foals gold), Thestrals, Acromantulas (Aragog's hollow — fear-inducing ambience),
  Bowtruckles on wand-wood trees, Nifflers digging for shiny things, Blast-Ended Skrewts near Hagrid's,
  Fluffy's distant howl, Grawp, Fire-crabs; will-o'-the-wisp fireflies at night.

### Black Lake
- Giant Squid surfacing & tickling students' feet, waving tentacles, playing catch; Grindylows; Merpeople singing
  (muffled "Come seek us where our voices sound" if you skim close); Kelpie disguise; first-year boat crossing at
  dusk on the "Sorting Night" preset with lantern-lit boats.

### Quidditch Match
- Full 14-player AI match (Gryffindor vs Slytherin default, any pairing selectable) on a loop with real rules:
  Quaffle passing, Bludgers chasing players, Beaters, Keepers, Seeker hunt for the Snitch, score boards update,
  crowd chants & house banners, Lee Jordan-style commentary (original voice lines).
- Player can hover in the stands or fly through the pitch; **optional mini-game**: join as Seeker and catch the
  Snitch before the AI Seeker.
- Signature moves animated: Wronski Feint, Sloth Grip Roll, Porskoff Ploy.

## 5. Fan-Treat Detail Catalogue (→ `docs/LORE_CHECKLIST.md`)
Tiered checklist so detail work is tracked, not forgotten:
- **Tier A (must-have):** Owlery traffic, Hedwig, Whomping Willow swatting birds, Giant Squid, centaurs, unicorns,
  Hagrid's hut chimney smoke, Great Hall floating candles visible through windows, house banners, Quidditch match.
- **Tier B (delight):** Peeves throwing water balloons from a window, Moaning Myrtle's flooded bathroom window,
  the Fat Lady portrait glow, Room of Requirement door appearing on a wall, Marauder's Map footprints UI overlay
  ("I solemnly swear…" toggles a parchment minimap), suits of armour singing carols at Christmas, Nearly Headless
  Nick and ghosts drifting through walls at night, Fawkes in Dumbledore's tower window.
- **Tier C (deep cuts):** Hagrid's Norbert crate, Mandrake shrieks near greenhouses, Ford Anglia in the forest,
  Trevor the toad loose, chocolate frog cards as collectibles (find all 101 famous wizards), Luna's shoes,
  Gilderoy Lockhart's Valentine dwarves (Feb preset), Patronus stag at the lake at night, Mirror-like reflections.
- **Audio:** original score inspired by (not copied from) the film mood — celesta motifs, choir, strings; layered
  ambient beds per zone.

## 6. Collectibles & Light Progression
- **Chocolate Frog Cards**, **Golden Snitches** (hidden flying), **Creature Journal** (Newt Scamander style — photograph
  creatures to fill entries; reading pages = lore), **Owl post letters**, **House points** for stunts (flying through
  the clock-tower gears, under the viaduct arches, through hoops). Unlocks: brooms, robes/house scarves, presets.

## 7. Asset Pipeline (Blender → UE5)
- **Modular kits** for the castle: walls, towers, turrets, buttresses, windows, roofs (Blender, trim sheets +
  tiling materials). Assemble in UE with Level Instances / Packed Level Actors; Nanite for all static meshes.
- Hero creatures (Squid, centaur, hippogriff, thestral, unicorn, acromantula, owl) modelled & rigged in Blender
  (Rigify), exported FBX → UE skeletal meshes; animate in Blender or with UE Control Rig. Use **Metahuman** as base
  for human NPCs + custom robes (Chaos Cloth).
- Terrain: Gaea/World Machine or Blender heightmap → UE Landscape; Megascans + PCG for rocks/forest.
- Water: UE Water plugin (lake, waterfall from the castle cliff), FluidFlux optional.
- Naming/folder convention: `Content/HPW/{Characters,Creatures,Environment/Castle,...}`, `SM_`, `SK_`, `M_`, `MI_`, `T_`.
- Source control: Git LFS (or Perforce/Diversion once binaries grow). `.gitattributes` for `*.uasset *.umap *.blend *.fbx`.

## 8. Tech Architecture (UE5)
- Modules: `HPWorld` (core), `HPFlight` (broom), `HPLivingWorld` (schedules, Mass crowds, time-of-day),
  `HPQuidditch` (match sim), `HPCreatures` (State Trees), `HPCollectibles`, `HPUI` (Marauder's Map, journal).
- `UTimeOfDaySubsystem` + `UWorldPresetSubsystem` (season/era) broadcast events consumed by NPC schedules.
- Performance budget: 60 fps on RTX 3070 @1440p; aggressive HLODs for castle from altitude; NPCs culled by
  significance manager.

## 9. Milestones
1. **M0 – Flight prototype (3–4 wks):** greybox terrain, broom movement, camera, speed FX. *Gate: flying is fun.*
2. **M1 – Greybox world (4–6 wks):** all zones blocked out, scale tested by flight time, landmarks readable.
3. **M2 – Castle art pass (8–12 wks):** modular kit, Great Hall, towers, viaduct, Owlery, Lumen lighting & time of day.
4. **M3 – Living world v1 (6–8 wks):** Mass students, owls, Squid, centaurs, unicorns, Hagrid; schedules.
5. **M4 – Quidditch (6 wks):** match sim, crowd, commentary, Seeker mini-game.
6. **M5 – Fan detail pass (ongoing):** work through LORE_CHECKLIST tiers A→C, collectibles, presets, audio.
7. **M6 – Polish & perf:** HLOD, optimisation, photo mode, accessibility (motion comfort, subtitles).

