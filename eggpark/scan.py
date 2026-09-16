# SPDX-License-Identifier: CC0-1.0
"""Scanning, the B basket scan, and the scan guide that leads you."""
import math

import pyglet

from eggpark import config, game, sounds, speech, state, world

# ============================================================================
# Scan
# ============================================================================

def try_scan():
    """Bound to Space. Ping every item within SCAN_RANGE, closest first."""
    sounds.fire_scan_start()
    items = []
    for egg in state.eggs:
        d = math.hypot(egg['x'] - state.player['x'], egg['y'] - state.player['y'])
        if d <= config.SCAN_RANGE:
            items.append(('egg', d, egg))
    for b in state.baskets:
        d = math.hypot(b['x'] - state.player['x'], b['y'] - state.player['y'])
        if d <= config.SCAN_RANGE:
            items.append(('basket', d, b))

    if not items:
        stop_scan_guide()
        sounds.fire_fumble()
        speech.say('Nothing in range.')
        return

    items.sort(key=lambda t: t[1])
    speech.say(f'Scanning. {len(items)} items in range.')

    # Lead to the nearest egg. Only eggs: baskets have their own scan (B),
    # because "take me to an egg" and "take me somewhere to put this egg" are
    # different wishes, and a guide that picks between them for you is one
    # you can't predict.
    nearest_egg = next((item for kind, _d, item in items if kind == 'egg'), None)
    if nearest_egg is not None:
        start_scan_guide('egg', nearest_egg)
    else:
        stop_scan_guide()

    # Schedule each ping at a delay proportional to its distance, so
    # close items ping immediately and far items ping later in the sweep.
    max_dist = items[-1][1] if items[-1][1] > 0 else 1.0
    for kind, dist, item in items:
        delay = (dist / max_dist) * config.SCAN_DURATION
        if kind == 'egg':
            pyglet.clock.schedule_once(lambda dt, e=item: sounds.fire_scan_egg_ping(e), delay)
        else:
            pyglet.clock.schedule_once(lambda dt, b=item: sounds.fire_scan_basket_ping(b), delay)


def basket_has_room(basket):
    """Unfound baskets are empty, so they always have room — and leading you
    to one doubles as finding it."""
    return not basket['discovered'] or len(basket['eggs']) < world.basket_cap()


def try_scan_baskets():
    """Bound to B. Lead to the nearest basket with room, found or not."""
    sounds.fire_scan_start()
    best, best_d = None, float('inf')
    for b in state.baskets:
        if not basket_has_room(b):
            continue
        d = math.hypot(b['x'] - state.player['x'], b['y'] - state.player['y'])
        if d <= config.SCAN_RANGE and d < best_d:
            best, best_d = b, d
    if best is None:
        stop_scan_guide()
        sounds.fire_fumble()
        speech.say('No basket with room in range.')
        return
    sounds.fire_scan_basket_ping(best)
    start_scan_guide('basket', best)
    found = '' if best['discovered'] else ' Not found yet.'
    speech.say(f'Basket with room, {int(round(best_d))} metres.{found}')


# ============================================================================
# Scan guide
# ============================================================================
#
# After a scan, a short blip repeats from the direction of what it found and
# leads you there.
#
# The idea comes from the scan guide in Periphery Synthetic by Shift Backtick
# (shiftbacktick.io) — a pulsing tone that tells you where something is by
# how it changes as you move and turn. None of its code or sound is used;
# that game's code is all rights reserved, and this is our own design, tuned
# by ear here.
#
# EACH QUALITY OF THE SOUND ANSWERS ONE QUESTION, AND ONLY ONE:
#   how far?     -> how fast it blips, and how loud
#   which way?   -> pitch: steady when you face it, sagging and wobbling
#                   blip-to-blip as it moves behind you
# The first version let facing speed it up too, and walking toward something,
# walking past it and turning on the spot all came out as "faster blips" and
# blurred together. Keep them separate.
#
# The blip plays a short way off in the target's DIRECTION, not at the
# target itself. OpenAL would otherwise fade it by distance on top of our own
# loudness curve, and a far target would be silent exactly when you most need
# to hear which way it is.

