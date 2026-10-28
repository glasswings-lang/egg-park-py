# SPDX-License-Identifier: CC0-1.0
"""The game on a controller: analog sticks, buttons, and hot-plugging.

WHY THIS EXISTS. The keyboard hurts to play on for long, and turning by
holding a key is all-or-nothing: you get the full turn speed or none of it,
so every correction overshoots and you swing about. A stick is analog. Push
it a little and you turn a little. That is not a convenience, it is the
difference between aiming and flailing.

WHAT IS WHERE. The shape of this follows Periphery Synthetic, which is the
audio game that has thought hardest about a pad: left stick to move, right
stick to turn, A to scan and to confirm, B for the thing in front of you and
for "back", Start for the menu, and — the good idea worth borrowing — HOLD Y
to turn the D-pad into questions rather than actions.
  Left stick    walk. Any direction, and how far you push is how fast you go.
  Click it      run, as a toggle. Stays on until you click again.
  Right stick   turn, left and right. A nudge is a nudge.
  Click it      lead me home, to where the park began (Shift+H)
  Right trigger hold to run, for as long as you hold it. The same as Shift.
  A             scan (Space)
  B             deposit everything (F); hold it to pour eggs in one at a time
  X             your full status (P)
  Y (tap)       read out the controls (H)
  D-pad up      lead me to a basket I have found, with room (B)
  D-pad down    lead me to a basket I have not found (V)
  D-pad right   lead me to a chest I have found, with room (C)
  D-pad left    lead me to a chest I have not found (Shift+C)
  Left trigger  the chest list: every chest found, and what its birds get (G).
                While it's open, D-pad up and down choose, left and right
                switch to the basket list and back (Shift+G), A picks, B closes;
                the sticks still walk and turn. See eggpark/chestlist.py.
  HOLD Y, then
    D-pad up    which way am I facing
    D-pad down  what am I carrying
    D-pad left  what is in this park
    D-pad right my full status
  Bumpers       volume down and up ([ and ])
  Start         the main menu (Escape)
  Back          settings (O)

WHY RUN IS ON THE STICK CLICK. It was only on the right trigger, and holding
a trigger down while pushing a stick is the exact grip that hurts — the pad
exists here because the keyboard hurt. Periphery puts its turbo on the stick
click, so that is where run goes, and as a toggle rather than a hold: press
once, run until you press again. The trigger still works for anyone who
wants it.

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
    controller.push_handlers(on_button_press=_on_button, on_button_release=_on_release,
                             on_dpad_motion=_on_dpad)
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


# Run, as a toggle: clicking the left stick turns it on and leaves it on.
# Nothing to hold down.
_running_latched = False

# Whether Y is being held. Held Y turns the D-pad into questions — see the
# module docstring. Tapping Y (pressed and released without the D-pad) reads
# the controls out, so the modifier is still discoverable by pressing it.
_y_held = False
_y_used_as_modifier = False


def running_latched():
    return _running_latched


def forget_run():
    """Stop running. For a new park, so a toggle cannot survive one."""
    global _running_latched
    _running_latched = False


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
        running = (_running_latched
                   or _controller.righttrigger > config.PAD_TRIGGER_THRESHOLD)
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

# The left trigger opens and closes the chest list. It's an axis, not a
# button, so it's read every frame and acts once per pull: _left_pulled stops
# a held trigger from opening and closing the list sixty times a second.
_left_pulled = False


def tick_left_trigger():
    global _left_pulled
    from eggpark import chestlist, prefs
    if _controller is None or not prefs.settings.get('enable_controller', True):
        return
    try:
        pulled = _controller.lefttrigger > config.PAD_TRIGGER_THRESHOLD
    except Exception:
        return
    if pulled and not _left_pulled:
        chestlist.toggle()
    _left_pulled = pulled


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

def _on_dpad(controller, vector):
    """The D-pad.

    pyglet sends ONE 2D vector, not four booleans: x is -1 left, 0, or 1
    right, and y is -1 down, 0, or 1 up. Letting go arrives as (0, 0), which
    falls through here and does nothing, which is what you want.

    This signature is pyglet's, and it is written down in
    pyglet.input.base.Controller.on_dpad_motion. Guessing it from memory
    instead cost a crash on load the first time a pad was plugged in — the
    pad reports its resting state as soon as the game opens, so the wrong
    signature was not a bug you could fail to hit. tests/test_pad.py now
    compares these handlers against pyglet's own declarations.
    """
    from eggpark import chests, menu, prefs, scan, soundtest
    left = vector.x < -0.5
    right = vector.x > 0.5
    up = vector.y > 0.5
    down = vector.y < -0.5
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
    from eggpark import chestlist
    if chestlist.is_open():
        if up:
            chestlist.move(-1)
        elif down:
            chestlist.move(+1)
        elif left or right:
            chestlist.switch()    # chests <-> baskets
        return
    if _y_held:
        # Held Y turns the D-pad into questions. Borrowed from Periphery
        # Synthetic, where holding Y and pressing a direction announces your
        # coordinates or heading: asking the game something and telling it to
        # do something are different, and they should not share a button.
        global _y_used_as_modifier
        from eggpark import game
        if up:
            game.announce_heading()
        elif down:
            game.announce_carrying()
        elif left:
            game.announce_park()
        elif right:
            game.announce_status()
        else:
            return
        _y_used_as_modifier = True
        return
    if up:
        scan.try_scan_found_baskets()
    elif down:
        scan.try_scan_unfound_baskets()
    elif right:
        chests.try_scan_found_chests()
    elif left:
        chests.try_scan_unfound_chests()


def _on_release(controller, name):
    """Y is the only button that does anything on release: tapping it reads
    the controls out, but only if it was not being held as the modifier."""
    global _y_held, _y_used_as_modifier
    if name == 'b':
        # A tap of B deposits everything, a hold has been pouring.
        from eggpark import menu, prefs, soundtest, world
        if menu._in_main_menu or prefs._in_settings or soundtest._in_sound_test:
            world.cancel_pour()
        else:
            world.release_deposit()
        return
    if name != 'y':
        return
    _y_held = False
    if not _y_used_as_modifier:
        from eggpark import menu, prefs, soundtest
        if not (menu._in_main_menu or prefs._in_settings or soundtest._in_sound_test):
            speak_pad_controls()
    _y_used_as_modifier = False


def _on_button(controller, name):
    global _y_held, _running_latched
    from eggpark import chests, game, menu, prefs, scan, soundtest, sounds, world

    if name == 'y' and not (menu._in_main_menu or prefs._in_settings
                            or soundtest._in_sound_test):
        # Held, not pressed: the D-pad decides what it meant, and the release
        # reads the controls out if nothing else used it.
        _y_held = True
        return
    if name == 'leftstick' and not (menu._in_main_menu or prefs._in_settings
                                    or soundtest._in_sound_test):
        # Run, as a toggle. Announced, because a mode you cannot see is a
        # mode you have to remember you are in.
        _running_latched = not _running_latched
        _speak('Running.' if _running_latched else 'Walking.')
        return

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

    from eggpark import chestlist
    if chestlist.is_open() and name in ('a', 'b'):
        if name == 'a':
            chestlist.pick()
        else:
            chestlist.close_list()
        return

    if name == 'a':
        scan.try_scan()
    elif name == 'b':
        world.press_deposit()     # tap or hold: decided on release
    elif name == 'x':
        game.announce_status()
    elif name == 'rightstick':
        scan.try_guide_home()
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
    'go. Click the left stick to run, and click it again to stop; holding '
    'the right trigger runs too. Right stick turns, left and right. '
    'A scans. B deposits everything; hold B to pour eggs in one at a time, '
    'and let go to stop. X says your status. Y on its own reads this out. '
    'On the D-pad: up leads you to a basket you have found with room, '
    'down to a basket you have not found, right to a chest you have found, '
    'left to a chest you have not found. '
    'The left trigger lists every chest you have found and what its birds get: '
    'D-pad up and down choose, left and right switch between chests and baskets, '
    'A leads you there, B or the trigger again closes it. '
    'Hold Y and press the D-pad to ask instead: up for your heading, '
    'down for what you are carrying, left for what is in the park, '
    'right for everything. '
    'Click the right stick to be led home, to where the park began. '
    'The bumpers lower and raise the volume. '
    'Start opens the menu, and Back opens settings. '
    'In a menu, the stick or D-pad moves, A picks, and B goes back.'
)


def speak_pad_controls():
    _speak(PAD_HELP)
