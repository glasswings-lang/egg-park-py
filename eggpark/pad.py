# SPDX-License-Identifier: CC0-1.0
"""The game on a controller: analog sticks, buttons, and hot-plugging.

WHY THIS EXISTS. The keyboard hurts to play on for long, and turning by
holding a key is all-or-nothing: you get the full turn speed or none of it,
so every correction overshoots and you swing about. A stick is analog. Push
it a little and you turn a little. That is not a convenience, it is the
difference between aiming and flailing.

WHAT IS WHERE.
  Left stick    walk. Any direction, and how far you push is how fast you go.
  Right stick   turn, left and right. A nudge is a nudge.
  Right trigger hold to run, like Shift.
  A             scan (Space)
  B             deposit (F)
  X             say where you are and what you have (P)
  Y             read out the controls (H)
  D-pad up      lead me to a basket I have found, with room (B)
  D-pad down    lead me to a basket I have not found (V)
  D-pad right   lead me to a chest I have found, with room (C)
  D-pad left    lead me to a chest I have not found (Shift+C)
  Bumpers       volume down and up ([ and ])
  Start         the main menu (Escape)
  Back          settings (O)

IN MENUS the same buttons do the obvious thing rather than nothing, or you
would have to put the pad down to start the game: D-pad or left stick moves
the focus, A picks, B goes back, and the left/right of a stick changes a
setting. Anything a menu doesn't claim is ignored while it is open.

HOW IT READS. Buttons arrive as events, which is what you want for "do this
now". Sticks and triggers are read every frame instead, in game.update,
because a stick is a position rather than an event — the event only tells you
it moved, and holding still is not an event.

DEADZONE. A stick at rest does not read zero, so anything inside
PAD_DEADZONE is treated as centre, and the useful range is stretched back
over the rest. Without that the park drifts while you are not touching
anything, which in an audio game reads as the world wandering off on its own.
"""
import math

import pyglet

from eggpark import config

# The open controller, or None. One at a time: a second pad joining should
# not take the game away from whoever is already holding one.
_controller = None
_manager = None


def _speak(text):
    # Imported late, and every time: eggpark.speech is ready long before a
    # controller event can arrive, but this module is imported early.
    from eggpark import speech
    speech.say(text)


# ---------------------------------------------------------------- opening

def open_pad():
    """Find a controller, open it, and keep watching for one to be plugged in.

    Never raises. A machine with no controller, or a pyglet build without the
    controller backend, must still start the game — this is an extra way to
    play, not a requirement for playing.
    """
    global _manager
    try:
        _manager = pyglet.input.ControllerManager()
        _manager.push_handlers(on_connect=_on_connect, on_disconnect=_on_disconnect)
        for controller in _manager.get_controllers():
            if _use(controller):
                break
    except Exception as exc:
        from eggpark import speech
        speech.log_event(f'controller support unavailable: {exc}')


def _use(controller):
    global _controller
    if _controller is not None:
        return False
    try:
        controller.open()
    except Exception as exc:
        from eggpark import speech
        speech.log_event(f'could not open controller {controller.name!r}: {exc}')
        return False
    controller.push_handlers(on_button_press=_on_button, on_dpad_motion=_on_dpad)
    _controller = controller
    from eggpark import speech
    speech.log_event(f'controller in use: {controller.name}')
    return True


def _on_connect(controller):
    if _use(controller):
        _speak('Controller connected. Press Y on it to hear the controls.')


def _on_disconnect(controller):
    global _controller
    if controller is _controller:
        _controller = None
        _speak('Controller disconnected.')
        # Another pad may still be plugged in; take it rather than going quiet.
        try:
            for other in _manager.get_controllers():
                if other is not controller and _use(other):
                    return
        except Exception:
            pass


def connected():
    return _controller is not None


# ---------------------------------------------------------------- reading

def deadzone():
    from eggpark import prefs
    return prefs.settings.get('pad_deadzone', config.PAD_DEADZONE)


def turn_curve():
    from eggpark import prefs
    return prefs.settings.get('pad_turn_curve', config.PAD_TURN_CURVE)


def _curved(value, curve):
    """Deadzone, then bend the response so small pushes stay small.

    The deadzone is removed and the rest stretched back to a full 0..1, so
    the stick still reaches its maximum — a deadzone that just clips would
    make the game slower to play than the keyboard.
    """
    dead = deadzone()
    size = abs(value)
    if size <= dead:
        return 0.0
    scaled = (size - dead) / max(1e-6, 1.0 - dead)
    return math.copysign(min(1.0, scaled) ** curve, value)


def read():
    """(forward, right, turn, running) from the pad, all zero with no pad.

    forward/right/turn are -1..1 and ANALOG: they carry how far the stick is
    pushed, which is the whole point of this file.
    """
    from eggpark import prefs
    if _controller is None or not prefs.settings.get('enable_controller', True):
        return 0.0, 0.0, 0.0, False
    try:
        move_curve = config.PAD_MOVE_CURVE
        forward = _curved(_controller.lefty, move_curve)
        right = _curved(_controller.leftx, move_curve)
        # Right stick right should turn RIGHT, and the game's yaw grows to
        # the left, so this is negated. Getting this backwards is the kind of
        # mistake that is obvious in play and invisible in code.
        turn = -_curved(_controller.rightx, turn_curve())
        running = _controller.righttrigger > config.PAD_TRIGGER_THRESHOLD
    except Exception:
        return 0.0, 0.0, 0.0, False
    return forward, right, turn, running