GUIDE_NEAR_RANGE = 40.0       # closer than this, it starts speeding up
GUIDE_NEAR_CURVE = 0.8        # <1 makes the change come on earlier
GUIDE_SLOWEST = 1.0           # seconds between blips, far away
GUIDE_FASTEST = 0.15          # seconds between blips, on arrival
GUIDE_QUIETEST = 0.15         # loudness far away, as a share of the loudest
GUIDE_VOLUME = 0.7            # loudest, before the volume slider
GUIDE_WOBBLE_CENTS = 180      # blip-to-blip wobble, fully behind you
GUIDE_SAG_CENTS = -250        # how far pitch sinks, fully behind you
GUIDE_VOICE_DISTANCE = 1.5    # metres out from you that the blip is placed
GUIDE_GIVE_UP = config.SCAN_RANGE * 1.25  # walked this far away: stop guiding

_scan_guide = None   # {'kind', 'target', 'next_at', 'count'} or None


def start_scan_guide(kind, target):
    global _scan_guide
    _scan_guide = {'kind': kind, 'target': target, 'next_at': game.now(), 'count': 0}


def stop_scan_guide():
    global _scan_guide
    _scan_guide = None


def _scan_guide_still_wanted(g, dist):
    if dist > GUIDE_GIVE_UP:
        return False
    if g['kind'] == 'egg':
        # Collected, or hatched on the ground: it's no longer in the world.
        return g['target'] in state.eggs and dist > config.COLLECT_RADIUS
    target = g['target']
    return (target in state.baskets and basket_has_room(target)
            and dist > config.BASKET_DEPOSIT_RADIUS)


def scan_guide_blip(dist, angle, count):
    """(seconds until next blip, volume, pitch) for one blip.

    `angle` is the target's bearing relative to where you face, in radians:
    0 dead ahead, +/-pi straight behind. Kept free of game state so it can be
    tested directly.
    """
    near = 1.0 - min(1.0, dist / GUIDE_NEAR_RANGE) ** GUIDE_NEAR_CURVE
    interval = GUIDE_SLOWEST + (GUIDE_FASTEST - GUIDE_SLOWEST) * near
    volume = GUIDE_VOLUME * (GUIDE_QUIETEST + (1.0 - GUIDE_QUIETEST) * near)
    away = (1.0 - math.cos(angle)) / 2.0          # 0 facing it, 1 behind
    wobble = GUIDE_WOBBLE_CENTS * away ** 1.5 * (1 if count % 2 else -1)
    cents = GUIDE_SAG_CENTS * away + wobble
    return interval, volume, 2.0 ** (cents / 1200.0)


def tick_scan_guide(t):
    g = _scan_guide
    if g is None:
        return
    target = g['target']
    dx, dy = target['x'] - state.player['x'], target['y'] - state.player['y']
    dist = math.hypot(dx, dy)
    if not _scan_guide_still_wanted(g, dist):
        stop_scan_guide()
        return
    if t < g['next_at']:
        return
    bearing = math.atan2(dy, dx) - state.player['yaw']
    angle = math.atan2(math.sin(bearing), math.cos(bearing))
    interval, volume, pitch = scan_guide_blip(dist, angle, g['count'])
    position = (state.player['x'] + dx / dist * GUIDE_VOICE_DISTANCE,
                state.player['y'] + dy / dist * GUIDE_VOICE_DISTANCE,
                state.player['z'])
    sounds.fire_scan_guide(position, volume=volume, pitch=pitch)
    g['count'] += 1
    # From now, not from the missed deadline: after a pause in the menu the
    # guide picks up with one blip rather than a burst of catch-up blips.
    g['next_at'] = t + interval
