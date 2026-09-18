# SPDX-License-Identifier: CC0-1.0
"""Settings: their defaults, loading and saving them, and the settings screen."""
import json
import math
import os

from eggpark import config, menu, sounds, speech

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

SETTINGS_FILE = os.path.join(config._script_dir, 'settings.json')

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
    ('vol_scan_guide',       'Volume: scan guide',        1.0),
    ('vol_bird_call',        'Volume: bird calls',        1.0),
    ('vol_egg_collect',      'Volume: egg collect',       1.0),
    ('vol_refuse',           'Volume: refuse',            1.0),
    ('vol_basket_discover',  'Volume: basket discover',   1.0),
    ('vol_basket_deposit',   'Volume: basket deposit',    1.0),
    ('vol_basket_full',      'Volume: basket full',       1.0),
    ('vol_hatch_in_basket',  'Volume: hatch in basket',   1.0),
    ('vol_egg_laid',         'Volume: egg laid',          1.0),
    ('vol_chest_chime',      'Volume: chest chimes',      1.0),
    ('vol_chest_discover',   'Volume: chest found',       1.0),
    ('vol_scan_chest_ping',  'Volume: scan chest pings',  1.0),
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
     'default': config.WALK_SPEED, 'min': 0.5, 'max': 5.0, 'step': 0.5,
     'format': lambda v: f'{v:.1f} meters per second'},
    {'key': 'run_speed', 'label': 'Run speed, holding Shift', 'kind': 'range',
     'default': config.RUN_SPEED, 'min': 1.0, 'max': 12.0, 'step': 0.5,
     'format': lambda v: f'{v:.1f} meters per second'},
    {'key': 'turn_speed', 'label': 'Turn speed', 'kind': 'range',
     'default': config.TURN_SPEED, 'min': math.pi / 8, 'max': math.pi, 'step': math.pi / 8,
     'format': lambda v: f'{int(round(math.degrees(v)))} degrees per second'},
    # How far away a thing can be and still sound close. Low values make the
    # world drop away fast and quiet; high values keep distant eggs and
    # baskets audible at the cost of the distance cue itself. On a slider
    # because the only way to judge it is to listen, and the person listening
    # is not the person who wrote the number.
    {'key': 'audio_distance', 'label': 'Hearing distance', 'kind': 'range',
     'default': config.SOURCE_MIN_DISTANCE, 'min': 1.0, 'max': 60.0, 'step': 5.0,
     'format': lambda v: f'{v:.0f} meters at full volume'},
    # How far the rest of the park drops while a scan is answering or a guide
    # is leading you. A busy park covers the scan completely, and no volume
    # setting can fix that on its own: turning the scan up turns the park up
    # with it. 100% is no ducking at all, which is how it used to be.
    # On a slider because the right amount depends on your headphones, your
    # park and your ears, none of which the number knows about.
    {'key': 'duck_level', 'label': 'Park quietens during a scan', 'kind': 'range',
     'default': 0.35, 'min': 0.1, 'max': 1.0, 'step': 0.05,
     'format': lambda v: ('no quietening' if v >= 0.999
                          else f'down to {v * 100:.0f} percent')},
    # How long you have to carry an egg before it hatches. On a slider for
    # the same reason as hearing distance: 30 seconds is a number, and
    # whether it feels like a pleasant push or a hostile stopwatch is not
    # something the number can tell you.
    {'key': 'hatch_time', 'label': 'Time before an egg hatches', 'kind': 'range',
     'default': config.HATCH_TIMER_INITIAL, 'min': 5.0, 'max': 180.0, 'step': 5.0,
     'format': lambda v: f'{v:.0f} seconds'},
    {'key': 'lay_time', 'label': 'Time before a bird lays', 'kind': 'range',
     'default': config.LAY_TIME_DEFAULT, 'min': 5.0, 'max': 900.0, 'step': 5.0,
     'format': lambda v: f'{v:.0f} seconds'},
    # Recordings vs synth. Normally a recorded sample wins wherever one
    # exists, which is what you want while playing — but not while WORKING on
    # the sounds. Turning this off forces every cue back to its placeholder,
    # so a take can be compared against what it's replacing without moving
    # files around on disk.
    # How fine the turning is near the middle of the stick. 1 is straight
    # through: a quarter push turns a quarter as fast. Higher keeps small
    # pushes small, which is what makes a gentle correction possible instead
    # of a swing — and how fine is fine enough is an ears-and-hands question.
    {'key': 'pad_turn_curve', 'label': 'Controller turning, fineness', 'kind': 'range',
     'default': config.PAD_TURN_CURVE, 'min': 1.0, 'max': 3.0, 'step': 0.25,
     'format': lambda v: ('straight through' if v <= 1.0 else f'{v:.2f}, finer near the middle')},
    # A worn stick does not read zero at rest, and the park drifting while
    # you hold nothing reads as the world wandering off by itself. Raise this
    # until it stops.
    {'key': 'pad_deadzone', 'label': 'Controller stick slack', 'kind': 'range',
     'default': config.PAD_DEADZONE, 'min': 0.0, 'max': 0.4, 'step': 0.05,
     'format': lambda v: ('none' if v <= 0.0 else f'{v * 100:.0f} percent ignored')},
    {'key': 'prefer_samples', 'label': 'Use recordings when available',
     'kind': 'bool', 'default': True},
    # A pad with a worn stick drifts, which in an audio game reads as the
    # world wandering off by itself. Switching it off here is quicker than
    # unplugging.
    {'key': 'enable_controller',      'label': 'Controller',      'kind': 'bool', 'default': True},
    {'key': 'enable_pickup',          'label': 'Egg pickup',      'kind': 'bool', 'default': True},
    {'key': 'enable_hand_hatching',   'label': 'Hand hatching',   'kind': 'bool', 'default': True},
    {'key': 'enable_basket_hatching', 'label': 'Basket hatching', 'kind': 'bool', 'default': True},
    {'key': 'enable_ground_hatching', 'label': 'Ground hatching', 'kind': 'bool', 'default': False},
    {'key': 'enable_bird_laying',     'label': 'Birds lay eggs',  'kind': 'bool', 'default': True},
    {'key': 'enable_egg_calls',       'label': 'Egg calls',       'kind': 'bool', 'default': True},
    {'key': 'enable_basket_chimes',   'label': 'Basket chimes',   'kind': 'bool', 'default': True},
    {'key': 'enable_chest_chimes',    'label': 'Chest chimes',    'kind': 'bool', 'default': True},
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
    speech.say(f'{item["label"]}: {_value_speech(item, new)}.')
    save_settings()
    sounds._sync_ambience()


