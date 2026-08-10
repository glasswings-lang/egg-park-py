# The Bird House — Game Design Document
*Drafted 2026-05-26 in collaboration with an AI agent and Rozaya*

---

## Overview

The Bird House is an audio-first sanctuary game. You tend a living space — an indoor incubation room and an expanding outdoor territory — where birds hatch, grow, and thrive over time. There is no failure state, no timer pressure, no arcade mechanics. The game rewards presence, patience, and gentle stewardship.

Built on the same foundation as Egg Park (Python, pyglet, OpenAL HRTF, accessible_output2) but with a fundamentally different emotional register. This is a place you inhabit, not a challenge you complete.

---

## Core Loop

1. **Tend the incubator** — turn eggs, monitor temperature and humidity, candle to check development
2. **Wander outside** — explore territory, gather nesting materials, listen to your birds
3. **Expand the space** — use gathered materials to grow the territory and improve the incubator
4. **Watch the flock grow** — bonded pairs lay eggs in nests, new birds hatch, the space fills with life
5. **Delegate to helpers** — as the sanctuary grows, NPC assistants take on roles, reporting to you as you wander

---

## Starting State

- 12 eggs in the incubator
- Small indoor incubation space
- Small outdoor territory
- Basic incubator (temperature and humidity drift slightly without tending)
- No birds yet, no nests yet
- No helpers yet

---

## The Incubation Space (Inside)

### Sonic texture
Warm, close, quiet. The hum of the incubator. Soft ambient warmth. Distinct from outside.

### Egg care mechanics
- **Turning** — eggs must be turned gently at regular intervals (species-dependent, typically 3x/day). A simple gesture action. The player marks and turns each egg. Skipping turns risks the embryo sticking to the shell.
- **Temperature** — must stay within species range (typically 99–102°F). Drifts without tending. Poor insulation means more drift. Audible signature when too high or too low — a warmth drone that goes slightly off.
- **Humidity** — two phases: lower during most of incubation, higher in the final days before hatch. Audible signature for each phase.
- **Candling** — player can candle any egg to check development. Blood vessels early, movement later. Gives information, not a pass/fail.
- **Final days** — stop turning 3 days before hatch. Listen for pipping (first cracks), then peeping, then hatching. Don't interfere.

### Improving the incubator
Gathered materials (moss, soft grass, feathers) can improve insulation and humidity stability, reducing how often the player needs to actively tend. Better incubator = healthier hatches = more birds.

---

## The Outdoor Territory (Outside)

### Sonic texture
Open, spacious, layered with bird calls. The incubator hum fades. Wind, rustling. Bird voices scattered spatially via HRTF.

### Bird behavior
- Adult birds wander their territory, calling at intervals (species-dependent)
- Bonded pairs build nests over time using materials available in the environment
- Nests enable egg-laying — eggs appear in nests when conditions are right (healthy birds, sufficient space, available materials)
- If territory is too small for the flock, birds call differently — a crowding signature, less peaceful, slightly anxious. Expanding the space resolves it.

### Gathering
- Player wanders and finds nesting materials: twigs, moss, soft grass, feathers
- Materials are more varied further out in expanded territory
- Materials serve two purposes: expand territory AND supply nest-building for birds
- Gathering requires presence — you have to be out there

### Expanding territory
- Costs a set of gathered materials
- World physically grows — more space to explore, more to find, less crowding
- Each expansion unlocks more sonic texture, more bird habitat

---

## Species System

### Architecture
Species are defined in JSON files, one per species. The game engine handles mechanics (turn egg, check temperature, play sound) — the species file provides all the flavor: timing, ranges, sound pointers, behavior parameters.

### Species JSON fields (draft)
```json
{
  "id": "example_finch",
  "name": "Example Finch",
  "description": "A small, sociable bird with a bright call.",
  "incubation_days": 14,
  "turning_times_per_day": 3,
  "stop_turning_days_before_hatch": 3,
  "temperature_min_f": 99.0,
  "temperature_max_f": 102.0,
  "humidity_early_pct": 45,
  "humidity_late_pct": 70,
  "humidity_late_start_day": 11,
  "egg_laying_interval_days": 21,
  "flock_or_solo": "flock",
  "wander_radius": 12.0,
  "wander_speed": 0.4,
  "call_interval_min": 6.0,
  "call_interval_max": 14.0,
  "sounds": {
    "egg_call": "sounds/example_finch/egg_call.wav",
    "egg_turn": "sounds/example_finch/egg_turn.wav",
    "pip": "sounds/example_finch/pip.wav",
    "hatch": "sounds/example_finch/hatch.wav",
    "chick_call": "sounds/example_finch/chick_call.wav",
    "adult_call": "sounds/example_finch/adult_call.wav",
    "nest_building": "sounds/example_finch/nest_building.wav",
    "crowding": "sounds/example_finch/crowding.wav"
  }
}
```

### Species UI
A simple accessible UI (NVDA-compatible) for adding and editing species without touching JSON directly. Fields map 1:1 to the JSON. Sound files can be pointed to via file picker.

---

## NPC Helpers (Assistants)

### Concept
As the sanctuary grows beyond what one person can tend, helpers become available. Each takes on a role and reports to the player through ambient speech as they wander past.

### Roles (examples)
- **Incubator tender** — monitors and adjusts temperature/humidity, turns eggs on schedule
- **Forager** — gathers nesting materials from the territory
- **Territory keeper** — monitors crowding, flags when expansion is needed
- **Nest watcher** — monitors nest activity, reports new eggs

### Behavior
- Helpers work autonomously in the background
- They speak brief ambient reports when the player is nearby: *"Humidity in the incubator is running a little low."* / *"Found some good moss near the north edge today."*
- Player still directs — can reassign roles, can override
- Helpers are unlocked as territory expands, one at a time

### Implementation note
Helpers could literally be lightweight AI/bot instances. Their report strings could be generated or templated. This is intentionally left open for future development.

---

## Accessibility

- Audio-first, designed around HRTF spatial audio with headphones
- NVDA/SAPI speech for all game state
- No visual requirement — all information available through sound and speech
- Keyboard-only controls (inherits from Egg Park)
- Calm pacing — no time pressure, no fail states

---

## Technical Foundation

Inherits from Egg Park:
- Python, single file to start (grows when it earns it)
- pyglet + OpenAL Soft HRTF
- accessible_output2 for screen reader speech
- A-minor pentatonic for synth placeholder sounds
- Sound architecture: one function per sound category, swap to samples without changing callers

New requirements:
- Persistent world state (save/load)
- Day/night cycle or time compression (real-time vs accelerated)
- Species JSON loader
- NPC helper system
- Territory expansion system
- Material gathering system
- Nest and egg-laying system

---

## Open Questions for Opus

1. **Time scale** — real-time incubation (14–21 days) or compressed? If compressed, what ratio feels right without losing the sense of patience and waiting?
2. **Save format** — JSON world state? SQLite? What's cleanest for a Python single-file origin?
3. **NPC voice** — templated strings, or something more dynamic?
4. **Starting species** — should the game ship with one default species, or prompt the player to define one before starting?
5. **Egg source for the first 12** — they just exist at game start, or is there a brief intro that places them?

---

*This document is a starting point. Hand it to Opus with the Egg Park codebase and ask it to architect The Bird House.*
