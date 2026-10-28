# SPDX-License-Identifier: CC0-1.0
"""Hatching, and the birds that live in your park."""
import math
import random
import time

from eggpark import config, prefs, sounds, speech, state, tally, world

# ============================================================================
# Hatching + birds
# ============================================================================

def hatch_into_wild_bird():
    """A held egg ran out — bird flies off, not yours. Counted, not announced:
    a handful of eggs can come due together and that was a line each."""
    tally.EGG_LOST.add()


# One event, one sound — see eggpark/tally.py for the rule and why. Nothing
# in here announces anything per egg: it counts, and tally reports the count
# once a frame at most.


def make_your_bird(basket):
    """The bird itself, with no sound and nothing said. The announcing is the
    caller's job, because a whole basket can hatch in one frame."""
    return _new_bird(basket)


def hatch_into_your_bird(basket):
    """A basketed egg ran out — bird is yours, joins the wandering set.

    Announces on its own: this is the one-at-a-time path, used when something
    other than the hatch loop hatches a single egg."""
    _new_bird(basket)
    sounds.fire_hatch_in_basket(basket)
    if prefs.settings.get('say_hatching', False):
        speech.say(f'A bird hatched. {len(state.birds)} birds in the park.')


def _new_bird(basket):
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
        # A chest's egg and clutch gifts ride along with every bird it hatches.
        'clutch_bonus': basket.get('clutch_bonus', 0),
        'clutches_left': clutches_in_a_life(basket.get('extra_clutches', 0)),
        'lay_timer': prefs.settings['lay_time'],
    }
    state.birds.append(bird)
    return bird


def tick_hatching(dt):
    # Eggs on the ground. With ground hatching on, an egg nobody rescues
    # counts down where it lies and hatches into a wild bird that leaves.
    # This is what stops a park of laying birds from filling up forever:
    # eggs lying out can't outlast one hatch time, and your flock only grows
    # from the eggs you actually get to safety.
    #
    # A wild egg that hatches away is replaced, so the wild supply stays what
    # it was. A laid egg is simply gone. No speech: with a big flock this
    # would never stop talking. You hear it fly off if it's near you.
    # Only GROUND_HATCH_PER_FRAME leave in any one frame, and a frame that
    # hatches several writes ONE log line for the lot.
    #
    # Eggs whose timers line up exactly do exist, and a park proved it: 4,161
    # eggs, every one with 180.0 seconds left, because the timer only ticks
    # while this setting is on and they had all been saved untouched. Turning
    # it on would have hatched every one of them in a single frame — a stall,
    # a wall of flyoffs, and 4,161 log lines. Trickling them out costs a few
    # seconds of make-believe and nothing else: an egg that hatches a moment
    # late is indistinguishable from one that was laid a moment later.
    if prefs.settings['enable_ground_hatching']:
        # Every egg's timer ticks, every frame, even during a backlog — only
        # the LEAVING is rationed. Stopping early instead (once enough ready
        # eggs were found) looked equivalent and wasn't: eggs further down the
        # list then stopped counting down at all, so a park that was overdue
        # in one lump drained at the rate its own timers allowed, which was
        # no rate at all. A test of 4,161 eggs due at once caught it.
        # Every egg's timer still ticks at the same average rate -- but a share
        # of the eggs each frame, each advanced by that much more time, instead
        # of all of them every frame. At 40,000 eggs the whole-list version
        # measured 3.5 ms a frame, a fifth of what a frame has; this is a tenth
        # of that. A timer measured in minutes cannot tell the difference, and
        # the LEAVING is still rationed below.
        ready = []
        slice_eggs, step = state.eggs.ticking(dt)
        for egg in slice_eggs:
            egg['hatch_timer'] = egg.get('hatch_timer', prefs.settings['hatch_time']) - step
            if egg['hatch_timer'] <= 0:
                ready.append(egg)
        ready = ready[:config.GROUND_HATCH_PER_FRAME]
        laid_gone = wild_gone = 0
        for egg in ready:
            state.eggs.remove(egg)
            if egg.get('laid'):
                laid_gone += 1
            else:
                wild_gone += 1
                state.eggs.append(world.spawn_egg_far_from_player())
            tally.GROUND_FLYOFF.add((egg['x'], egg['y'], egg['z']))
        if ready:
            world.log_counts(f'{len(ready)} egg(s) hatched on the ground and flew off '
                             f'({laid_gone} laid, {wild_gone} wild and replaced)')

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
                        tally.EGG_WARNING.add()
                    h['next_warning'] = config.WARNING_INTERVAL

    # Basket eggs — same pattern. Disabling basket-hatching means deposited
    # eggs just sit there forever; the basket becomes a museum.
    if prefs.settings['enable_basket_hatching']:
        for b in state.baskets + state.chests:
            for he in list(b['eggs']):
                he['hatch_timer'] -= dt
                if he['hatch_timer'] <= 0:
                    b['eggs'].remove(he)
                    make_your_bird(b)
                    tally.BIRD_HATCHED.add((b['x'], b['y'], b['z']))
                    continue
                # Same warning, but positional at the basket so the player
                # can hear which basket is about to pop. Emotionally this
                # is the *positive* warning (a bird is incoming) — same
                # sample category, the recording can carry either valence.
                if he['hatch_timer'] <= config.WARNING_WINDOW:
                    he['next_warning'] = he.get('next_warning', 0.0) - dt
                    if he['next_warning'] <= 0:
                        if prefs.settings['enable_egg_warnings']:
                            tally.EGG_WARNING.add((b['x'], b['y'], b['z']))
                        he['next_warning'] = config.WARNING_INTERVAL


