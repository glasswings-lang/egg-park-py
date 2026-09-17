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

## Thanks

The scan guide — the blip that leads you to what a scan found, speeding up
as you close in and wobbling as you turn away — was inspired by the scan
guide in **Periphery Synthetic** by **Shift Backtick**
(<https://shiftbacktick.io>). Nothing from it is used here: no code and no
sound. Just the idea that a sound can tell you where something is by the way
it changes as you move. Go play it.

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
| **Sound test**        | Every cue in the game, with what it means       |
| **Controls**          | Reads the control list aloud                    |
| **Quit**              | Leaves the game                                 |

### Sound test

A world made entirely of sound is unusable until you know which sound is
which, and there was no way to learn that except triggering each cue in
play and reasoning backwards.

**Up / Down** to choose, **Enter** to hear it, **Right** to say what it
means. It also tells you whether you're hearing a recording or the built-in
placeholder.

It doubles as the recording workstation:

| Key | |
| --- | --- |
| **S** | Switch between your recordings and the built-in sounds |
| **R** | Reload recordings from disk — no restart after saving a take |

| **F** | Open `sounds.txt`, where you point at your own recordings |
| **P** | Read out any problems with that file |

So the loop is: record, **R**, **Enter** to hear it, **S** to hear what it
replaced, **S** again. The same switch lives in Settings as *Use recordings
when available*, and it applies to the whole game, not just this screen.

### Using your own recordings — `sounds.txt`

You can drop files into `public/audio/samples/` named exactly right
(`egg-call-1.wav` and so on) and they'll be found. But that means renaming
your takes and moving them, which is a coding task wearing a filename.

`sounds.txt` is the other way. One line per sound:

```
egg-call = C:\Users\you\recordings\take 4 good one.wav
```

Paths can be anywhere on your machine or relative to the game folder.
Spaces are fine, quotes optional. Write the same sound twice to give it two
versions and the game picks between them at random. A line here **replaces**
whatever the samples folder has for that cue, so "which files does this use"
has one answer and it's written down.

It's generated on first run with **every cue listed, commented out, with
what each one means** — so nothing has to be typed from memory. Uncomment a
line, put a path after the equals sign, save, press **R**.

Nothing fails silently. A typo'd cue name, a missing file, a line with no
equals sign — each is reported, and pressing **P** reads them out. A broken
line is also announced on the cue it was meant to supply, which is where
you'd go looking when a sound doesn't play.

`sounds.txt` is not committed. It names paths on your machine.

## Saving

Your park saves itself to `park.json` next to `main.py`: every 30 seconds
while you play, whenever you open the menu, and when you quit or close the
window. Next time, the menu's first item is **Continue your park**.

Starting a new park over a saved one takes Enter twice, and the old park is
kept as `park-previous.json`. A save that can't be read is never overwritten;
it's set aside as `park-unreadable.json` and a fresh park starts.

## Play log

Every session writes `play-log.txt` next to `main.py`: everything the game
said aloud, and the numbers behind it (baskets found, eggs held out of how
many, basket capacity) at every find, pickup, refusal and deposit. The one
before is kept as `play-log-previous.txt`. If something seems wrong while
playing, keep playing; the log shows exactly when and what.

If the game ever stops on its own, it writes what went wrong to
`crash-log.txt` next to `main.py`, saves the park on the way down, and says
so aloud. Crashes are appended with a date and time rather than overwriting
each other, so a rare one still leaves a trail. Under `pythonw` there is no
console, so without this a crash left nothing at all behind.

## Tests

```
python tests/test_soundlist.py      # sounds.txt parsing and the template
python tests/test_sound_wiring.py   # every sound is registered everywhere
python tests/test_scan_guide.py     # the scan guide and B, inside the real game
python tests/test_movement.py       # running, and footsteps that don't hiss
python tests/test_play_log.py       # the play log records finds and capacity
python tests/test_park_save.py      # the park survives closing the game
python tests/test_egg_spread.py     # eggs spread around your baskets, no drift
python tests/test_birds_lay.py      # birds lay eggs near home
python tests/test_chests.py         # chests: gifts, capacity, C and Shift+C
python tests/test_nets.py           # nets, scooping, basket and chest footsteps
python tests/test_crash_safety.py   # a scan in a full park, and the crash log
```

Plain Python, no pytest. The first two read the game's code as text rather
than running it, because running it opens a window.

The tests that start with `test_scan_guide.py` in the list above are the
exception: they run the
game for real, through `tests/_game_harness.py`. That first
moves onto a hidden Windows desktop with no screen, keyboard or speakers
attached, with speech off, so it can't take focus from a screen reader or
make a sound. If it can't get that hidden desktop, it refuses to run.

`test_sound_wiring.py` is the one that matters when changing sounds: adding
a cue means touching four separate places, and forgetting one fails
silently. It prints the checklist when it catches you.

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
| **Shift** (hold)    | Run                                              |
| **Q** / Left arrow  | Turn left                                        |
| **E** / Right arrow | Turn right                                       |
| **Space**           | Scan — reveal nearby eggs and baskets by ping    |
| **B**               | Guide to the nearest found basket with room      |
| **V** / **Shift+B** | Guide to the nearest basket not yet found        |
| **C**               | Guide to the nearest found chest with room       |
| **Shift+C**         | Guide to the nearest chest not yet found         |
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
mechanics (egg pickup, hand-hatching, basket-hatching, ground-hatching, bird laying, egg calls, basket
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
├── main.py            # starts the game: audio setup, then boot
├── eggpark/           # the game, one file per part
│   ├── config.py      #   fixed numbers: speeds, distances, ranges
│   ├── speech.py      #   screen reader speech and the play log
│   ├── state.py       #   what's in the park: you, eggs, baskets, birds
│   ├── prefs.py       #   settings and the settings screen
│   ├── menu.py        #   main menu; starting and restarting a park
│   ├── sounds.py      #   every sound, recordings, sounds.txt, catalogue
│   ├── soundtest.py   #   the sound test screen
│   ├── world.py       #   eggs and baskets: spawning, pickup, deposit
│   ├── scan.py        #   scanning, B, and the scan guide
│   ├── flock.py       #   hatching and birds
│   ├── chests.py      #   chests: gifts, finding, C and Shift+C
│   ├── game.py        #   window, keys, per-frame update, status
│   └── saving.py      #   saving and loading the park
├── tests/             # see Tests above
├── openal32.dll       # OpenAL Soft (HRTF backend for pyglet)
├── docs/
│   └── SOUNDS.md      # sound design specs / recording plan
├── public/
│   └── audio/
│       └── samples/   # drop recorded .wav files here — auto-loaded at startup
└── README.md
```
