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

## On a controller

Plug one in and it works — a wired Xbox pad is what this was built against.
Nothing has to be configured, and the keyboard is untouched. Press **Y** on
the pad to hear the whole mapping read out.

Why it exists: a keyboard hurts to play on for long, and holding a turn key
gives you all of the turn speed or none of it, so every correction
overshoots. A stick is analog. A nudge turns you a little, and a gentle push
walks you slowly up to an egg.

| | |
| --- | --- |
| **Left stick** | Walk, any direction. How far you push is how fast you go |
| **Click left stick** | Run — a toggle, so nothing to hold |
| **Right stick** | Turn, proportionally |
| **Right trigger** | Hold to run, for as long as you hold it |
| **A** | Scan |
| **B** | Deposit everything; hold it to pour eggs in one at a time |
| **X** | Your status |
| **Y**, tapped | Read out the controller controls |
| **D-pad up / down** | Lead to a found / unfound basket |
| **D-pad right / left** | Lead to a found / unfound chest |
| **Left trigger** | The chest list: every chest you've found, nearest first, and what its birds get. D-pad up and down choose, left and right switch to the basket list and back, A leads you there, B closes. The park keeps running |
| **Hold Y + D-pad** | Ask: heading / carrying / the park / everything |
| **Right stick, clicked** | Lead home, to where the park began |
| **Bumpers** | Volume down / up |
| **Start / Back** | Main menu / settings |

The shape of this follows [Periphery Synthetic's
manual](https://periphery-synthetic-ep.shiftbacktick.io/manual.html) — left
stick moves, right stick turns, **A** scans and confirms, **B** acts and goes
back, **Start** opens the menu, sprint is on the stick click rather than a
held trigger, and holding **Y** turns the D-pad into questions instead of
actions. Holding a trigger while pushing a stick is the grip that hurts, and
the pad is here because the keyboard hurt.

In any menu the stick or D-pad moves the focus, **A** picks and **B** goes
back, so a session never has to start at the keyboard. A held stick is one
step, not sixty a second.

Three settings go with it: *Controller* switches it off entirely,
*Controller turning, fineness* sets how gentle small pushes are, and
*Controller stick slack* is the deadzone, for a worn stick that drifts at
rest.

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
python tests/test_chest_list.py     # the chest list: G and the left trigger
python tests/test_nets.py           # nets, scooping, basket and chest footsteps
python tests/test_crash_safety.py   # a scan in a full park, and the crash log
python tests/test_tally.py          # many events at once make one sound, not hundreds
python tests/test_big_park.py       # 12,000 eggs and 250 birds still run smoothly
python tests/test_duck.py           # the park quietens while the scan answers
python tests/test_pad.py            # the controller: sticks, buttons, menus
python tests/test_pad_live.py       # boots with a REAL pad on pyglet's own loop
python tests/test_speed.py          # speed builds, and wind rises with it
python tests/test_voices.py         # the voice pool: what plays when a park is busy
python tests/test_eggfield.py       # the egg grid: still true, and cheap in a heap
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
| **G**               | Chest list: Up / Down choose, Enter leads, Esc closes |
| **Shift+G**         | Basket list, the same, with each basket's room   |
| **F**, tapped       | Deposit everything held at the basket or chest you're on |
| **F**, held         | Pour eggs in one at a time, quicker as you hold; let go to stop |
| **P**               | Speak status (heading, distances, counts, caps)  |
| **Shift+H**         | Guide home, to where the park began              |
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
   Standing within depositing range (5 m, for baskets and chests alike)
   changes your **footsteps** too, which is how you know you're on the spot
   rather than merely near it.
5. Stand on a discovered basket and tap F to deposit everything you hold,
   or hold F to pour eggs in one at a time: one knock each, climbing as the
   basket fills, quicker the longer you hold. Let go and it says how many
   went in, so you can spread what you carry across several baskets.
   Shift+G lists every basket you've found with its room, and G every chest;
   pick one and you're led there. Lost? Shift+H leads you home.
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
│   ├── voices.py      #   the pool of reused OpenAL voices every sound plays on
│   ├── soundtest.py   #   the sound test screen
│   ├── world.py       #   eggs and baskets: spawning, pickup, deposit
│   ├── eggfield.py    #   the egg list, with a grid so density stays cheap
│   ├── scan.py        #   scanning, B, and the scan guide
│   ├── flock.py       #   hatching and birds
│   ├── tally.py       #   repeated events counted, and reported once
│   ├── pad.py         #   the controller: sticks, buttons, menus
│   ├── chests.py      #   chests: gifts, finding, C and Shift+C
│   ├── chestlist.py   #   the chest and basket lists: G, Shift+G, the left trigger
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
