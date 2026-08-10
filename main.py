# SPDX-License-Identifier: CC0-1.0
"""Egg Park — Python port using pyglet + accessible_output2.

Audio-first exploration game. Walk a flat world, hear eggs calling from
their positions, collect them, deposit at baskets, watch them hatch into
wandering birds.

Architecture:
- Single-file vanilla Python. Grows when it earns it.
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
  Q / Left arrow  — turn left
  E / Right arrow — turn right
  Space           — scan (reveals nearby eggs + baskets via audible ping)
  F               — deposit held eggs at the basket you're standing on
  P               — speak status (heading, distances, counts, capacities)
  R               — reload sample bank (re-scan public/audio/samples)
  [ / ]           — master volume down / up
  O               — open settings (pauses the world)
  H / ?           — speak the controls aloud (this list, in the game)
  Escape          — quit

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

import glob
import json
import math
import random
import time

import pyglet
# Force pyglet to use OpenAL (HRTF support) instead of XAudio2.
pyglet.options['audio'] = ('openal', 'xaudio2', 'directsound', 'pulse', 'silent')

from pyglet.window import key
from pyglet.media import synthesis

try:
    from accessible_output2 import outputs
    _speech = outputs.auto.Auto()
except Exception as exc:
    print(f'[warning] accessible_output2 unavailable: {exc}')
    _speech = None


def say(text):
    """Speak a line via the user's screen reader."""
    if _speech:
        _speech.speak(text)


# ============================================================================
# Constants
# ============================================================================

WALK_SPEED = 2.0
TURN_SPEED = math.pi / 2

# A-minor pentatonic, the world's tonal anchor. All pitched sounds draw
# from this so eggs / baskets / scan pings / bird calls harmonize.
PENTATONIC_FREQS = [220.00, 261.63, 293.66, 329.63, 392.00]  # A3 C4 D4 E4 G4
PENTATONIC_NAMES = ['A3', 'C4', 'D4', 'E4', 'G4']

# Register separation. Everything drew from the same five notes, so eggs and
# baskets sat on top of each other and eggs won — they call more often and a
# triangle is far more assertive than a sine. Timbre alone was never going to
# carry it.
#
# Birds already solved this by living an octave up. Baskets now live an
# octave DOWN, which gives three layers you can hear apart even when all
# three are sounding: baskets low, eggs middle, birds high.
#
# TUNE BY EAR — this is one number. 0.5 is an octave down; 1.0 puts baskets
# back with the eggs; 0.25 is two octaves down and probably too low to
# localise, since HRTF direction cues thin out badly in the bass.
BASKET_OCTAVE = 0.5
BIRD_OCTAVE = 2.0

# Eggs
NUM_EGGS = 4
EGG_CALL_INTERVAL = 1.5
EGG_AUDIBLE = 80.0
COLLECT_RADIUS = 2.0
EGG_SPAWN_MIN = 20.0
EGG_SPAWN_MAX = 60.0

# Baskets
BASKET_AUDIBLE = 80.0
BASKET_DEPOSIT_RADIUS = 2.0
BASKET_DISCOVER_RADIUS = 3.5
BASKET_CHIME_INTERVAL_FAR = 4.0
BASKET_CHIME_INTERVAL_NEAR = 1.0

# Basket generation. The park used to hold exactly three baskets, forever,
# which capped carry capacity at two eggs and made walking outward pointless
# — there was nothing further out to find.
#
# Now the world keeps BASKET_TARGET_UNFOUND unclaimed baskets within reach of
# wherever you actually are. Claim one and another appears somewhere you
# haven't been, so exploring in any direction eventually pays.
BASKET_TARGET_UNFOUND = 2     # unclaimed baskets kept available at any time
BASKET_SPAWN_MIN = 45.0       # never closer than this to the player...
BASKET_SPAWN_MAX = 85.0       # ...nor further than earshot plus a little
BASKET_MIN_SEPARATION = 25.0  # keep them apart or two chimes fight for the ear
BASKET_MAX_TOTAL = 24         # ceiling, so a long session can't fill the world
BASKET_PLACE_ATTEMPTS = 24    # tries to find a spot before giving up this tick
# Unclaimed baskets left far behind are forgotten. Without this the park
# silts up with baskets you walked past once and will never return to: a
# twenty-minute wander spawned seventeen and found two, hit the ceiling, and
# generation stopped — which is the original three-baskets-forever problem
# wearing a different hat. Comfortably beyond earshot, so nothing is ever
# removed while it can still be heard.
BASKET_FORGET_DISTANCE = BASKET_AUDIBLE * 1.75

# Capacity
CARRY_BUMP_EVERY = 3   # player carry cap grows by 1 every N basket discoveries
CARRY_START = 1        # starting carry capacity (also grows from there)

# Scan
SCAN_RANGE = 200.0
SCAN_DURATION = 2.5    # close items ping first, far items last

# Hatching
HATCH_TIMER_INITIAL = 30.0
WILD_BIRD_DISPERSAL = 1.5
BIRD_CALL_MIN_INTERVAL = 8.0
BIRD_CALL_MAX_INTERVAL = 16.0
BIRD_WANDER_RADIUS = 10.0
BIRD_WANDER_SPEED = 0.4

# Footsteps — distance the player has to walk before the next step fires.
# Cadence is implicitly tied to walk speed: 1.0 m stride at default 2.0 m/s
# = ~2 steps/sec = ~120 BPM (natural walking cadence). Slower walk_speed
# spaces them out; faster compresses them toward a jog/run rate.
STEP_DISTANCE = 1.0

# Egg warning — when a held or basketed egg's hatch_timer drops below
# WARNING_WINDOW, the warning sound fires once per WARNING_INTERVAL until
# the egg hatches (or the held egg is deposited, resetting the cadence).
WARNING_WINDOW = 5.0
WARNING_INTERVAL = 1.0

# Bird ambient — wing-flap / rustle per bird, between calls. Picked
# independently of bird_call's timing so the two overlap unpredictably.
BIRD_AMBIENT_MIN_INTERVAL = 15.0
BIRD_AMBIENT_MAX_INTERVAL = 40.0

# Origin chime — a beacon at world (0, 0, 0). Lets the player hear which
# way "home" is from anywhere reasonable. Fires on a fixed interval rather
# than proximity-scaled so it's a constant landmark, not a reactive thing.
ORIGIN_CHIME_INTERVAL = 8.0
ORIGIN_MAX_DISTANCE = 500.0  # carries well beyond SOURCE_MAX_DISTANCE

# Spatial audio attenuation (shared by all positioned sounds).
#
# SOURCE_MIN_DISTANCE is OpenAL's REFERENCE distance, not a minimum: it is
# the distance at which a sound plays at full gain, and under the default
# inverse-distance model gain falls as ref / (ref + (dist - ref)).
#
# It was 1.0 in a world where eggs spawn 20-60 m out and baskets sit at 40 m.
# At 40 m that is 1/40th gain -- about -32 dB. So the basket scan ping fired
# perfectly and correctly, at every basket in range, entirely inaudibly. The
# feature was never missing; it was whispering from four blocks away.
#
# At 20 m: 40 m -> 0.33 gain, 60 m -> 0.33... no: ref/(ref+(d-ref)) = 20/40
# = 0.5 at 40 m, 0.25 at 80 m. A usable gradient that still tells you how far
# away something is, which is the whole point of the cue.
SOURCE_MIN_DISTANCE = 20.0
SOURCE_MAX_DISTANCE = 80.0


# ============================================================================
# World state
# ============================================================================

# X-Y is the horizontal walking plane, Z is vertical (up). Yaw rotates
# around +Z; yaw=0 means facing +X.
player = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'yaw': 0.0}

# Eggs in the world. Each: {x, y, z, freq_idx, hatch_timer}.
# freq_idx selects a note from PENTATONIC_FREQS.
eggs = []

# Baskets at fixed cardinal-direction positions for easy navigation while
# testing. Each: {x, y, z, freq_idx, discovered, eggs}. `eggs` is a list
# of {hatch_timer} for eggs deposited in this basket.
# The three starting baskets sit at fixed cardinal positions with fixed
# pitches, so the opening of every park is learnable: east is always A3,
# north always D4, west always G4. Everything beyond these is generated as
# you wander (see maybe_spawn_basket).
INITIAL_BASKETS = (
    {'x':  40.0, 'y':   0.0, 'z': 0.0, 'freq_idx': 0, 'discovered': False},  # east  / A3
    {'x':   0.0, 'y':  40.0, 'z': 0.0, 'freq_idx': 2, 'discovered': False},  # north / D4
    {'x': -40.0, 'y':   0.0, 'z': 0.0, 'freq_idx': 4, 'discovered': False},  # west  / G4
)

baskets = [dict(b, eggs=[]) for b in INITIAL_BASKETS]

# Held eggs (player inventory). Each: {hatch_timer}. We don't track which
# spawned egg this came from once collected — they're fungible.
held = []

# Hatched birds wandering the world. Each: {x, y, z, freq_idx, home_x,
# home_y, wander_angle, next_call_at}.
birds = []


