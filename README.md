# Egg Park (Python)

Audio-first exploration game built on pyglet + accessible_output2 +
OpenAL Soft HRTF. Walk a flat world, hear eggs calling, collect them at
the cost of holding their hatch timers, deposit at baskets before they
hatch. Eggs in baskets hatch into wandering birds that join your park.

## Licence

**CC0 1.0 Universal** — public domain dedication. Full text in `LICENSE`.

That covers everything in this repository: the code, the documentation, and
the recorded sounds under `public/audio/samples/`. Take it, change it, sell
it, credit nobody. No permission needed and none to ask for.

The reasoning, since it's a deliberate choice rather than a default: you
can't own an idea, and you certainly can't own code generated from other
people's work without their consent.

**One exception, and it isn't mine to waive:** `openal32.dll` is OpenAL
Soft, under the LGPL, and stays under the LGPL. It's redistributed here
unmodified and dynamically loaded, so it can be swapped for your own build.
See `THIRD-PARTY.md` for the details and `LICENSES/` for the texts.

## Setup

```
pip install pyglet accessible_output2 PyOpenAL
```

The OpenAL Soft DLL is checked in as `openal32.dll` in this folder so
pyglet finds it. (Copied from PyOpenAL's bundled `soft_oal_64.dll`.)

## Running

```
python main.py
```

A small window opens — keyboard focus only, visuals don't matter. NVDA or
SAPI announces game state. Use headphones for the HRTF spatial audio.

## Main menu

The game opens to a spoken menu rather than dropping you into a park.
**Up / Down** moves, **Enter** picks.

| Item                  | What it does                                    |
| --------------------- | ----------------------------------------------- |
| **Walk in the park**  | Spawns a fresh park and starts playing          |
| **Back to the park**  | Replaces the above once a park exists           |
| **Start a new park**  | Throws this park away and spawns another        |
| **Settings**          | Same settings screen, and closing returns here  |
| **Controls**          | Reads the control list aloud                    |
| **Quit**              | Leaves the game                                 |

**Esc** in the park comes back here — it no longer quits outright. Quit
lives in the menu, so it takes a deliberate choice rather than one keypress
with no confirmation.

Nothing ticks while the menu is open. No egg is on a timer while you're
still deciding what you want to do.

## Controls

| Key                 | Action                                           |
| ------------------- | ------------------------------------------------ |
| **W** / Up arrow    | Walk forward                                     |
| **S** / Down arrow  | Walk back                                        |
| **A**               | Strafe left                                      |
| **D**               | Strafe right                                     |
| **Q** / Left arrow  | Turn left                                        |
| **E** / Right arrow | Turn right                                       |
| **Space**           | Scan — reveal nearby eggs and baskets by ping    |
| **F**               | Deposit held eggs at the basket you're on        |
| **P**               | Speak status (heading, distances, counts, caps)  |
| **R**               | Reload sample bank (re-scan samples folder)      |
| **[** / **]**       | Master volume down / up (10% steps, 0–200%)      |
| **O**               | Open settings screen (pauses the world)          |
| **Esc**             | Back to the main menu (pauses the world)         |

Inside the settings screen, **Up / Down** picks a setting, **Left / Right**
adjusts it (volume changes by 10%; toggles flip off / on), **Space** or
**Enter** toggles, **O** or **Esc** closes. Settings persist to
`settings.json` next to `main.py`. You can turn off any of the automatic
mechanics (egg pickup, hand-hatching, basket-hatching, egg calls, basket
chimes, bird calls) — useful if you just want to wander the soundscape.

## Game loop

1. Walk a flat plane. Eggs spawn at random positions and call every
   1.5 s — listen for the nearest one and follow it.
2. Walk within 2 m of an egg to collect it. It joins your inventory and
   starts a 30 s hatch timer. A new egg spawns somewhere else.
3. Three baskets are placed in cardinal directions (east A3, north D4,
   west G4 — different pitches so you can tell them apart by ear). They
   chime periodically; faster as you approach.
4. Walk to a basket to discover it. Each discovery bumps every basket's
   capacity by 1 and bumps your carry capacity every 3 baskets. A found
   basket also **changes voice** — same note and position, brighter timbre
   — so you can hear at a distance which ones you've already claimed.
   Standing within depositing range changes your **footsteps** too, which
   is how you know you're on the spot rather than merely near it.
5. Stand on a discovered basket, press F to deposit held eggs.
6. Eggs in baskets continue to tick. When the timer runs out, the egg
   hatches into one of your birds — joins the world, wanders the park,
   calls periodically. If a held egg hatches before you deposit, the bird
   flies off as a wild bird (lost to the world).

## Status

Mechanical foundation complete (2026-05-18). All sounds are synth
placeholders; see `docs/SOUNDS.md` for the recording plan to replace them
with real audio.

## File layout

```
egg-park-py/
├── main.py            # all game code, single file
├── openal32.dll       # OpenAL Soft (HRTF backend for pyglet)
├── docs/
│   └── SOUNDS.md      # sound design specs / recording plan
├── public/
│   └── audio/
│       └── samples/   # drop recorded .wav files here — auto-loaded at startup
└── README.md
```
