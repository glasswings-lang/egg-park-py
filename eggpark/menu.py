# SPDX-License-Identifier: CC0-1.0
"""The main menu, and starting, resuming and restarting a park."""
import os

from eggpark import chestlist, game, prefs, saving, sounds, soundtest, speech, state, world

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
        items.append(('Start a new park', saving.confirm_new_park))
    elif os.path.isfile(saving.PARK_SAVE_FILE):
        items.append(('Continue your park', saving.continue_saved_park))
        items.append(('Start a new park', saving.confirm_new_park))
    else:
        items.append(('Walk in the park', start_game))
    items.append(('Settings', prefs.open_settings))
    items.append(('Sound test', soundtest.open_sound_test))
    items.append(('Controls', game.speak_controls))
    items.append(('Quit', saving.quit_game))
    return items


def open_main_menu(announce='Main menu.'):
    global _in_main_menu, _main_menu_focus
    if _game_started:
        saving.save_park('menu opened')
    chestlist.forget()
    _in_main_menu = True
    _main_menu_focus = 0
    saving._new_park_armed = False
    sounds.fire_menu_open()
    speech.say(f'{announce} Up and down to choose, Enter to pick.')
    _speak_focused_menu_item()


def _speak_focused_menu_item():
    items = main_menu_items()
    label, _action = items[_main_menu_focus % len(items)]
    speech.say(f'{label}.')


def main_menu_focus_move(direction):
    global _main_menu_focus
    saving._new_park_armed = False   # moving away cancels a half-confirmed new park
    _main_menu_focus = (_main_menu_focus + direction) % len(main_menu_items())
    _speak_focused_menu_item()


def main_menu_activate():
    items = main_menu_items()
    _label, action = items[_main_menu_focus % len(items)]
    action()


def _speak_world_intro():
    speech.say('W A S D move. Q E turn. Space scans. F deposits, and holding F '
        'pours eggs in one at a time. G lists your chests and Shift G your '
        'baskets. Shift H leads you home. P reports status. H says every '
        'control, and on a controller, tap Y. Escape returns to the menu. '
        'Find eggs, deposit at baskets, hatch birds.')


def start_game():
    """First park of the session."""
    global _in_main_menu, _game_started
    _in_main_menu = False
    _game_started = True
    sounds.fire_menu_close()
    world.reset_world()
    world.initial_spawn()
    world.log_counts('park started')
    saving.save_park('new park')
    sounds.update_listener()  # positional audio correct before the first tick
    speech.say('The park is yours.')
    _speak_world_intro()


def resume_game():
    global _in_main_menu
    _in_main_menu = False
    sounds.fire_menu_close()
    speech.say('Back in the park.')


def restart_game():
    """Throw away this park and spawn a fresh one.

    Speaks what it's about to destroy before doing it. There's no undo, and
    a menu item that quietly deletes an hour of collecting would be a cruel
    thing to sit one arrow key away from 'Back to the park'.
    """
    global _in_main_menu
    lost = len(state.birds)
    _in_main_menu = False
    sounds.fire_menu_close()
    world.reset_world()
    world.initial_spawn()
    saving.save_park('new park')
    sounds.update_listener()
    if lost:
        speech.say(f'New park. The previous {lost} '
            f'bird{"s" if lost != 1 else ""} stayed behind.')
    else:
        speech.say('New park.')
    _speak_world_intro()
