# SPDX-License-Identifier: CC0-1.0
"""The window, keys, the per-frame update, and spoken status."""
import math
import time

import pyglet
from pyglet.window import key

from eggpark import config, flock, menu, prefs, saving, scan, sounds, soundtest, speech, state, world

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
             'A step left. D step right. Hold Shift to run.'),
    ('Turn', 'Q or left arrow turns left. E or right arrow turns right.'),
    ('Do', 'Space scans for eggs and leads you to the nearest. '
           'B leads you to the nearest found basket with room. '
           'V leads you to the nearest basket you have not found yet. '
           'F deposits at a basket. P speaks your status.'),
    ('Set up', 'O opens settings. Left and right square brackets '
               'lower and raise the volume. R reloads the sample bank.'),
    ('Leave', 'Escape goes back to the main menu, where Quit lives. '
              'H repeats these controls.'),
)


def speak_controls():
    speech.say('Controls. ' + ' '.join(body for _label, body in CONTROL_HELP))


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
    # Sound test consumes its own keys.
    if soundtest._in_sound_test:
        if symbol == key.ESCAPE:
            soundtest.close_sound_test()
        elif symbol == key.UP:
            soundtest.sound_test_focus_move(-1)
        elif symbol == key.DOWN:
            soundtest.sound_test_focus_move(+1)
        elif symbol == key.RETURN or symbol == key.SPACE:
            soundtest.sound_test_play()
        elif symbol == key.RIGHT:
            soundtest.sound_test_explain()
        elif symbol == key.S:
            soundtest.sound_test_toggle_source()
        elif symbol == key.R:
            sounds.reload_sample_bank()
        elif symbol == key.P:
            sounds.speak_sound_list_problems()
        elif symbol == key.F:
            soundtest.open_sounds_file()
        else:
            return None
        return pyglet.event.EVENT_HANDLED

    # Main menu consumes its own keys. Checked FIRST: settings can be opened
    # from here, and the world must not see any of it.
    if menu._in_main_menu:
        if symbol == key.UP:
            menu.main_menu_focus_move(-1)
        elif symbol == key.DOWN:
            menu.main_menu_focus_move(+1)
        elif symbol == key.RETURN or symbol == key.SPACE:
            menu.main_menu_activate()
        elif symbol == key.ESCAPE:
            # Escape closes the menu if there's a park to go back to, and
            # otherwise does nothing. It deliberately does NOT quit: this is
            # the first screen of the game, and quitting on the key people
            # press to mean "never mind" is a bad trade.
            if menu._game_started:
                menu.resume_game()
            else:
                speech.say('Choose an option, or pick Quit to leave.')
        else:
            return None  # not ours; let it fall through
        return pyglet.event.EVENT_HANDLED

    # Settings screen consumes its own keys; nothing falls through to game.
    if prefs._in_settings:
        if symbol == key.ESCAPE or symbol == key.O:
            prefs.close_settings()
        elif symbol == key.UP:
            prefs.settings_focus_move(-1)
        elif symbol == key.DOWN:
            prefs.settings_focus_move(+1)
        elif symbol == key.LEFT:
            prefs.settings_change(-1)
        elif symbol == key.RIGHT:
            prefs.settings_change(+1)
        elif symbol == key.SPACE or symbol == key.RETURN:
            prefs.settings_toggle()
        else:
            return None  # not ours; let it fall through
        return pyglet.event.EVENT_HANDLED

    if symbol == key.ESCAPE:
        # Back to the menu, not out of the game. Quitting outright on Escape
        # is a hard thing to undo by accident with no visible confirmation.
        menu.open_main_menu()
    elif symbol == key.H or symbol == key.SLASH:
        speak_controls()
    elif symbol == key.P:
        announce_status()
    elif symbol == key.F:
        world.try_deposit()
    elif symbol == key.SPACE:
        scan.try_scan()
    elif symbol == key.B:
        scan.try_scan_found_baskets()
    elif symbol == key.V:
        scan.try_scan_unfound_baskets()
    elif symbol == key.R:
        sounds.reload_sample_bank()
    elif symbol == key.O:
        prefs.open_settings()
    elif symbol == key.BRACKETLEFT:
        prefs.nudge_setting('master_volume', -1)
    elif symbol == key.BRACKETRIGHT:
        prefs.nudge_setting('master_volume', +1)
    else:
        # Movement keys and anything else we don't act on: fall through, so
        # KeyStateHandler below us still sees them.
        return None
    return pyglet.event.EVENT_HANDLED


def on_activate():
    speech.say('Window focused.')


