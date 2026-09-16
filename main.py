# SPDX-License-Identifier: CC0-1.0
"""Egg Park — Python port using pyglet + accessible_output2.

Audio-first exploration game. Walk a flat world, hear eggs calling from
their positions, collect them, deposit at baskets, watch them hatch into
wandering birds.

Architecture:
- This file only starts the game. The game lives in eggpark/, one file per
  part: config (fixed numbers), speech (screen reader + play log), state
  (what's in the park), prefs (settings), menu, sounds, soundtest, world
  (eggs and baskets), scan (scanning and the guide), flock (hatching and
  birds), game (window, keys, the per-frame update) and saving.
  It was one 3000-line file until 2026-09-16.
- pyglet for window + input + 3D positional audio (OpenAL Soft HRTF).
- accessible_output2 for NVDA/JAWS/SAPI screen-reader speech.
- All sounds currently synth placeholders. See `docs/SOUNDS.md` for the
  recording spec — each placeholder is one helper function (e.g.
  `fire_egg_call`) so swapping to samples is a single-function change.

Controls (game):
  W / Up arrow    — walk forward
  S / Down arrow  — walk back
  A               — strafe left
  D               — strafe right
  Shift (hold)    — run
  Q / Left arrow  — turn left
  E / Right arrow — turn right
  Space           — scan (reveals nearby eggs + baskets via audible ping,
                    then a guide blip leads to the nearest egg)
  B               — guide to the nearest basket with room, found or not
  F               — deposit held eggs at the basket you're standing on
  P               — speak status (heading, distances, counts, capacities)
  R               — reload sample bank (re-scan public/audio/samples)
  [ / ]           — master volume down / up
  O               — open settings (pauses the world)
  H / ?           — speak the controls aloud (this list, in the game)
  Escape          — back to the main menu (Quit lives there)

Controls (settings screen):
  Up / Down       — focus previous / next setting
  Left / Right    — decrease / increase  (volume: -/+10%; toggles: off/on)
  Space / Enter   — toggle current setting
  O / Escape      — close settings
"""

import os

# OpenAL Soft HRTF must be enabled BEFORE pyglet loads its audio driver.
os.environ['ALSOFT_HRTF'] = '1'

# Ensure pyglet finds openal32.dll regardless of cwd.
_script_dir = os.path.dirname(os.path.abspath(__file__))
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(_script_dir)

import pyglet
# Force pyglet to use OpenAL (HRTF support) instead of XAudio2.
pyglet.options['audio'] = ('openal', 'xaudio2', 'directsound', 'pulse', 'silent')

# The game itself lives in the eggpark package, one file per part. Imported
# only now, after the audio driver and DLL path above are set.
from eggpark import game, menu, prefs, saving, sounds, speech  # noqa: E402

# Work that used to happen as a side effect of loading the one big file.
# Explicit, and in this order: the log first so anything said is recorded,
# settings before sounds so the recordings switch is honoured.
speech._open_play_log()
prefs.load_settings()
sounds.rebuild_sample_bank()


# ============================================================================
# Boot
# ============================================================================

sounds.update_listener()  # so positional audio is correct before the first tick.

# Boot chime + start the ambience bed if it's enabled in settings.
sounds.fire_boot()
sounds._sync_ambience()

# No park yet — the menu is the first thing you meet. `start_game()` spawns
# one when it's asked for, so nothing ticks and no egg is on a timer while
# someone is still deciding what they want to do.
game.window.activate()
pyglet.clock.schedule_interval(game.update, 1 / 60)
game._next_egg_call_at = game.now() + 0.5
game._next_origin_chime_at = game.now() + 2.0  # let boot chime + speech land first

# Generate sounds.txt on first run, now that SOUND_CATALOGUE exists to
# describe every cue in it. Never overwrites an existing one.
sounds.write_sounds_template()

menu.open_main_menu(announce='Egg Park.')

pyglet.app.run()

# The window's close button ends the loop without passing through quit_game.
if menu._game_started:
    saving.save_park('window closed')