# --- Settings screen state + handlers ---------------------------------------

_in_settings = False
_settings_focus = 0


def _speak_focused_setting():
    item = SETTINGS_MENU[_settings_focus]
    speech.say(f'{item["label"]}: {_value_speech(item, settings[item["key"]])}.')


def open_settings():
    global _in_settings, _settings_focus
    # Remember where we came from, so closing goes BACK there rather than
    # always dumping you into the world. Opening settings from the main menu
    # and being spat into a park you never asked to start would be a worse
    # bug than the one the main menu exists to fix.
    menu._settings_from_menu = menu._in_main_menu
    menu._in_main_menu = False
    _in_settings = True
    _settings_focus = 0
    sounds.fire_menu_open()
    speech.say('Settings opened. Up and down to choose, left and right to change. '
        'Space toggles. Escape closes.')
    _speak_focused_setting()


def close_settings():
    global _in_settings
    _in_settings = False
    save_settings()
    sounds.fire_menu_close()
    if menu._settings_from_menu:
        menu.open_main_menu(announce='Settings closed.')
    else:
        speech.say('Settings closed.')


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
        speech.say(f'{item["label"]}: {"on" if new else "off"}.')
        save_settings()
        sounds._sync_ambience()


def settings_toggle():
    """Space/Enter inside settings — flip booleans, no-op on ranges."""
    item = SETTINGS_MENU[_settings_focus]
    if item['kind'] == 'bool':
        settings[item['key']] = not settings[item['key']]
        speech.say(f'{item["label"]}: {"on" if settings[item["key"]] else "off"}.')
        save_settings()
        sounds._sync_ambience()
