# SPDX-License-Identifier: CC0-1.0
"""The sound test screen: hear every cue and what it means."""
import os

from eggpark import menu, prefs, sounds, speech

# `ambience` is deliberately absent: it is a continuous bed rather than a
# cue, it runs for half a minute, and it has its own toggle. Previewing it
# would mean sitting through it.

_in_sound_test = False
_sound_test_focus = 0


def open_sound_test():
    global _in_sound_test, _sound_test_focus
    menu._in_main_menu = False
    _in_sound_test = True
    _sound_test_focus = 0
    sounds.fire_menu_open()
    speech.say('Sound test. Up and down to choose, Enter to hear it, Right to say '
        'what it means. S switches between recordings and the built-in '
        'sounds. F opens the file where you point at your own recordings. '
        'R loads them. P reads any problems. Escape goes back.')
    _speak_sound_test_item()


def close_sound_test():
    global _in_sound_test
    _in_sound_test = False
    sounds.fire_menu_close()
    menu.open_main_menu(announce='Sound test closed.')


def _sound_test_entry():
    return sounds.SOUND_CATALOGUE[_sound_test_focus % len(sounds.SOUND_CATALOGUE)]


def _speak_sound_test_item():
    """Name the cue and say whether it's a recording or the placeholder.

    Which one you're about to hear matters more than anything else on this
    screen — the whole point is comparing them — so it's said every time
    rather than tucked behind another keypress.
    """
    category, label, _meaning, _getter = _sound_test_entry()
    if sounds.has_recording(category):
        state = ('recorded' if prefs.settings.get('prefer_samples', True)
                 else 'recorded, but using the built-in')
    else:
        state = 'built-in'
    # A broken line in sounds.txt is announced HERE, on the cue it was meant
    # to supply. That's where you'd go looking when a recording doesn't play,
    # and it saves reading an error list to find out which one failed.
    problem = sounds.sound_list_problem_for(category)
    speech.say(f'{label}. {state}. {problem}' if problem else f'{label}. {state}.')


def sound_test_focus_move(direction):
    global _sound_test_focus
    _sound_test_focus = (_sound_test_focus + direction) % len(sounds.SOUND_CATALOGUE)
    _speak_sound_test_item()


def sound_test_play():
    """Play the focused cue, at the listener.

    Everything is non-positional here even though several of these are
    normally spatial. You're identifying a sound, not locating it, and a
    preview that arrived from somewhere off to your left would be harder to
    compare against the next one.
    """
    category, _label, _meaning, getter = _sound_test_entry()
    if category == 'egg-warning':
        sounds.fire_egg_warning()      # both tones, exactly as the game fires it
        return
    sounds._play(sounds.pick_source(category, fallback=getter()), volume=0.5,
          category=category)


def sound_test_explain():
    _category, label, meaning, _getter = _sound_test_entry()
    speech.say(f'{label}. {meaning}')


def open_sounds_file():
    """Open sounds.txt in whatever the system uses for .txt files.

    The whole point of that file is being editable without touching code, so
    getting to it shouldn't mean navigating to a folder either. Created first
    if it isn't there yet, so this key always leads somewhere.
    """
    sounds.write_sounds_template()
    try:
        os.startfile(sounds.SOUNDS_LIST_FILE)  # noqa: S606 - Windows shell open
        speech.say('Opened sounds dot text. Save it, then press R here to load it.')
    except Exception as exc:
        speech.say(f'Could not open the file. It is at {sounds.SOUNDS_LIST_FILE}. {exc}')


def sound_test_toggle_source():
    prefs.settings['prefer_samples'] = not prefs.settings.get('prefer_samples', True)
    prefs.save_settings()
    speech.say('Using recordings.' if prefs.settings['prefer_samples']
        else 'Using the built-in sounds.')
    _speak_sound_test_item()