def on_deactivate():
    speech.say('Window lost focus. Alt-tab back to the Egg Park window.')


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
    if prefs._in_settings or menu._in_main_menu or soundtest._in_sound_test:
        return

    # Turn.
    turn_speed = prefs.settings['turn_speed']
    if keys[key.Q] or keys[key.LEFT]:
        state.player['yaw'] += turn_speed * dt
    if keys[key.E] or keys[key.RIGHT]:
        state.player['yaw'] -= turn_speed * dt

    # Move (forward + strafe).
    move_forward = (1 if keys[key.W] or keys[key.UP] else 0) - \
                   (1 if keys[key.S] or keys[key.DOWN] else 0)
    move_right = (1 if keys[key.D] else 0) - (1 if keys[key.A] else 0)

    if move_forward != 0 or move_right != 0:
        dx = math.cos(state.player['yaw']) * move_forward + math.sin(state.player['yaw']) * move_right
        dy = math.sin(state.player['yaw']) * move_forward - math.cos(state.player['yaw']) * move_right
        length = math.hypot(dx, dy)
        running = keys[key.LSHIFT] or keys[key.RSHIFT]
        walk_speed = prefs.settings['run_speed'] if running else prefs.settings['walk_speed']
        stride = config.RUN_STEP_DISTANCE if running else config.STEP_DISTANCE
        state.player['x'] += (dx / length) * walk_speed * dt
        state.player['y'] += (dy / length) * walk_speed * dt

        # Footstep cadence: accumulate walked distance, fire each time we
        # cross STEP_DISTANCE. Tying cadence to distance (not time) means
        # adjusting walk_speed naturally changes step rate. Toggle-off
        # still ticks the counter so re-enabling mid-walk doesn't burst.
        _dist_since_step += walk_speed * dt
        if _dist_since_step >= stride:
            _dist_since_step -= stride
            if prefs.settings['enable_footsteps']:
                sounds.fire_footstep()
    else:
        # Standing still — reset so we don't fire a half-step the moment
        # the player starts moving again. Each fresh walk gets a full
        # stride before the first footstep.
        _dist_since_step = 0.0

    sounds.update_listener()

    # Pickups + discovery happen passively while walking.
    world.try_collect_eggs()
    world.try_discover_basket()
    world.forget_distant_baskets()
    world.maybe_spawn_basket()

    # Hatching timers.
    flock.tick_hatching(dt)
    flock.tick_birds(dt)
    flock.tick_laying(dt)
    world.watch_counts()
    saving.tick_autosave()

    t = now()

    scan.tick_scan_guide(t)

    # Egg call — round-robin over all eggs in audible range. Each call
    # fires from the nearest egg; the nearest changes as you move so you
    # get the cocktail-party effect of multiple eggs in the world.
    # The interval still ticks when the toggle is off so re-enabling
    # doesn't trigger a burst.
    if t >= _next_egg_call_at:
        if prefs.settings['enable_egg_calls']:
            nearest = nearest_audible_egg()
            if nearest:
                sounds.fire_egg_call(nearest)
        _next_egg_call_at = t + config.EGG_CALL_INTERVAL

    # Origin chime — fixed-interval beacon at world (0, 0, 0). Fires
    # whether or not the player is in range; OpenAL's distance attenuation
    # at max_distance=500 handles audibility falloff naturally.
    if t >= _next_origin_chime_at:
        if prefs.settings['enable_origin_chime']:
            sounds.fire_origin_chime()
        _next_origin_chime_at = t + config.ORIGIN_CHIME_INTERVAL

    # Basket chime — proximity-scaled per the nearest discovered basket.
    # Same toggle-off-still-ticks pattern.
    if t >= _next_basket_chime_at:
        nearest_b = nearest_audible_basket()
        if nearest_b:
            if prefs.settings['enable_basket_chimes']:
                sounds.fire_basket_chime(nearest_b)
            d = math.hypot(nearest_b['x'] - state.player['x'], nearest_b['y'] - state.player['y'])
            proximity = max(0.0, 1.0 - d / config.BASKET_AUDIBLE)
            interval = (config.BASKET_CHIME_INTERVAL_FAR -
                        (config.BASKET_CHIME_INTERVAL_FAR - config.BASKET_CHIME_INTERVAL_NEAR) * proximity)
            _next_basket_chime_at = t + interval
        else:
            _next_basket_chime_at = t + config.BASKET_CHIME_INTERVAL_FAR


def nearest_audible_egg():
    best = None
    best_d = float('inf')
    for egg in state.eggs:
        d = math.hypot(egg['x'] - state.player['x'], egg['y'] - state.player['y'])
        if d > config.EGG_AUDIBLE:
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
    for b in state.baskets:
        d = math.hypot(b['x'] - state.player['x'], b['y'] - state.player['y'])
        if d > config.BASKET_AUDIBLE:
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
    heading_deg = math.degrees(state.player['yaw']) % 360
    parts = [f'heading {heading_deg:.0f} degrees']

    n_egg = nearest_audible_egg()
    if n_egg:
        d = math.hypot(n_egg['x'] - state.player['x'], n_egg['y'] - state.player['y'])
        parts.append(f'nearest egg {d:.0f} meters')

    n_basket = nearest_audible_basket()
    if n_basket:
        d = math.hypot(n_basket['x'] - state.player['x'], n_basket['y'] - state.player['y'])
        parts.append(f'nearest basket {d:.0f} meters')

    parts.append(f'{len(state.held)} of {world.player_carry_cap()} held')
    parts.append(f'{world.discovered_count()} baskets found')
    if state.birds:
        parts.append(f'{len(state.birds)} birds in the park')

    speech.say('. '.join(parts) + '.')
