# SPDX-License-Identifier: CC0-1.0
"""Hatching, and the birds that live in your park."""
import math
import random
import time

from eggpark import config, prefs, sounds, speech, state, world

# ============================================================================
# Hatching + birds
# ============================================================================

def hatch_into_wild_bird():
    """A held egg ran out — bird flies off, not yours."""
    sounds.fire_wild_bird_flyoff()
    speech.say('An egg in your hand hatched. The bird flew off.')


def hatch_into_your_bird(basket):
    """A basketed egg ran out — bird is yours, joins the wandering set."""
    now_t = time.monotonic()
    bird = {
        'x': basket['x'] + random.uniform(-1, 1),
        'y': basket['y'] + random.uniform(-1, 1),
        'z': 0.0,
        'freq_idx': random.randrange(len(config.PENTATONIC_FREQS)),
        'call_style': random.choice(sounds.BIRD_CALL_STYLES),
        'home_x': basket['x'],
        'home_y': basket['y'],
        'wander_angle': random.uniform(0, 2 * math.pi),
        'next_call_at': now_t + random.uniform(2.0, 4.0),
        'next_ambient_at': now_t + random.uniform(
            config.BIRD_AMBIENT_MIN_INTERVAL, config.BIRD_AMBIENT_MAX_INTERVAL),
        'eggs_to_lay': config.BIRD_EGGS_TO_LAY,
        'lay_timer': prefs.settings['lay_time'],
    }
    state.birds.append(bird)
    sounds.fire_hatch_in_basket(basket)
    speech.say(f'A bird hatched. {len(state.birds)} birds in the park.')


def tick_hatching(dt):
    # Held eggs — timer only advances if hand-hatching is enabled, so
    # turning the toggle off effectively freezes any held egg indefinitely.
    if prefs.settings['enable_hand_hatching']:
        for h in list(state.held):
            h['hatch_timer'] -= dt
            if h['hatch_timer'] <= 0:
                state.held.remove(h)
                hatch_into_wild_bird()
                continue
            # Warning chirp while the held egg is in its last seconds.
            # Fires once per WARNING_INTERVAL — non-positional since the
            # egg is in your hand.
            if h['hatch_timer'] <= config.WARNING_WINDOW:
                h['next_warning'] -= dt
                if h['next_warning'] <= 0:
                    if prefs.settings['enable_egg_warnings']:
                        sounds.fire_egg_warning()
                    h['next_warning'] = config.WARNING_INTERVAL

    # Basket eggs — same pattern. Disabling basket-hatching means deposited
    # eggs just sit there forever; the basket becomes a museum.
    if prefs.settings['enable_basket_hatching']:
        for b in state.baskets:
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
                if he['hatch_timer'] <= config.WARNING_WINDOW:
                    he['next_warning'] = he.get('next_warning', 0.0) - dt
                    if he['next_warning'] <= 0:
                        if prefs.settings['enable_egg_warnings']:
                            sounds.fire_egg_warning(position=(b['x'], b['y'], b['z']))
                        he['next_warning'] = config.WARNING_INTERVAL


def tick_birds(dt):
    now_t = time.monotonic()
    for bird in state.birds:
        # Wander. Random-walk angle drift + forward motion.
        bird['wander_angle'] += random.uniform(-0.5, 0.5) * dt
        dx = math.cos(bird['wander_angle']) * config.BIRD_WANDER_SPEED * dt
        dy = math.sin(bird['wander_angle']) * config.BIRD_WANDER_SPEED * dt
        nx = bird['x'] + dx
        ny = bird['y'] + dy
        # Stay within wander radius of home — if drifting too far, turn back.
        if math.hypot(nx - bird['home_x'], ny - bird['home_y']) <= config.BIRD_WANDER_RADIUS:
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
            if prefs.settings['enable_bird_calls']:
                sounds.fire_bird_call(bird)
            bird['next_call_at'] = now_t + random.uniform(
                config.BIRD_CALL_MIN_INTERVAL, config.BIRD_CALL_MAX_INTERVAL
            )

        # Wing-flap / rustle / small movement noises between calls.
        # Scheduled independently so the two streams interleave instead of
        # falling into a predictable rhythm with the calls.
        if now_t >= bird.get('next_ambient_at', 0):
            if prefs.settings['enable_bird_ambient']:
                sounds.fire_bird_ambient(bird)
            bird['next_ambient_at'] = now_t + random.uniform(
                config.BIRD_AMBIENT_MIN_INTERVAL, config.BIRD_AMBIENT_MAX_INTERVAL
            )


def tick_laying(dt):
    """Each bird with eggs left to lay counts down and lays one near home.

    Counts down with dt, like hatching, so it stops while the menu or
    settings are open and the time left is saved with the park. Birds from
    before laying existed have neither field, and get a plain bird's one egg
    and a full wait.
    """
    if not prefs.settings['enable_bird_laying']:
        return
    for bird in state.birds:
        if bird.setdefault('eggs_to_lay', config.BIRD_EGGS_TO_LAY) <= 0:
            continue
        bird['lay_timer'] = bird.get('lay_timer', prefs.settings['lay_time']) - dt
        if bird['lay_timer'] > 0:
            continue
        egg = world.lay_egg_near(bird['home_x'], bird['home_y'])
        state.eggs.append(egg)
        bird['eggs_to_lay'] -= 1
        bird['lay_timer'] = prefs.settings['lay_time']
        sounds.fire_egg_laid(egg)
        world.log_counts(f'a bird laid an egg, {bird["eggs_to_lay"]} left for it to lay')