# ============================================================================
# Settings — live-adjustable knobs persisted to settings.json next to
# main.py. Accessible in-game via the Settings screen (press O) or, for
# master volume, the [ / ] hotkeys.
#
# Adding a new setting is a single entry in SETTINGS_MENU. The settings
# dict is built from defaults; load_settings() merges in the user's saved
# values; save_settings() writes the dict back atomically on every change.
# Reference settings[key] live in code — changes take effect on the next
# read.
#
# Two kinds of setting:
#   'range' — numeric value, adjusted in fixed steps via Left/Right.
#             Entry carries its own min, max, step, and format(value) for
#             how it's spoken aloud.
#   'bool'  — on/off; Left = off, Right = on, Space/Enter toggles.
# ============================================================================

SETTINGS_FILE = os.path.join(_script_dir, 'settings.json')

_pct = lambda v: f'{int(round(v * 100))} percent'

# Per-category volume sliders pair 1:1 with the sound categories declared
# in the sample bank. Each multiplies on top of master_volume at fire time
# (in _play). Default 1.0 = use the baseline volume= the fire_* helper
# passes; dial down to balance hot recordings, dial up for thin ones.
# Ambience is the exception — it plays continuously, so its baseline
# default is much lower so the bed doesn't drown out spatial cues.
_VOLUME_CATEGORIES = [
    ('vol_egg_call',         'Volume: egg calls',         1.0),
    ('vol_basket_chime',     'Volume: basket chimes',     1.0),
    ('vol_scan_egg_ping',    'Volume: scan egg pings',    1.0),
    ('vol_scan_basket_ping', 'Volume: scan basket pings', 1.0),
    ('vol_bird_call',        'Volume: bird calls',        1.0),
    ('vol_egg_collect',      'Volume: egg collect',       1.0),
    ('vol_refuse',           'Volume: refuse',            1.0),
    ('vol_basket_discover',  'Volume: basket discover',   1.0),
    ('vol_basket_deposit',   'Volume: basket deposit',    1.0),
    ('vol_basket_full',      'Volume: basket full',       1.0),
    ('vol_hatch_in_basket',  'Volume: hatch in basket',   1.0),
    ('vol_wild_bird_flyoff', 'Volume: wild bird flyoff',  1.0),
    ('vol_footstep',         'Volume: footsteps',         1.0),
    ('vol_egg_warning',      'Volume: egg warning',       1.0),
    ('vol_scan_start',       'Volume: scan start',        1.0),
    ('vol_bird_ambient',     'Volume: bird ambient',      1.0),
    ('vol_fumble',           'Volume: fumble',            1.0),
    ('vol_boot',             'Volume: boot',              1.0),
    ('vol_menu_open',        'Volume: menu open',         1.0),
    ('vol_menu_close',       'Volume: menu close',        1.0),
    ('vol_ambience',         'Volume: ambience',          0.1),
    ('vol_origin',           'Volume: origin chime',      1.0),
]

SETTINGS_MENU = [
    {'key': 'master_volume', 'label': 'Master volume', 'kind': 'range',
     'default': 1.0, 'min': 0.0, 'max': 2.0, 'step': 0.1, 'format': _pct},
] + [
    {'key': k, 'label': l, 'kind': 'range',
     'default': d, 'min': 0.0, 'max': 2.0, 'step': 0.1, 'format': _pct}
    for (k, l, d) in _VOLUME_CATEGORIES
] + [
    {'key': 'walk_speed', 'label': 'Walk speed', 'kind': 'range',
     'default': WALK_SPEED, 'min': 0.5, 'max': 5.0, 'step': 0.5,
     'format': lambda v: f'{v:.1f} meters per second'},
    {'key': 'turn_speed', 'label': 'Turn speed', 'kind': 'range',
     'default': TURN_SPEED, 'min': math.pi / 8, 'max': math.pi, 'step': math.pi / 8,
     'format': lambda v: f'{int(round(math.degrees(v)))} degrees per second'},
    # How far away a thing can be and still sound close. Low values make the
    # world drop away fast and quiet; high values keep distant eggs and
    # baskets audible at the cost of the distance cue itself. On a slider
    # because the only way to judge it is to listen, and the person listening
    # is not the person who wrote the number.
    {'key': 'audio_distance', 'label': 'Hearing distance', 'kind': 'range',
     'default': SOURCE_MIN_DISTANCE, 'min': 1.0, 'max': 60.0, 'step': 5.0,
     'format': lambda v: f'{v:.0f} meters at full volume'},
    # How long you have to carry an egg before it hatches. On a slider for
    # the same reason as hearing distance: 30 seconds is a number, and
    # whether it feels like a pleasant push or a hostile stopwatch is not
    # something the number can tell you.
    {'key': 'hatch_time', 'label': 'Time before an egg hatches', 'kind': 'range',
     'default': HATCH_TIMER_INITIAL, 'min': 15.0, 'max': 180.0, 'step': 15.0,
     'format': lambda v: f'{v:.0f} seconds'},
    {'key': 'enable_pickup',          'label': 'Egg pickup',      'kind': 'bool', 'default': True},
    {'key': 'enable_hand_hatching',   'label': 'Hand hatching',   'kind': 'bool', 'default': True},
    {'key': 'enable_basket_hatching', 'label': 'Basket hatching', 'kind': 'bool', 'default': True},
    {'key': 'enable_egg_calls',       'label': 'Egg calls',       'kind': 'bool', 'default': True},
    {'key': 'enable_basket_chimes',   'label': 'Basket chimes',   'kind': 'bool', 'default': True},
    {'key': 'enable_bird_calls',      'label': 'Bird calls',      'kind': 'bool', 'default': True},
    {'key': 'enable_footsteps',       'label': 'Footsteps',       'kind': 'bool', 'default': True},
    {'key': 'enable_egg_warnings',    'label': 'Egg warnings',    'kind': 'bool', 'default': True},
    {'key': 'enable_bird_ambient',    'label': 'Bird ambient',    'kind': 'bool', 'default': True},
    {'key': 'enable_ambience',        'label': 'Ambience',        'kind': 'bool', 'default': True},
    {'key': 'enable_origin_chime',    'label': 'Origin chime',    'kind': 'bool', 'default': True},
]

settings = {item['key']: item['default'] for item in SETTINGS_MENU}
_settings_by_key = {item['key']: item for item in SETTINGS_MENU}


def load_settings():
    """Merge settings.json on top of defaults. Unknown keys are ignored
    (forward-compat: removing a setting from SETTINGS_MENU leaves the value
    in the file harmlessly until the next save rewrites it)."""
    if not os.path.isfile(SETTINGS_FILE):
        return
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            saved = json.load(f)
    except Exception as exc:
        print(f'[settings] could not load: {exc}')
        return
    for k, v in saved.items():
        if k in _settings_by_key:
            settings[k] = v


def save_settings():
    """Atomic-ish: write to .tmp then os.replace."""
    try:
        tmp = SETTINGS_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
        os.replace(tmp, SETTINGS_FILE)
    except Exception as exc:
        print(f'[settings] could not save: {exc}')


load_settings()


def _value_speech(item, val):
    return item['format'](val) if item['kind'] == 'range' else ('on' if val else 'off')


def nudge_setting(key, direction):
    """Apply one step in the given direction (+1 / -1) to a range setting,
    clamp to [min, max], speak, persist. Called by both the in-screen
    Left/Right handlers and the dedicated [ / ] hotkeys."""
    item = _settings_by_key[key]
    new = max(item['min'], min(item['max'],
              round(settings[key] + item['step'] * direction, 6)))
    settings[key] = new
    say(f'{item["label"]}: {_value_speech(item, new)}.')
    save_settings()
    _sync_ambience()


# --- Settings screen state + handlers ---------------------------------------

_in_settings = False
_settings_focus = 0


def _speak_focused_setting():
    item = SETTINGS_MENU[_settings_focus]
    say(f'{item["label"]}: {_value_speech(item, settings[item["key"]])}.')


def open_settings():
    global _in_settings, _settings_focus, _settings_from_menu, _in_main_menu
    # Remember where we came from, so closing goes BACK there rather than
    # always dumping you into the world. Opening settings from the main menu
    # and being spat into a park you never asked to start would be a worse
    # bug than the one the main menu exists to fix.
    _settings_from_menu = _in_main_menu
    _in_main_menu = False
    _in_settings = True
    _settings_focus = 0
    fire_menu_open()
    say('Settings opened. Up and down to choose, left and right to change. '
        'Space toggles. Escape closes.')
    _speak_focused_setting()


def close_settings():
    global _in_settings
    _in_settings = False
    save_settings()
    fire_menu_close()
    if _settings_from_menu:
        open_main_menu(announce='Settings closed.')
    else:
        say('Settings closed.')


def settings_focus_move(direction):
    global _settings_focus
    _settings_focus = (_settings_focus + direction) % len(SETTINGS_MENU)
    _speak_focused_setting()


def settings_change(direction):
    """Left (direction=-1) or Right (direction=+1) on the focused setting."""
    item = SETTINGS_MENU[_settings_focus]
    if item['kind'] == 'range':
        nudge_setting(item['key'], direction)
    else:  # bool — directional set
        new = (direction > 0)
        settings[item['key']] = new
        say(f'{item["label"]}: {"on" if new else "off"}.')
        save_settings()
        _sync_ambience()