def menu_axis():
    """(vertical, horizontal) as -1, 0 or 1, for moving through a menu.

    A stick held over is one step, not sixty a second: menus are stepped
    through by the D-pad and by flicks, and _menu_latched is what stops a
    held stick from running the whole list past you.
    """
    if _controller is None:
        return 0, 0
    try:
        up_down = _curved(_controller.lefty, 1.0)
        left_right = _curved(_controller.leftx, 1.0)
    except Exception:
        return 0, 0
    vertical = 1 if up_down > 0.6 else (-1 if up_down < -0.6 else 0)
    horizontal = 1 if left_right > 0.6 else (-1 if left_right < -0.6 else 0)
    return vertical, horizontal


_menu_latched = (0, 0)


def tick_menus():
    """Let the left stick move through whichever menu is open. Called every
    frame from game.update, which keeps running while a menu is up."""
    global _menu_latched
    if _controller is None:
        return
    from eggpark import menu, prefs, soundtest
    vertical, horizontal = menu_axis()
    if (vertical, horizontal) == _menu_latched:
        return                      # still held from last frame: one step only
    _menu_latched = (vertical, horizontal)
    if vertical == 0 and horizontal == 0:
        return
    if soundtest._in_sound_test:
        if vertical:
            soundtest.sound_test_focus_move(-vertical)
        elif horizontal > 0:
            soundtest.sound_test_explain()
    elif menu._in_main_menu:
        if vertical:
            menu.main_menu_focus_move(-vertical)
    elif prefs._in_settings:
        if vertical:
            prefs.settings_focus_move(-vertical)
        elif horizontal:
            prefs.settings_change(horizontal)


# ---------------------------------------------------------------- buttons

def _on_dpad(controller, left, right, up, down):
    """The D-pad. pyglet sends one event per change with every direction's
    state, so a release arrives as all four false and does nothing here."""
    from eggpark import chests, menu, prefs, scan, soundtest
    if menu._in_main_menu or prefs._in_settings or soundtest._in_sound_test:
        if up or down:
            step = -1 if up else 1
            if soundtest._in_sound_test:
                soundtest.sound_test_focus_move(step)
            elif menu._in_main_menu:
                menu.main_menu_focus_move(step)
            else:
                prefs.settings_focus_move(step)
        elif (left or right) and prefs._in_settings:
            prefs.settings_change(1 if right else -1)
        return
    if up:
        scan.try_scan_found_baskets()
    elif down:
        scan.try_scan_unfound_baskets()
    elif right:
        chests.try_scan_found_chests()
    elif left:
        chests.try_scan_unfound_chests()


def _on_button(controller, name):
    from eggpark import chests, game, menu, prefs, scan, soundtest, sounds, world

    # Menus first, exactly as the keyboard handler does: settings can be
    # opened from the menu and the world must not see any of it.
    if soundtest._in_sound_test:
        if name == 'a':
            soundtest.sound_test_play()
        elif name == 'b':
            soundtest.close_sound_test()
        elif name == 'x':
            soundtest.sound_test_explain()
        elif name == 'y':
            sounds.reload_sample_bank()
        return
    if menu._in_main_menu:
        if name == 'a':
            menu.main_menu_activate()
        elif name == 'b' and menu._game_started:
            menu.resume_game()
        return
    if prefs._in_settings:
        if name == 'a':
            prefs.settings_toggle()
        elif name in ('b', 'back', 'start'):
            prefs.close_settings()
        return

    if name == 'a':
        scan.try_scan()
    elif name == 'b':
        world.try_deposit()
    elif name == 'x':
        game.announce_status()
    elif name == 'y':
        speak_pad_controls()
    elif name == 'start':
        menu.open_main_menu()
    elif name == 'back':
        prefs.open_settings()
    elif name == 'leftshoulder':
        prefs.nudge_setting('master_volume', -1)
    elif name == 'rightshoulder':
        prefs.nudge_setting('master_volume', +1)


# ---------------------------------------------------------------- the help

PAD_HELP = (
    'Controller. Left stick walks, and how far you push it is how fast you '
    'go. Right stick turns, left and right. Hold the right trigger to run. '
    'A scans. B deposits. X says your status. Y reads this out. '
    'On the D-pad: up leads you to a basket you have found with room, '
    'down to a basket you have not found, right to a chest you have found, '
    'left to a chest you have not found. '
    'The bumpers lower and raise the volume. '
    'Start opens the menu, and Back opens settings. '
    'In a menu, the stick or D-pad moves, A picks, and B goes back.'
)


def speak_pad_controls():
    _speak(PAD_HELP)
