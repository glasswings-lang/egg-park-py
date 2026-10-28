# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Egg Park: an audio-first exploration game in Python. pyglet for window, input and 3D audio through OpenAL Soft with HRTF; accessible_output2 for screen-reader speech (NVDA, JAWS, SAPI). The window is only a keyboard-focus target; nothing visual matters. It is built for a player with a screen reader running at all times, so every player-facing change is a change to what is said or heard.

- Install: `pip install pyglet accessible_output2` (PyOpenAL is not needed; nothing imports it)
- Run: `python main.py`
- `openal32.dll` (OpenAL Soft 1.25.1, LGPL) and `hrtf/SADIE_D1-48000.mhr` (SADIE II, Apache 2.0) are tracked on purpose so a clone just runs. Everything else is CC0.
- `main.py` sets `ALSOFT_CONF` to `alsoft.conf` (unless already set) and `EGG_PARK_HRTF` to `hrtf/`, before pyglet loads. OpenAL Soft reads `ALSOFT_CONF` after `%AppData%\alsoft.ini`, so the repo's keys win; keys it leaves out, such as the output driver, still come from the machine's file. Use the SADIE file without `InvertedY` in its name; the `InvertedY` one has above and below swapped.

## Tests

Plain Python scripts, no pytest, no runner. Run one at a time from the repo root, for example `python tests/test_chests.py`. Each prints `ok` / `FAIL` lines and exits non-zero on failure. The full list with one-line descriptions is in the Tests section of `README.md`.

Two kinds:

- Source-reading tests (`test_soundlist.py`, `test_sound_wiring.py`, `test_no_private_strings.py`) read the code as text with regex and never import the game, because importing it opens a window.
- Game tests run `main.py` for real through `tests/_game_harness.py`. The harness moves the process onto a hidden Windows desktop (`tests/_isolated_desktop.py`), blocks `accessible_output2`, forces pyglet's silent audio driver, and redirects the play log, save, crash log, `sounds.txt` and `settings.json` to a temp folder via the `EGG_PARK_*` environment variables, so tests start from default settings, never the player's. If the hidden desktop is unavailable it exits with code 3 rather than run unprotected. On that desktop the Intel and NVIDIA OpenGL drivers both refuse `wglMakeCurrent`, so `_isolated_desktop.py` preloads Mesa llvmpipe from `tests/mesa/` (test processes only). A `GLException 0x1282` at window creation means that preload did not happen. Never bypass this: an unisolated game run steals focus from NVDA and speaks over it.

Writing a game test: `run_game(checks)` execs `main.py` with `pyglet.app.run` replaced by `checks(G)`. `G['name']` finds a name in whichever `eggpark/` module defines it; `G['name'] = value` replaces it in the owning module, which is how tests stub things like `G['say'] = spoken.append`. End with `finish('test_name')`.

## Architecture

- `main.py` only boots: sets `ALSOFT_HRTF` and the DLL directory before pyglet loads audio, installs the crash hook (writes `crash-log.txt`, saves the park, says so aloud), loads settings and the sample bank, opens the controller, schedules `game.update` at 60 Hz, opens the main menu. The boot order is deliberate and commented there.
- `eggpark/` is one module per part (the README File layout section names each). Modules import each other as module objects (`from eggpark import state, sounds`) and always access `module.attr`. Keep it that way: the imports are circular, and `from module import name` on mutable state would also break the harness's per-module monkeypatching.
- `state.py` holds all live park state as module-level globals (`player`, `eggs`, `baskets`, `held`, `chests`, `birds`, `progress`). Coordinates: X-Y is the walking plane, Z is up, yaw 0 faces +X. `eggs` is an `EggField` (`eggfield.py`), a list with a 25 m spatial grid so neighbourhood queries stay cheap at 12,000 eggs.
- `voices.py` is a pool of reused OpenAL voices that every sound plays on; `tally.py` collapses many simultaneous events into one report. Both exist for big-park performance (`test_big_park.py`, `test_voices.py`, `test_tally.py`).
- Nothing ticks while a menu or settings is open; the world is paused.
- Persistence, all next to `main.py` and gitignored: `park.json` (autosave every 30 s, on menu, on quit, on window close; previous kept as `park-previous.json`, unreadable ones set aside as `park-unreadable.json`), `settings.json`, `play-log.txt` (everything spoken plus the numbers behind it, previous session kept), `crash-log.txt` (appended), `sounds.txt`.

## Sounds

All sounds are synth placeholders, each behind one helper (`fire_egg_call` and so on) in `sounds.py`, so swapping to a recording is local. Recordings are picked up from `public/audio/samples/` by exact filename, or mapped by `sounds.txt` (`cue-name = path`), which overrides the folder for that cue. `sounds.txt` is generated on first boot and new cues are appended to an existing one. Lines indented four spaces or a tab are examples and ignored; one to three spaces is a real line (what deleting the `#` from a `# cue = ` line leaves).

F1 in the sound test opens `eggpark/filepick.py`: IFileOpenDialog through comtypes, declared by hand in vtable order, with a Preview push button (Alt+P). The choice is written into `sounds.txt` by `sounds.assign_in_sounds_list`, never kept anywhere else. Sound test and Preview playback go through `sounds.play_preview` / `stop_preview`, so only one preview sounds at a time. `tests/test_choose_recording.py` drives the real dialog from a second thread with window messages: a timer on the game thread never fires while the dialog is modal.

Adding a cue means registering it in four places: `_SAMPLE_CATEGORIES`, `_VOLUME_CATEGORIES`, `SOUND_CATALOGUE` and `docs/SOUNDS.md`. Missing one fails silently in game. Run `python tests/test_sound_wiring.py` after any sound change; its `SHARES_VOLUME_WITH` and `NOT_IN_SOUND_TEST` hold the deliberate exceptions, each with a reason.

## Keeping docs in step

Controls are documented in three places that must agree: the docstring in `main.py`, the in-game help text, and the Controls and controller tables in `README.md`. The controller mapping follows Periphery Synthetic's layout (see README). A new mechanic is expected to reach all of them, as recent commits show.

## Private-string guard

`tests/test_no_private_strings.py` blocks commits containing names or paths listed in `docs/private/forbidden-strings.txt` (gitignored, along with all of `docs/private/`). It runs as a pre-commit and commit-msg hook from `githooks/`, armed per clone with `git config core.hooksPath githooks`. Where `docs/private/` exists, a missing or empty list is a failure, not a skip. Never commit anything under `docs/private/`, and never put real names, handles or machine paths in code, tests or commit messages.

## Other docs

- `docs/SOUNDS.md`: sound design spec and recording plan per cue.
- `docs/BIRDHOUSE_DESIGN.md`: design document for a separate, later game (The Bird House) on the same foundation. Not part of Egg Park's code.