def settings_toggle():
    """Space/Enter inside settings — flip booleans, no-op on ranges."""
    item = SETTINGS_MENU[_settings_focus]
    if item['kind'] == 'bool':
        settings[item['key']] = not settings[item['key']]
        say(f'{item["label"]}: {"on" if settings[item["key"]] else "off"}.')
        save_settings()
        _sync_ambience()


# ============================================================================
# Main menu
# ============================================================================
#
# The game used to drop you straight into a fresh park, with settings
# reachable only by remembering that O opens them. A key you have to remember
# is a key you don't have — so the settings now live somewhere you ARRIVE at,
# rather than somewhere you have to know how to navigate to.
#
# It is also the place anything else that isn't "walk around a park" will go:
# loading a saved park, starting a fresh one over an existing one, whatever
# comes next. `main_menu_items()` builds the list fresh each time it's opened
# so a new entry is one tuple, not a new screen.
#
# Escape from the world comes BACK here rather than quitting outright. Escape
# used to exit the game immediately, which is a hard thing to undo by accident
# when you can't see a confirmation dialog.

_in_main_menu = False
_main_menu_focus = 0
_game_started = False
_settings_from_menu = False


def main_menu_items():
    """(label, action) pairs, rebuilt on each open.

    The first entry changes with context: before a park exists it starts one,
    afterwards it goes back to the one you left. Same position either way, so
    the muscle memory is 'Enter on the first item continues what I'm doing'.
    """
    items = []
    if _game_started:
        items.append(('Back to the park', resume_game))
        items.append(('Start a new park', restart_game))
    else:
        items.append(('Walk in the park', start_game))
    items.append(('Settings', open_settings))
    items.append(('Controls', speak_controls))
    items.append(('Quit', pyglet.app.exit))
    return items


def open_main_menu(announce='Main menu.'):
    global _in_main_menu, _main_menu_focus
    _in_main_menu = True
    _main_menu_focus = 0
    fire_menu_open()
    say(f'{announce} Up and down to choose, Enter to pick.')
    _speak_focused_menu_item()


def _speak_focused_menu_item():
    items = main_menu_items()
    label, _action = items[_main_menu_focus % len(items)]
    say(f'{label}.')


def main_menu_focus_move(direction):
    global _main_menu_focus
    _main_menu_focus = (_main_menu_focus + direction) % len(main_menu_items())
    _speak_focused_menu_item()


def main_menu_activate():
    items = main_menu_items()
    _label, action = items[_main_menu_focus % len(items)]
    action()


def _speak_world_intro():
    say('W A S D move. Q E turn. Space scans. F deposits. P reports status. '
        'Escape returns to the menu. Find eggs, deposit at baskets, '
        'hatch birds.')


def start_game():
    """First park of the session."""
    global _in_main_menu, _game_started
    _in_main_menu = False
    _game_started = True
    fire_menu_close()
    initial_spawn()
    update_listener()  # positional audio correct before the first tick
    say('The park is yours.')
    _speak_world_intro()


def resume_game():
    global _in_main_menu
    _in_main_menu = False
    fire_menu_close()
    say('Back in the park.')


def restart_game():
    """Throw away this park and spawn a fresh one.

    Speaks what it's about to destroy before doing it. There's no undo, and
    a menu item that quietly deletes an hour of collecting would be a cruel
    thing to sit one arrow key away from 'Back to the park'.
    """
    global _in_main_menu
    lost = len(birds)
    _in_main_menu = False
    fire_menu_close()
    reset_world()
    initial_spawn()
    update_listener()
    if lost:
        say(f'New park. The previous {lost} '
            f'bird{"s" if lost != 1 else ""} stayed behind.')
    else:
        say('New park.')
    _speak_world_intro()


# ============================================================================
# Capacity helpers
# ============================================================================

def discovered_count():
    return sum(1 for b in baskets if b['discovered'])