# Birds are moved a third of the flock a frame, each with three frames' worth
# of time. 28 Oct 2026: 1,505 birds every frame was 4 ms of the 16 a frame
# has. A bird's position only matters when it calls or rustles, and three
# frames is a twentieth of a second, so nothing you can hear changes.
BIRD_TICK_SLICES = 3
_bird_slice = 0


def tick_birds(dt):
    global _bird_slice
    if dt > config.MAX_MOVE_DT or len(state.birds) < 100:
        flock = state.birds            # a stall, or a small flock: everyone
    else:
        _bird_slice = (_bird_slice + 1) % BIRD_TICK_SLICES
        flock = state.birds[_bird_slice::BIRD_TICK_SLICES]
        dt *= BIRD_TICK_SLICES
    now_t = time.monotonic()
    for bird in flock:
        # Flights: every so often a bird takes off and crosses its range in a
        # straight line, then goes back to wandering. This is what makes a
        # flock sound alive — something passing you is far more legible than
        # something drifting, and the rustle it fires on the way reads as
        # wings rather than as an object sliding about.
        flying_until = bird.get('flying_until', 0.0)
        if now_t >= bird.get('next_flight_at', 0.0):
            bird['flying_until'] = now_t + random.uniform(
                config.BIRD_FLIGHT_MIN_LENGTH, config.BIRD_FLIGHT_MAX_LENGTH)
            bird['next_flight_at'] = bird['flying_until'] + random.uniform(
                config.BIRD_FLIGHT_MIN_INTERVAL, config.BIRD_FLIGHT_MAX_INTERVAL)
            # A new heading for the flight, and a rustle as it goes.
            bird['wander_angle'] = random.uniform(0.0, 2.0 * math.pi)
            if prefs.settings['enable_bird_ambient']:
                tally.RUSTLE.add((bird['x'], bird['y'], bird['z']))
            flying_until = bird['flying_until']
        flying = now_t < flying_until
        speed = config.BIRD_FLIGHT_SPEED if flying else config.BIRD_WANDER_SPEED

        # Wander. Random-walk angle drift + forward motion. A bird in flight
        # holds its line; a bird pottering about wobbles.
        if not flying:
            bird['wander_angle'] += random.uniform(-0.5, 0.5) * dt
        dx = math.cos(bird['wander_angle']) * speed * dt
        dy = math.sin(bird['wander_angle']) * speed * dt
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
                tally.RUSTLE.add((bird['x'], bird['y'], bird['z']))
            bird['next_ambient_at'] = now_t + random.uniform(
                config.BIRD_AMBIENT_MIN_INTERVAL, config.BIRD_AMBIENT_MAX_INTERVAL
            )


def tick_laying(dt):
    """Each bird counts down to its next clutch and lays it near home.

    Counts down with dt, like hatching, so it stops while the menu or
    settings are open and the time left is saved with the park. Birds from
    before laying existed have no timer yet, and get a full wait.
    """
    if not prefs.settings['enable_bird_laying']:
        return
    # At most LAY_CLUTCHES_PER_FRAME clutches are laid in any one frame, and
    # the rest wait for the next one.
    #
    # Birds hatch in batches, so their laying timers line up, and then they
    # all come due together. A flock of 231 was measured laying dozens of
    # clutches in a single frame: 290 ms of placement work while the world
    # stood still, which is felt as footsteps arriving in clumps rather than
    # as a frame rate. One a frame is 60 a second of capacity, far more than
    # any flock needs, and nothing is skipped — a bird that has to wait a
    # frame or two lays a moment later, which is invisible.
    laid = 0
    done = []
    for bird in state.birds:
        bird['lay_timer'] = bird.get('lay_timer', prefs.settings['lay_time']) - dt
        if bird['lay_timer'] > 0:
            continue
        if laid >= config.LAY_CLUTCHES_PER_FRAME:
            bird['lay_timer'] = 0.0       # due, and first in line next frame
            continue
        bird['lay_timer'] = prefs.settings['lay_time']
        lay_clutch(bird)
        laid += 1
        # Birds from before clutches ran out have no count: they get a plain
        # bird's roll now, counting this clutch as their first.
        if 'clutches_left' not in bird:
            bird['clutches_left'] = clutches_in_a_life(0)
        bird['clutches_left'] -= 1
        if bird['clutches_left'] <= 0:
            done.append(bird)
    for bird in done:
        state.birds.remove(bird)
        tally.BIRD_LEFT.add((bird['x'], bird['y'], bird['z']))
    if done:
        world.log_counts(f'{len(done)} bird(s) laid their last clutch and flew off')


def clutches_in_a_life(extra):
    """How many clutches a new bird will lay before it flies off."""
    return random.randint(config.CLUTCHES_MIN, config.CLUTCHES_MAX) + extra


def clutch_size(bird):
    return random.randint(config.CLUTCH_MIN, config.CLUTCH_MAX) + bird.get('clutch_bonus', 0)


def lay_clutch(bird):
    """Lay a whole clutch at once. One laid sound, from the first egg: a
    clutch is one event, and ten plops on top of each other would be noise."""
    size = clutch_size(bird)
    clutch = []
    # No grid to build: state.eggs is one (see eggpark/eggfield.py), and each egg
    # is in it the moment it is appended, so the next egg of the clutch already
    # sees its sibling. Sorting the park for every clutch used to be most of the
    # cost of laying one.
    for _ in range(size):
        egg = world.lay_egg_near(bird['home_x'], bird['home_y'])
        state.eggs.append(egg)
        clutch.append(egg)
    if clutch:
        sounds.fire_egg_laid(clutch[0])
    world.log_counts(f'a bird laid a clutch of {size}')