def player_carry_cap():
    """Starts at CARRY_START; +1 per CARRY_BUMP_EVERY baskets discovered."""
    return CARRY_START + (discovered_count() // CARRY_BUMP_EVERY)


def basket_cap():
    """Each basket holds N eggs where N = baskets discovered (min 1)."""
    return max(1, discovered_count())


# ============================================================================
# Synth source factories (all placeholders — replace with sample banks)
# ============================================================================

def _triangle(frequency, duration, attack=0.06, decay=None, release=0.04, peak=1.0):
    """Build a Triangle source with a pluck-shaped ADSR envelope."""
    if decay is None:
        decay = max(0.01, duration - attack - release)
    return pyglet.media.StaticSource(synthesis.Triangle(
        duration=duration, frequency=frequency, sample_rate=44100,
        envelope=synthesis.ADSREnvelope(
            attack=attack, decay=decay, release=release, sustain_amplitude=0.0,
        ),
    ))


def _sine(frequency, duration, attack=0.10, decay=None, release=0.10):
    if decay is None:
        decay = max(0.01, duration - attack - release)
    return pyglet.media.StaticSource(synthesis.Sine(
        duration=duration, frequency=frequency, sample_rate=44100,
        envelope=synthesis.ADSREnvelope(
            attack=attack, decay=decay, release=release, sustain_amplitude=0.0,
        ),
    ))


def _square(frequency, duration, attack=0.02, decay=None, release=0.02):
    if decay is None:
        decay = max(0.01, duration - attack - release)
    return pyglet.media.StaticSource(synthesis.Square(
        duration=duration, frequency=frequency, sample_rate=44100,
        envelope=synthesis.ADSREnvelope(
            attack=attack, decay=decay, release=release, sustain_amplitude=0.0,
        ),
    ))


def _noise_burst(duration, attack=0.05, decay=None, release=0.05):
    if decay is None:
        decay = max(0.01, duration - attack - release)
    return pyglet.media.StaticSource(synthesis.WhiteNoise(
        duration=duration, sample_rate=44100,
        envelope=synthesis.ADSREnvelope(
            attack=attack, decay=decay, release=release, sustain_amplitude=0.0,
        ),
    ))


# Per-note egg-call sources (one per pentatonic step). Triangle = "egg
# voice." Replace each with sample-bank lookup `samples['egg-call'][note]`.
_egg_call_sources = [_triangle(f, 0.5) for f in PENTATONIC_FREQS]

# Per-note basket chime sources — an octave below the eggs, and longer.
# Low tones need more cycles before the ear commits to a pitch, so a bass
# note at egg duration reads as a thud rather than a note.
_basket_chime_sources = [_sine(f * BASKET_OCTAVE, 1.3) for f in PENTATONIC_FREQS]

# Same note, different timbre, for a basket you've already found.
#
# Baskets used to be SILENT until discovered, so stepping on one switched its
# chime on and the world audibly changed. That gate had to go — you found a
# basket by walking within 3.5 m of it, so the beacon only ever switched on
# after you no longer needed it. But removing the gate took the reward with
# it: every basket now sounded identical before and after, and discovery
# became a single ding followed by nothing.
#
# So: pitch and position stay exactly the same, and only the WAVEFORM
# changes. A triangle carries odd harmonics a sine doesn't, so a found
# basket reads as brighter and closer without moving or changing note.
# You can still find the ones you haven't claimed, and you can still hear
# which ones you have.
# NOTE: found/unfound is a difference WITHIN the basket register, never a
# step out of it. An earlier attempt made a found basket a triangle at egg
# pitch, which made it sound like an egg — the two states were
# distinguishable but the whole category stopped being.
_basket_chime_found_sources = [_triangle(f * BASKET_OCTAVE, 1.3,
                                         attack=0.10, release=0.30)
                               for f in PENTATONIC_FREQS]

# Per-note scan pings. Briefer than ambient calls; the ping is a discrete
# "here is one item" signal.
_scan_egg_ping_sources = [_triangle(f, 0.3, attack=0.02, release=0.02) for f in PENTATONIC_FREQS]
# Basket pings follow baskets into the low register — a scan that answered in
# a different octave to the thing it was pointing at would undo the whole
# separation at the exact moment you're trying to tell them apart.
_scan_basket_ping_sources = [_sine(f * BASKET_OCTAVE, 0.6, attack=0.04, release=0.06)
                             for f in PENTATONIC_FREQS]

# Per-note bird ambient calls. Brighter triangle one octave up so birds
# read as overhead/airy compared to ground-level eggs.
_bird_call_sources = [_triangle(f * BIRD_OCTAVE, 0.4, attack=0.03, release=0.03)
                      for f in PENTATONIC_FREQS]

# Non-pitched one-shots.
_collect_source = _triangle(440.0, 0.35, attack=0.02, release=0.03)         # A4
# "Hands full" — you walked near an egg you can't carry.
#
# This was a square wave at 110 Hz with a 5 ms attack, which is a buzzsaw
# with a click on the front, played at the listener at half volume. It was
# frightening, and it fires CONSTANTLY: carry capacity starts at one, so
# every egg you pass while holding one sets it off.
#
# It is also the only sound in the game triggered by NOT acting. You didn't
# press anything and nothing went wrong — you walked past something you'll
# come back for. `fumble`, which fires when you press a key that genuinely
# doesn't work, was gentler than this. That was backwards.
#
# Now: sine, soft attack, quieter, and short. B3 is off the pentatonic and
# sits in the gap between egg A3 and egg C4, so it reads as "not a thing"
# rather than a note — and can't be mistaken for an egg you could take.
_refuse_source = _sine(246.94, 0.22, attack=0.05, release=0.12)  # B3, off-scale           # A2 buzz
_basket_discover_source = _sine(174.61, 1.4, attack=0.20, release=0.20)     # F3 — warm "found"
_deposit_source = _triangle(110.0, 0.4, attack=0.02, release=0.02)          # A2 thump
_basket_full_source = _square(146.83, 0.20, attack=0.005, release=0.02)     # D3 — denied
_hatch_in_basket_source = _sine(523.25, 1.6, attack=0.30, release=0.30)     # C5 — bright bloom
_wild_bird_flyoff_source = _noise_burst(WILD_BIRD_DISPERSAL,
                                         attack=0.05, decay=WILD_BIRD_DISPERSAL - 0.2, release=0.15)

# Footstep — short noise burst as the synth placeholder. Quiet by design;
# it fires every meter and shouldn't fatigue. Real samples will replace it.
_footstep_source = _noise_burst(0.12, attack=0.005, decay=0.05, release=0.06)

# Standing on a basket. Longer and softer than open ground — a shorter,
# duller burst reads as a step onto something that gives, rather than onto
# packed earth. It tells you you're ON the basket, which the chime can't:
# the chime is loudest nearby but never says "here", and standing exactly
# on the deposit spot is the one thing you actually need to know before
# pressing F.
_footstep_basket_source = _noise_burst(0.18, attack=0.01, decay=0.09, release=0.08)

# Egg warning — short distressed-coo placeholder (sine in mid-octave).
# Egg warning — the only alarm in the game. It means you are about to lose
# a bird, and it is the one sound that must never be mistaken for anything.
#
# It used to be a single sine at 659.25 Hz, which is also exactly the pitch
# and near enough the length of `scan start` — the blip you fire deliberately
# several times a minute. An alarm that sounds like the most common
# acknowledgement in the game is an alarm you learn to ignore.
#
# Now: two tones, FALLING, both deliberately off the pentatonic (Eb5 -> Bb4),
# so it is the only thing in the world that isn't in key. Falling because
# this reports something slipping away rather than asking for input, matching
# the shape used everywhere else. Two events also read as urgency in a way no
# single tone does, which is why smoke alarms and reversing lorries chirp
# rather than hold a note.
#
# Kept short — it fires once a second for the last five seconds, so it has to
# stay clear of its own next repeat and must not become punishing to hear
# five times.
_egg_warning_source = _triangle(622.25, 0.10, attack=0.005, release=0.03)   # Eb5
_egg_warning_second_source = _triangle(466.16, 0.15, attack=0.005, release=0.05)  # Bb4
EGG_WARNING_GAP = 0.11  # seconds between the two tones            # E5

# Scan start — quick chime marking the moment of pressing Space.
_scan_start_source = _triangle(659.25, 0.18, attack=0.01, release=0.04)         # E5

# Bird ambient — short noise burst, brighter than a footstep.
_bird_ambient_source = _noise_burst(0.18, attack=0.02, decay=0.08, release=0.06)

# Fumble — softer cousin of refuse for non-pickup "didn't work" moments.
_fumble_source = _square(196.00, 0.16, attack=0.005, release=0.02)              # G3

# Boot — a warm bloom that announces the game has loaded.
_boot_source = _sine(329.63, 1.2, attack=0.25, release=0.30)                    # E4

# Menu cues — rising for open, falling for close (the conventional shape).
_menu_open_source = _triangle(523.25, 0.20, attack=0.02, release=0.05)          # C5
_menu_close_source = _triangle(329.63, 0.20, attack=0.02, release=0.05)         # E4

# Origin chime — the fixed beacon at world (0, 0, 0).
#
# It used to be E3 (164.81 Hz), chosen as "outside the pentatonic's
# mid-octave but harmonically related". Moving baskets an octave down put
# a basket on exactly that pitch — and a found basket is a triangle, so the
# permanent landmark and a movable one became the same sound. Two beacons
# that can't be told apart are worse than one.
#
# Eb3 keeps the low-register bell character and is the one pitch in it that
# is NOT in A minor pentatonic, so it can never collide with a basket
# however the octave constant is tuned. Slightly outside the key on
# purpose: home should sound like home, not like another landmark.
ORIGIN_FREQ = 155.56  # Eb3 — deliberately not a pentatonic degree
_origin_source = _triangle(ORIGIN_FREQ, 1.5, attack=0.2, release=0.4)

# Ambience — looped under everything. The synth fallback is filtered noise
# (200 Hz lowpass) so the placeholder reads as distant air rather than
# full-spectrum hiss. A recorded `ambience.wav` plays as-recorded; only
# this synth fallback gets the lowpass.
def _make_lowpass_noise_source(duration_sec, cutoff_hz, sample_rate=44100):
    """Generate a Source of lowpass-filtered white noise via numpy + scipy.
    Falls back to plain white noise if either is missing — the game still
    boots, the bed is just harsher until samples replace it."""
    try:
        import numpy as np
        from scipy import signal as sp_signal
        import io
        import wave
    except ImportError:
        return pyglet.media.StaticSource(synthesis.WhiteNoise(
            duration=duration_sec, sample_rate=sample_rate,
        ))
    n = int(duration_sec * sample_rate)
    x = np.random.uniform(-1.0, 1.0, n).astype(np.float32)
    # 4th-order Butterworth lowpass at the cutoff.
    sos = sp_signal.butter(4, cutoff_hz, btype='low', fs=sample_rate, output='sos')
    y = sp_signal.sosfilt(sos, x).astype(np.float32)
    # The lowpass strips most of the energy from white noise (we kept only
    # the bottom ~200 Hz of ~22 kHz bandwidth), so normalize back up with
    # a touch of headroom so it doesn't clip on loud peaks.
    peak = float(np.abs(y).max())
    if peak > 0:
        y = y / peak * 0.8
    samples_int = (y * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples_int.tobytes())
    buf.seek(0)
    return pyglet.media.load('synth-ambience.wav', file=buf, streaming=False)


_ambience_source = _make_lowpass_noise_source(30.0, 200.0)


# ============================================================================
# Sample bank — looks for recorded .wav files in public/audio/samples and
# uses them in place of the synth placeholders above. Flat-pool per
# category: drop `{category}-N.wav` variants in (or a single
# `{category}.wav` for one-variant categories) and the engine picks one
# at random per fire. Empty categories fall back to the synth placeholder
# transparently. No pitch matching — the pentatonic still drives synth
# variation per egg / basket / bird while you're recording, but the
# recorded pool is flat and direction/HRTF carries the spatial cue.
# ============================================================================

SAMPLES_DIR = os.path.join(_script_dir, 'public', 'audio', 'samples')
os.makedirs(SAMPLES_DIR, exist_ok=True)

_SAMPLE_CATEGORIES = (
    'egg-call', 'basket-chime', 'basket-chime-found',
    'scan-egg-ping', 'scan-basket-ping', 'bird-call',
    'egg-collect', 'refuse', 'basket-discover', 'basket-deposit',
    'basket-full', 'hatch-in-basket', 'wild-bird-flyoff',
    'footstep', 'footstep-basket',
    'egg-warning', 'scan-start', 'bird-ambient', 'fumble',
    'boot', 'menu-open', 'menu-close', 'ambience', 'origin',
)

# Each category stores as [StaticSource, ...] — flat list of variants.
_sample_bank = {}


def _load_one_sample(path):
    try:
        return pyglet.media.load(path, streaming=False)
    except Exception as exc:
        print(f'[samples] could not load {os.path.basename(path)}: {exc}')
        return None


def _load_sample_bank():
    for category in _SAMPLE_CATEGORIES:
        paths = sorted(glob.glob(os.path.join(SAMPLES_DIR, f'{category}-*.wav')))
        single = os.path.join(SAMPLES_DIR, f'{category}.wav')
        if os.path.isfile(single):
            paths.insert(0, single)
        sources = [s for s in (_load_one_sample(p) for p in paths) if s]
        if sources:
            _sample_bank[category] = sources
    if _sample_bank:
        summary = [f'{cat}({len(v)})' for cat, v in _sample_bank.items()]
        print(f'[samples] loaded: {", ".join(summary)}')


def pick_source(category, *, fallback):
    """Return a random recorded source for this category, or fallback."""
    bank = _sample_bank.get(category)
    return random.choice(bank) if bank else fallback


_load_sample_bank()


def reload_sample_bank():
    """Re-scan public/audio/samples without restarting the game."""
    _sample_bank.clear()
    _load_sample_bank()
    total = sum(len(v) for v in _sample_bank.values())
    say(f'Reloaded {total} sample files.' if total else 'Sample bank empty.')


# ============================================================================
# Audio playback
# ============================================================================

# Active Player references — Python GCs locals before audio finishes, so
# keep them alive until pyglet's on_player_eos fires.
_active_players = set()

# One-shots that are meant to be AT the listener — your own footsteps, UI
# cues, collect/refuse. They have to be re-positioned every frame, exactly
# like the ambience bed, or they don't stay at you.
#
# Setting the position once at fire time is not enough, and this is why the
# steps sounded like they came from behind. In the update loop the order is:
#
#     player['x'] += ...        # you move
#     fire_footstep()           # source pinned to where you now are
#     update_listener()         # the LISTENER finally moves
#
# so the sound starts one frame ahead of the listener, the listener catches
# up, and then keeps walking forward for the rest of the burst while the
# source stays nailed to that patch of ground. Net effect: every step
# recedes behind you.
#
# The ambience bed was always co-located with the listener too, and never
# sounded wrong — because it alone got its position pushed every frame.
# That was the control that proves it's the update, not the co-location.
_listener_locked = set()


def _play(source, *, position=None, volume=1.0, category=None,
          min_distance=None, max_distance=None):
    p = pyglet.media.Player()
    p.queue(source)
    # Per-category volume multiplies on top of master volume. Category names
    # ('egg-call', etc.) map to setting keys by replacing '-' with '_' and
    # prefixing 'vol_'. Missing keys default to 1.0, so passing an unknown
    # category is a no-op (you just don't get a slider for it).
    cat_vol = 1.0
    if category:
        cat_vol = settings.get('vol_' + category.replace('-', '_'), 1.0)
    p.volume = volume * settings['master_volume'] * cat_vol
    # Spatialize. If the caller passed a world position, use it. Otherwise
    # snap the source to the listener's current position — without this,
    # the source defaults to OpenAL's world-origin (0,0,0) and the listener
    # walks away from it, so "non-positional" sounds end up sounding like
    # they're coming from wherever the player spawned. Co-locating source
    # with listener gives OpenAL a centered, max-gain render — i.e., the
    # "at the listener" behavior we actually want for footsteps, UI cues,
    # collect/refuse/etc.
    at_listener = position is None
    if at_listener:
        position = (player['x'], player['y'], player['z'])
    p.position = position
    # Distance attenuation. The defaults work for in-world objects (eggs,
    # baskets, birds — 80 m max). Origin chime overrides with a much
    # larger max so it stays audible as a navigational beacon.
    # Read from settings so the Hearing distance slider takes effect on the
    # very next sound, with no restart -- tuning this by ear is impossible if
    # you have to relaunch between each try.
    if min_distance is None:
        min_distance = settings.get('audio_distance', SOURCE_MIN_DISTANCE)
    p.min_distance = min_distance
    p.max_distance = max_distance if max_distance is not None else SOURCE_MAX_DISTANCE

    def _on_eos():
        _active_players.discard(p)
        _listener_locked.discard(p)

    p.push_handlers(on_player_eos=_on_eos)
    _active_players.add(p)
    if at_listener:
        _listener_locked.add(p)
    p.play()


# --- One sound-effect function per "category." Swap each to use samples
# without changing any caller code. -----------------------------------------

def fire_egg_call(egg):
    src = pick_source('egg-call', fallback=_egg_call_sources[egg['freq_idx']])
    _play(src, position=(egg['x'], egg['y'], egg['z']), volume=0.6,
          category='egg-call')


def fire_basket_chime(basket):
    """Chime the given basket, in whichever voice matches its state.

    Two categories so a recorded sample bank can distinguish them too:
    drop `basket-chime-found-1.wav` and the found voice uses your recording
    while unfound baskets keep theirs. If you only record `basket-chime`,
    the found voice falls back to the synth triangle rather than silently
    collapsing both states into one sound.
    """
    if basket['discovered']:
        src = pick_source(
            'basket-chime-found',
            fallback=_basket_chime_found_sources[basket['freq_idx']])
    else:
        src = pick_source(
            'basket-chime',
            fallback=_basket_chime_sources[basket['freq_idx']])
    # Sample category varies; VOLUME category deliberately does not. _play
    # looks a category up as `vol_<name>` and silently defaults a miss to
    # 1.0, so a separate volume category here would mean "Volume: basket
    # chimes" quietly stopped applying to half the baskets in the world.
    _play(src, position=(basket['x'], basket['y'], basket['z']), volume=0.5,
          category='basket-chime')


def fire_collect_sound():
    _play(pick_source('egg-collect', fallback=_collect_source), volume=0.5,
          category='egg-collect')


def fire_refuse_sound():
    # Quieter than the other cues on purpose. This one fires more often than
    # anything except footsteps, and it's reporting an ordinary situation,
    # not a mistake.
    _play(pick_source('refuse', fallback=_refuse_source), volume=0.3,
          category='refuse')


def fire_basket_discover(basket):
    src = pick_source('basket-discover', fallback=_basket_discover_source)
    _play(src, position=(basket['x'], basket['y'], basket['z']), volume=0.7,
          category='basket-discover')


def fire_deposit_sound(basket):
    src = pick_source('basket-deposit', fallback=_deposit_source)
    _play(src, position=(basket['x'], basket['y'], basket['z']), volume=0.7,
          category='basket-deposit')


def fire_basket_full_sound():
    _play(pick_source('basket-full', fallback=_basket_full_source), volume=0.5,
          category='basket-full')


def fire_scan_egg_ping(egg):
    src = pick_source('scan-egg-ping', fallback=_scan_egg_ping_sources[egg['freq_idx']])
    _play(src, position=(egg['x'], egg['y'], egg['z']), volume=0.7,
          category='scan-egg-ping')


def fire_scan_basket_ping(basket):
    src = pick_source('scan-basket-ping', fallback=_scan_basket_ping_sources[basket['freq_idx']])
    _play(src, position=(basket['x'], basket['y'], basket['z']), volume=0.7,
          category='scan-basket-ping')


def fire_hatch_in_basket(basket):
    src = pick_source('hatch-in-basket', fallback=_hatch_in_basket_source)
    _play(src, position=(basket['x'], basket['y'], basket['z']), volume=0.7,
          category='hatch-in-basket')


def fire_wild_bird_flyoff():
    # Non-positional — the bird flies off and away, plays at the listener
    # since you're losing it.
    _play(pick_source('wild-bird-flyoff', fallback=_wild_bird_flyoff_source),
          volume=0.5, category='wild-bird-flyoff')


def fire_bird_call(bird):
    src = pick_source('bird-call', fallback=_bird_call_sources[bird['freq_idx']])
    _play(src, position=(bird['x'], bird['y'], bird['z']), volume=0.5,
          category='bird-call')


def fire_footstep():
    # Non-positional — these are *your* footsteps, they play at the listener.
    #
    # The surface changes on BASKET_DEPOSIT_RADIUS (via current_basket, the
    # same test F uses), not the wider discovery radius — so the ground
    # changes at exactly the point depositing starts working. Hearing it
    # change and then being told 'not standing on a basket' would be worse
    # than no cue at all.
    #
    # One volume category for both surfaces: "Volume: footsteps" has to mean
    # all of them. Only the sample category and the synth fallback change.
    if current_basket() is not None:
        src = pick_source('footstep-basket', fallback=_footstep_basket_source)
    else:
        src = pick_source('footstep', fallback=_footstep_source)
    _play(src, volume=0.3, category='footstep')


def fire_egg_warning(*, position=None):
    """The alarm. Fires from the egg's location for basketed eggs, at the
    listener for held ones — same category either way, so one recorded take
    covers both contexts (anticipation and anxiety).

    A RECORDED sample plays once, whole. Only the synth placeholder is built
    from two scheduled tones: a recording already contains whatever shape its
    author wanted, and firing the second tone over it would talk across
    someone's take.
    """
    recorded = _sample_bank.get('egg-warning')
    if recorded:
        _play(random.choice(recorded), position=position, volume=0.5,
              category='egg-warning')
        return

    _play(_egg_warning_source, position=position, volume=0.5,
          category='egg-warning')
    # Second tone scheduled rather than concatenated: pyglet sources can't be
    # joined without rebuilding the wave by hand, and a scheduled follow-up
    # costs nothing. Position is captured so a basketed warning stays put.
    pyglet.clock.schedule_once(
        lambda _dt: _play(_egg_warning_second_source, position=position,
                          volume=0.5, category='egg-warning'),
        EGG_WARNING_GAP)


def fire_scan_start():
    _play(pick_source('scan-start', fallback=_scan_start_source),
          volume=0.4, category='scan-start')


def fire_bird_ambient(bird):
    _play(pick_source('bird-ambient', fallback=_bird_ambient_source),
          position=(bird['x'], bird['y'], bird['z']),
          volume=0.4, category='bird-ambient')


def fire_fumble():
    _play(pick_source('fumble', fallback=_fumble_source),
          volume=0.4, category='fumble')


def fire_boot():
    _play(pick_source('boot', fallback=_boot_source),
          volume=0.6, category='boot')


def fire_menu_open():
    _play(pick_source('menu-open', fallback=_menu_open_source),
          volume=0.4, category='menu-open')


def fire_menu_close():
    _play(pick_source('menu-close', fallback=_menu_close_source),
          volume=0.4, category='menu-close')


def fire_origin_chime():
    # Beacon at world origin. Extended max-distance so it remains audible
    # as a navigational landmark from anywhere on the walking plane.
    _play(pick_source('origin', fallback=_origin_source),
          position=(0.0, 0.0, 0.0), volume=0.5, category='origin',
          max_distance=ORIGIN_MAX_DISTANCE)


# --- Ambience: continuous looped bed, not one-shot ---------------------------
# Pyglet's Player.loop replays the same source forever. We pick the source
# once at boot (random pick if the user dropped variants like ambience-1.wav)
# and keep that one player alive across settings changes — only its .volume
# property and play/pause state update when settings change.

_ambience_player = None


def _resolve_ambience_source():
    bank = _sample_bank.get('ambience')
    if bank:
        return random.choice(bank)
    return _ambience_source


def _sync_ambience():
    """Reconcile the ambience player with current settings. Safe to call
    after any setting change — if nothing relevant changed it's a no-op."""
    global _ambience_player
    enabled = settings['enable_ambience']
    target_vol = settings['master_volume'] * settings.get('vol_ambience', 1.0)

    if enabled:
        if _ambience_player is None:
            _ambience_player = pyglet.media.Player()
            _ambience_player.queue(_resolve_ambience_source())
            _ambience_player.loop = True
            # Seed at current player position. update_listener pushes
            # further updates each frame, so the bed follows the player.
            _ambience_player.position = (player['x'], player['y'], player['z'])
            _ambience_player.min_distance = SOURCE_MIN_DISTANCE
            _ambience_player.max_distance = SOURCE_MAX_DISTANCE
        _ambience_player.volume = target_vol
        if not _ambience_player.playing:
            _ambience_player.play()
    else:
        if _ambience_player is not None and _ambience_player.playing:
            _ambience_player.pause()


# ============================================================================
# Listener
# ============================================================================

_listener = pyglet.media.get_audio_driver().get_listener()


def update_listener():
    pos = (player['x'], player['y'], player['z'])
    _listener.position = pos
    _listener.forward_orientation = (
        math.cos(player['yaw']), math.sin(player['yaw']), 0.0,
    )
    _listener.up_orientation = (0.0, 0.0, 1.0)
    # Ambience is a continuous loop player created once at boot; one-shot
    # _play calls snap to the listener at fire time, but the ambience
    # source needs its position updated every frame so the bed follows
    # the player around the world instead of staying at the spawn point.
    if _ambience_player is not None:
        _ambience_player.position = pos
    # Same treatment for the at-the-listener one-shots. Iterate a copy: a
    # player can reach end-of-stream and drop out of the set mid-loop.
    for p in tuple(_listener_locked):
        try:
            p.position = pos
        except Exception:
            _listener_locked.discard(p)


# ============================================================================
# Egg lifecycle
# ============================================================================

def spawn_egg_far_from_player():
    """Place a new egg at a random position roughly EGG_SPAWN_MIN..MAX away."""
    angle = random.uniform(0, 2 * math.pi)
    dist = random.uniform(EGG_SPAWN_MIN, EGG_SPAWN_MAX)
    return {
        'x': player['x'] + math.cos(angle) * dist,
        'y': player['y'] + math.sin(angle) * dist,
        'z': 0.0,
        'freq_idx': random.randrange(len(PENTATONIC_FREQS)),
        'hatch_timer': settings['hatch_time'],
    }


def reset_world():
    """Wipe every trace of the current park, ready for a fresh spawn.

    Everything mutable in World state gets cleared here. If you add a new
    piece of per-park state up there, clear it here too — a leftover that
    survives a restart shows up as a ghost: a bird calling from a park that
    no longer exists, and no way to work out where it came from.

    Lists are emptied in place rather than rebound, because other modules
    and closures hold references to these exact objects.
    """
    eggs.clear()
    held.clear()
    birds.clear()
    # Baskets are REBUILT, not just reset: generated ones have to go, or a
    # new park inherits every basket the last one grew.
    baskets.clear()
    baskets.extend(dict(b, eggs=[]) for b in INITIAL_BASKETS)
    player.update({'x': 0.0, 'y': 0.0, 'z': 0.0, 'yaw': 0.0})


def initial_spawn():
    """Stagger initial eggs in known directions.

    Assumes an empty world — it only appends. Call `reset_world()` first if
    a park already exists, or you get two parks overlaid on each other.
    """
    presets = [
        (30.0,   0.0),
        ( 0.0,  30.0),
        (-30.0,  0.0),
        ( 0.0, -30.0),
    ]
    for i in range(NUM_EGGS):
        x, y = presets[i] if i < len(presets) else (
            random.uniform(-50, 50), random.uniform(-50, 50)
        )
        eggs.append({
            'x': x, 'y': y, 'z': 0.0,
            'freq_idx': i % len(PENTATONIC_FREQS),
            'hatch_timer': settings['hatch_time'],
        })


def try_collect_eggs():
    """Auto-collect any egg within COLLECT_RADIUS, respecting carry cap."""
    if not settings['enable_pickup']:
        return
    for egg in list(eggs):
        dx = egg['x'] - player['x']
        dy = egg['y'] - player['y']
        if math.hypot(dx, dy) > COLLECT_RADIUS:
            continue
        if len(held) >= player_carry_cap():
            fire_refuse_sound()
            say(f'Hands full. {len(held)} eggs held.')
            # Don't dequeue — egg stays so the player can come back after
            # depositing.
            return
        # Collect: move this egg's remaining hatch timer into hand.
        # next_warning is a per-egg countdown to the next warning chirp;
        # it only matters once hatch_timer drops below WARNING_WINDOW.
        # The clock genuinely starts when you lift it: an egg lying in the
        # world never ticks (only held and basketed eggs count down), so its
        # stored timer is still exactly what it was given at spawn. Reading
        # the setting here means the slider takes effect on the very next egg
        # you pick up instead of the next one that spawns -- which is what
        # you need when you're tuning it by feel.
        held.append({'hatch_timer': settings['hatch_time'], 'next_warning': 0.0})
        fire_collect_sound()
        say(f'Egg collected. {len(held)} of {player_carry_cap()} held.')
        eggs.remove(egg)
        eggs.append(spawn_egg_far_from_player())
        return


# ============================================================================
# Basket lifecycle
# ============================================================================

def unfound_baskets_in_reach():
    """Unclaimed baskets close enough to be heard from where the player is.

    'In reach' is the audible radius rather than some larger planning
    distance on purpose: a basket you cannot hear may as well not exist, so
    it shouldn't count toward the world feeling stocked.
    """
    return [b for b in baskets
            if not b['discovered']
            and math.hypot(b['x'] - player['x'], b['y'] - player['y']) <= BASKET_AUDIBLE]


def forget_distant_baskets():
    """Drop unclaimed baskets the player has left far behind.

    ONLY undiscovered ones, and only well outside earshot. A discovered
    basket is part of the park — it holds eggs, it counts toward capacity,
    and you may be walking back to it. Removing one of those would delete
    eggs mid-hatch, from a place the player is deliberately returning to.
    """
    for b in list(baskets):
        if b['discovered']:
            continue
        if math.hypot(b['x'] - player['x'], b['y'] - player['y']) > BASKET_FORGET_DISTANCE:
            baskets.remove(b)


def maybe_spawn_basket():
    """Keep unclaimed baskets available near wherever the player has walked.

    Called every frame; almost always a cheap count that does nothing. One
    basket per call at most, so wandering into empty territory fills it in
    over a few seconds rather than dropping a cluster at once.

    Placement is a random bearing at BASKET_SPAWN_MIN..MAX. Never closer
    than the minimum, so a basket can't appear underfoot — a chime starting
    up two metres away from a spot you already walked past reads as a bug,
    not as discovery.
    """
    if len(baskets) >= BASKET_MAX_TOTAL:
        return
    if len(unfound_baskets_in_reach()) >= BASKET_TARGET_UNFOUND:
        return

    for _attempt in range(BASKET_PLACE_ATTEMPTS):
        angle = random.uniform(0.0, 2.0 * math.pi)
        dist = random.uniform(BASKET_SPAWN_MIN, BASKET_SPAWN_MAX)
        x = player['x'] + math.cos(angle) * dist
        y = player['y'] + math.sin(angle) * dist
        if any(math.hypot(b['x'] - x, b['y'] - y) < BASKET_MIN_SEPARATION
               for b in baskets):
            continue
        baskets.append({
            'x': x, 'y': y, 'z': 0.0,
            'freq_idx': len(baskets) % len(PENTATONIC_FREQS),
            'discovered': False,
            'eggs': [],
        })
        return
    # Ran out of attempts: the area is crowded. Nothing to report — the next
    # frame tries again, and by then the player has usually moved.


def try_discover_basket():
    """Walk within BASKET_DISCOVER_RADIUS of an undiscovered basket → discover."""
    for b in baskets:
        if b['discovered']:
            continue
        dx = b['x'] - player['x']
        dy = b['y'] - player['y']
        if math.hypot(dx, dy) <= BASKET_DISCOVER_RADIUS:
            b['discovered'] = True
            fire_basket_discover(b)
            n = discovered_count()
            # No denominator any more. The total grows as you walk, so
            # "3 of 5" followed later by "4 of 7" reads as the goal moving
            # away from you — the opposite of what finding one means.
            say(
                f'Basket discovered. {n} found. '
                f'Basket capacity {basket_cap()}. '
                f'Carry capacity {player_carry_cap()}.'
            )
            return


def try_deposit():
    """Bound to F. Drop everything from hand into the basket you're on."""
    on = current_basket()
    if on is None:
        fire_fumble()
        say('Not standing on a basket.')
        return
    if not on['discovered']:
        # Standing on an undiscovered basket — discover first, then deposit
        # can be retried on next press.
        try_discover_basket()
        return
    if not held:
        fire_fumble()
        say('No eggs to deposit.')
        return
    cap = basket_cap()
    room = cap - len(on['eggs'])
    if room <= 0:
        fire_basket_full_sound()
        say(f'Basket full. Holds {cap}.')
        return
    n = min(room, len(held))
    for _ in range(n):
        on['eggs'].append(held.pop(0))
    fire_deposit_sound(on)
    if n < len(held) + n:
        say(f'Deposited {n}. Basket {len(on["eggs"])} of {cap}. {len(held)} still held.')
    else:
        say(f'Deposited {n}. Basket {len(on["eggs"])} of {cap}.')


def current_basket():
    """Return the basket the player is standing on, or None."""
    for b in baskets:
        if math.hypot(b['x'] - player['x'], b['y'] - player['y']) <= BASKET_DEPOSIT_RADIUS:
            return b
    return None


# ============================================================================
# Scan
# ============================================================================

def try_scan():
    """Bound to Space. Ping every item within SCAN_RANGE, closest first."""
    fire_scan_start()
    items = []
    for egg in eggs:
        d = math.hypot(egg['x'] - player['x'], egg['y'] - player['y'])
        if d <= SCAN_RANGE:
            items.append(('egg', d, egg))
    for b in baskets:
        d = math.hypot(b['x'] - player['x'], b['y'] - player['y'])
        if d <= SCAN_RANGE:
            items.append(('basket', d, b))

    if not items:
        fire_fumble()
        say('Nothing in range.')
        return

    items.sort(key=lambda t: t[1])
    say(f'Scanning. {len(items)} items in range.')

    # Schedule each ping at a delay proportional to its distance, so
    # close items ping immediately and far items ping later in the sweep.
    max_dist = items[-1][1] if items[-1][1] > 0 else 1.0
    for kind, dist, item in items:
        delay = (dist / max_dist) * SCAN_DURATION
        if kind == 'egg':
            pyglet.clock.schedule_once(lambda dt, e=item: fire_scan_egg_ping(e), delay)
        else:
            pyglet.clock.schedule_once(lambda dt, b=item: fire_scan_basket_ping(b), delay)


# ============================================================================
# Hatching + birds
# ============================================================================

def hatch_into_wild_bird():
    """A held egg ran out — bird flies off, not yours."""
    fire_wild_bird_flyoff()
    say('An egg in your hand hatched. The bird flew off.')


def hatch_into_your_bird(basket):
    """A basketed egg ran out — bird is yours, joins the wandering set."""
    now_t = time.monotonic()
    bird = {
        'x': basket['x'] + random.uniform(-1, 1),
        'y': basket['y'] + random.uniform(-1, 1),
        'z': 0.0,
        'freq_idx': random.randrange(len(PENTATONIC_FREQS)),
        'home_x': basket['x'],
        'home_y': basket['y'],
        'wander_angle': random.uniform(0, 2 * math.pi),
        'next_call_at': now_t + random.uniform(2.0, 4.0),
        'next_ambient_at': now_t + random.uniform(
            BIRD_AMBIENT_MIN_INTERVAL, BIRD_AMBIENT_MAX_INTERVAL),
    }
    birds.append(bird)
    fire_hatch_in_basket(basket)
    say(f'A bird hatched. {len(birds)} birds in the park.')


def tick_hatching(dt):
    # Held eggs — timer only advances if hand-hatching is enabled, so
    # turning the toggle off effectively freezes any held egg indefinitely.
    if settings['enable_hand_hatching']:
        for h in list(held):
            h['hatch_timer'] -= dt
            if h['hatch_timer'] <= 0:
                held.remove(h)
                hatch_into_wild_bird()
                continue
            # Warning chirp while the held egg is in its last seconds.
            # Fires once per WARNING_INTERVAL — non-positional since the
            # egg is in your hand.
            if h['hatch_timer'] <= WARNING_WINDOW:
                h['next_warning'] -= dt
                if h['next_warning'] <= 0:
                    if settings['enable_egg_warnings']:
                        fire_egg_warning()
                    h['next_warning'] = WARNING_INTERVAL

    # Basket eggs — same pattern. Disabling basket-hatching means deposited
    # eggs just sit there forever; the basket becomes a museum.
    if settings['enable_basket_hatching']:
        for b in baskets:
            for he in list(b['eggs']):
                he['hatch_timer'] -= dt
                if he['hatch_timer'] <= 0:
                    b['eggs'].remove(he)
                    hatch_into_your_bird(b)
                    continue
                # Same warning, but positional at the basket so the player
                # can hear which basket is about to pop. Emotionally this
                # is the *positive* warning (a bird is incoming) — same
                # sample category, the recording can carry either valence.
                if he['hatch_timer'] <= WARNING_WINDOW:
                    he['next_warning'] = he.get('next_warning', 0.0) - dt
                    if he['next_warning'] <= 0:
                        if settings['enable_egg_warnings']:
                            fire_egg_warning(position=(b['x'], b['y'], b['z']))
                        he['next_warning'] = WARNING_INTERVAL


def tick_birds(dt):
    now_t = time.monotonic()
    for bird in birds:
        # Wander. Random-walk angle drift + forward motion.
        bird['wander_angle'] += random.uniform(-0.5, 0.5) * dt
        dx = math.cos(bird['wander_angle']) * BIRD_WANDER_SPEED * dt
        dy = math.sin(bird['wander_angle']) * BIRD_WANDER_SPEED * dt
        nx = bird['x'] + dx
        ny = bird['y'] + dy
        # Stay within wander radius of home — if drifting too far, turn back.
        if math.hypot(nx - bird['home_x'], ny - bird['home_y']) <= BIRD_WANDER_RADIUS:
            bird['x'] = nx
            bird['y'] = ny
        else:
            # Bounce wander angle toward home.
            bird['wander_angle'] = math.atan2(
                bird['home_y'] - bird['y'], bird['home_x'] - bird['x']
            )

        # Periodic call. Same toggle-off-still-ticks pattern as the egg
        # calls and basket chimes.
        if now_t >= bird['next_call_at']:
            if settings['enable_bird_calls']:
                fire_bird_call(bird)
            bird['next_call_at'] = now_t + random.uniform(
                BIRD_CALL_MIN_INTERVAL, BIRD_CALL_MAX_INTERVAL
            )

        # Wing-flap / rustle / small movement noises between calls.
        # Scheduled independently so the two streams interleave instead of
        # falling into a predictable rhythm with the calls.
        if now_t >= bird.get('next_ambient_at', 0):
            if settings['enable_bird_ambient']:
                fire_bird_ambient(bird)
            bird['next_ambient_at'] = now_t + random.uniform(
                BIRD_AMBIENT_MIN_INTERVAL, BIRD_AMBIENT_MAX_INTERVAL
            )


# ============================================================================
# Window + input
# ============================================================================

window = pyglet.window.Window(width=400, height=200, caption='Egg Park')
keys = key.KeyStateHandler()
window.push_handlers(keys)


# The controls, in the game, spoken. They were only ever written in the
# module docstring at the top of this file -- which is a comment, in source,
# and so is readable by everyone except the person the game is for. A key
# binding you cannot ask about is a key binding you have to have memorised
# before you start, and that is not a thing anyone should be asked to do.
#
# Grouped movement-first, since that is what you need in the first ten
# seconds, and each pair reads as one phrase rather than a list of letters.
CONTROL_HELP = (
    ('Move', 'W or up arrow forward. S or down arrow back. '
             'A step left. D step right.'),
    ('Turn', 'Q or left arrow turns left. E or right arrow turns right.'),
    ('Do', 'Space scans for eggs. F deposits at a basket. '
           'P speaks your status.'),
    ('Set up', 'O opens settings. Left and right square brackets '
               'lower and raise the volume. R reloads the sample bank.'),
    ('Leave', 'Escape goes back to the main menu, where Quit lives. '
              'H repeats these controls.'),
)


def speak_controls():
    say('Controls. ' + ' '.join(body for _label, body in CONTROL_HELP))


def on_key_press(symbol, modifiers):
    """Returns EVENT_HANDLED for anything it consumes. THIS IS LOAD-BEARING.

    pyglet's own `Window.on_key_press` quits the application on Escape. Our
    handler is pushed above it, but pyglet keeps passing an event DOWN the
    stack until a handler returns EVENT_HANDLED — so returning None meant
    our code ran and then pyglet quit anyway, from the park, from settings,
    from anywhere. Escape appeared to be hard-wired to "exit", and no amount
    of changing what it does here could have fixed it.

    Return EVENT_HANDLED for every key this function acts on, or Escape goes
    back to quitting.

    Equally: DON'T return it for keys we don't act on. `keys`
    (KeyStateHandler) sits below us and is what movement reads, so swallowing
    everything unconditionally would leave W A S D dead.
    """
    # Main menu consumes its own keys. Checked FIRST: settings can be opened
    # from here, and the world must not see any of it.
    if _in_main_menu:
        if symbol == key.UP:
            main_menu_focus_move(-1)
        elif symbol == key.DOWN:
            main_menu_focus_move(+1)
        elif symbol == key.RETURN or symbol == key.SPACE:
            main_menu_activate()
        elif symbol == key.ESCAPE:
            # Escape closes the menu if there's a park to go back to, and
            # otherwise does nothing. It deliberately does NOT quit: this is
            # the first screen of the game, and quitting on the key people
            # press to mean "never mind" is a bad trade.
            if _game_started:
                resume_game()
            else:
                say('Choose an option, or pick Quit to leave.')
        else:
            return None  # not ours; let it fall through
        return pyglet.event.EVENT_HANDLED

    # Settings screen consumes its own keys; nothing falls through to game.
    if _in_settings:
        if symbol == key.ESCAPE or symbol == key.O:
            close_settings()
        elif symbol == key.UP:
            settings_focus_move(-1)
        elif symbol == key.DOWN:
            settings_focus_move(+1)
        elif symbol == key.LEFT:
            settings_change(-1)
        elif symbol == key.RIGHT:
            settings_change(+1)
        elif symbol == key.SPACE or symbol == key.RETURN:
            settings_toggle()
        else:
            return None  # not ours; let it fall through
        return pyglet.event.EVENT_HANDLED

    if symbol == key.ESCAPE:
        # Back to the menu, not out of the game. Quitting outright on Escape
        # is a hard thing to undo by accident with no visible confirmation.
        open_main_menu()
    elif symbol == key.H or symbol == key.SLASH:
        speak_controls()
    elif symbol == key.P:
        announce_status()
    elif symbol == key.F:
        try_deposit()
    elif symbol == key.SPACE:
        try_scan()
    elif symbol == key.R:
        reload_sample_bank()
    elif symbol == key.O:
        open_settings()
    elif symbol == key.BRACKETLEFT:
        nudge_setting('master_volume', -1)
    elif symbol == key.BRACKETRIGHT:
        nudge_setting('master_volume', +1)
    else:
        # Movement keys and anything else we don't act on: fall through, so
        # KeyStateHandler below us still sees them.
        return None
    return pyglet.event.EVENT_HANDLED


def on_activate():
    say('Window focused.')


def on_deactivate():
    say('Window lost focus. Alt-tab back to the Egg Park window.')


# Push our custom handlers as a separate frame from KeyStateHandler.
# Using @window.event would clobber the keys frame in pyglet 2.x.
window.push_handlers(
    on_key_press=on_key_press,
    on_activate=on_activate,
    on_deactivate=on_deactivate,
)


# ============================================================================
# Update loop
# ============================================================================

_next_egg_call_at = 0.0
_next_basket_chime_at = 0.0
_next_origin_chime_at = 0.0
_dist_since_step = 0.0  # accumulates walked meters; fires footstep at STEP_DISTANCE
_clock_start = time.monotonic()


def now():
    return time.monotonic() - _clock_start


def update(dt):
    global _next_egg_call_at, _next_basket_chime_at, _next_origin_chime_at, _dist_since_step

    # Settings screen pauses the world entirely — no movement, no ticks,
    # no calls. Hatch timers don't advance, so opening settings mid-game
    # doesn't accidentally lose a held egg.
    if _in_settings or _in_main_menu:
        return

    # Turn.
    turn_speed = settings['turn_speed']
    if keys[key.Q] or keys[key.LEFT]:
        player['yaw'] += turn_speed * dt
    if keys[key.E] or keys[key.RIGHT]:
        player['yaw'] -= turn_speed * dt

    # Move (forward + strafe).
    move_forward = (1 if keys[key.W] or keys[key.UP] else 0) - \
                   (1 if keys[key.S] or keys[key.DOWN] else 0)
    move_right = (1 if keys[key.D] else 0) - (1 if keys[key.A] else 0)

    if move_forward != 0 or move_right != 0:
        dx = math.cos(player['yaw']) * move_forward + math.sin(player['yaw']) * move_right
        dy = math.sin(player['yaw']) * move_forward - math.cos(player['yaw']) * move_right
        length = math.hypot(dx, dy)
        walk_speed = settings['walk_speed']
        player['x'] += (dx / length) * walk_speed * dt
        player['y'] += (dy / length) * walk_speed * dt

        # Footstep cadence: accumulate walked distance, fire each time we
        # cross STEP_DISTANCE. Tying cadence to distance (not time) means
        # adjusting walk_speed naturally changes step rate. Toggle-off
        # still ticks the counter so re-enabling mid-walk doesn't burst.
        _dist_since_step += walk_speed * dt
        if _dist_since_step >= STEP_DISTANCE:
            _dist_since_step -= STEP_DISTANCE
            if settings['enable_footsteps']:
                fire_footstep()
    else:
        # Standing still — reset so we don't fire a half-step the moment
        # the player starts moving again. Each fresh walk gets a full
        # stride before the first footstep.
        _dist_since_step = 0.0

    update_listener()

    # Pickups + discovery happen passively while walking.
    try_collect_eggs()
    try_discover_basket()
    forget_distant_baskets()
    maybe_spawn_basket()

    # Hatching timers.
    tick_hatching(dt)
    tick_birds(dt)

    t = now()

    # Egg call — round-robin over all eggs in audible range. Each call
    # fires from the nearest egg; the nearest changes as you move so you
    # get the cocktail-party effect of multiple eggs in the world.
    # The interval still ticks when the toggle is off so re-enabling
    # doesn't trigger a burst.
    if t >= _next_egg_call_at:
        if settings['enable_egg_calls']:
            nearest = nearest_audible_egg()
            if nearest:
                fire_egg_call(nearest)
        _next_egg_call_at = t + EGG_CALL_INTERVAL

    # Origin chime — fixed-interval beacon at world (0, 0, 0). Fires
    # whether or not the player is in range; OpenAL's distance attenuation
    # at max_distance=500 handles audibility falloff naturally.
    if t >= _next_origin_chime_at:
        if settings['enable_origin_chime']:
            fire_origin_chime()
        _next_origin_chime_at = t + ORIGIN_CHIME_INTERVAL

    # Basket chime — proximity-scaled per the nearest discovered basket.
    # Same toggle-off-still-ticks pattern.
    if t >= _next_basket_chime_at:
        nearest_b = nearest_audible_basket()
        if nearest_b:
            if settings['enable_basket_chimes']:
                fire_basket_chime(nearest_b)
            d = math.hypot(nearest_b['x'] - player['x'], nearest_b['y'] - player['y'])
            proximity = max(0.0, 1.0 - d / BASKET_AUDIBLE)
            interval = (BASKET_CHIME_INTERVAL_FAR -
                        (BASKET_CHIME_INTERVAL_FAR - BASKET_CHIME_INTERVAL_NEAR) * proximity)
            _next_basket_chime_at = t + interval
        else:
            _next_basket_chime_at = t + BASKET_CHIME_INTERVAL_FAR


def nearest_audible_egg():
    best = None
    best_d = float('inf')
    for egg in eggs:
        d = math.hypot(egg['x'] - player['x'], egg['y'] - player['y'])
        if d > EGG_AUDIBLE:
            continue
        if d < best_d:
            best = egg
            best_d = d
    return best


def nearest_audible_basket():
    """Nearest basket within audible range, discovered or not.

    It used to skip undiscovered ones, which made the chime useless as a way
    to FIND a basket: you discovered one by walking within 3.5 m of it, and
    only then did it start telling you where it was. The beacon switched on
    after you no longer needed it.

    `discovered` still does real work -- it drives carry capacity and basket
    capacity -- so it stays. It just isn't a gate on hearing any more.
    Discovery is a milestone now, not a prerequisite.
    """
    best = None
    best_d = float('inf')
    for b in baskets:
        d = math.hypot(b['x'] - player['x'], b['y'] - player['y'])
        if d > BASKET_AUDIBLE:
            continue
        if d < best_d:
            best = b
            best_d = d
    return best


# ============================================================================
# Status announcements
# ============================================================================

def announce_status():
    """Speak heading, nearest item, capacities, counts. Bound to P."""
    heading_deg = math.degrees(player['yaw']) % 360
    parts = [f'heading {heading_deg:.0f} degrees']

    n_egg = nearest_audible_egg()
    if n_egg:
        d = math.hypot(n_egg['x'] - player['x'], n_egg['y'] - player['y'])
        parts.append(f'nearest egg {d:.0f} meters')

    n_basket = nearest_audible_basket()
    if n_basket:
        d = math.hypot(n_basket['x'] - player['x'], n_basket['y'] - player['y'])
        parts.append(f'nearest basket {d:.0f} meters')

    parts.append(f'{len(held)} of {player_carry_cap()} held')
    parts.append(f'{discovered_count()} baskets found')
    if birds:
        parts.append(f'{len(birds)} birds in the park')

    say('. '.join(parts) + '.')


# ============================================================================
# Boot
# ============================================================================

update_listener()  # so positional audio is correct before the first tick.

# Boot chime + start the ambience bed if it's enabled in settings.
fire_boot()
_sync_ambience()

# No park yet — the menu is the first thing you meet. `start_game()` spawns
# one when it's asked for, so nothing ticks and no egg is on a timer while
# someone is still deciding what they want to do.
window.activate()
pyglet.clock.schedule_interval(update, 1 / 60)
_next_egg_call_at = now() + 0.5
_next_origin_chime_at = now() + 2.0  # let boot chime + speech land first

open_main_menu(announce='Egg Park.')

pyglet.app.run()
