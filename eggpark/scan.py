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
    px, py = state.player['x'], state.player['y']
    # Only the nearest few eggs are ever pinged, so only the nearest few are
    # asked for. Building an entry for every egg in range and sorting the lot
    # measured 52.8 ms in a crowded park -- a fifth of a second of the game
    # stopping dead, every time Space was pressed. The count for the spoken line
    # is worked out from whole cells instead of egg by egg.
    egg_hits = state.eggs.nearest_many(px, py, config.SCAN_RANGE,
                                       config.SCAN_MAX_PINGS_PER_KIND)
    eggs_in_range = state.eggs.count_within(px, py, config.SCAN_RANGE)
    items = [('egg', d, egg) for d, egg in egg_hits]
    for b in state.baskets:
        d = math.hypot(b['x'] - state.player['x'], b['y'] - state.player['y'])
        if d <= config.SCAN_RANGE:
            items.append(('basket', d, b))
    for c in state.chests:
        d = math.hypot(c['x'] - state.player['x'], c['y'] - state.player['y'])
        if d <= config.SCAN_RANGE:
            items.append(('chest', d, c))

    if not items:
        stop_scan_guide()
        sounds.fire_fumble()
        speech.say('Nothing in range.')
        return

    items.sort(key=lambda t: t[1])
    # What is in range, not what is being pinged: the eggs were already thinned
    # to the nearest few before they got here.
    in_range = eggs_in_range + sum(1 for kind, _d, _i in items if kind != 'egg')
    speech.say(f'Scanning. {in_range} items in range.')

    # Lead to the nearest egg. Only eggs: baskets have their own scan (B),
    # because "take me to an egg" and "take me somewhere to put this egg" are
    # different wishes, and a guide that picks between them for you is one
    # you can't predict.
    nearest_egg = next((item for kind, _d, item in items if kind == 'egg'), None)
    if nearest_egg is not None:
        start_scan_guide('egg', nearest_egg)
    else:
        stop_scan_guide()

    # Only the nearest few of each kind ping. Space used to ping everything
    # in range: hundreds of eggs after a few clutches, which was a wall of
    # sound, and past what the audio card will play at once — it crashed the
    # game. `items` is sorted, so this keeps the nearest of each.
    kept, seen = [], {}
    for entry in items:
        seen[entry[0]] = seen.get(entry[0], 0) + 1
        if seen[entry[0]] <= config.SCAN_MAX_PINGS_PER_KIND:
            kept.append(entry)
    if len(kept) < in_range:
        speech.log_event(f'scan: {in_range} items in range, '
                         f'pinging the nearest {len(kept)}')

    # Schedule each ping at a delay proportional to its distance, so
    # close items ping immediately and far items ping later in the sweep.
    max_dist = kept[-1][1] if kept[-1][1] > 0 else 1.0
    for kind, dist, item in kept:
        delay = (dist / max_dist) * config.SCAN_DURATION
        if kind == 'egg':
            pyglet.clock.schedule_once(lambda dt, e=item: sounds.fire_scan_egg_ping(e), delay)
        elif kind == 'chest':
            pyglet.clock.schedule_once(lambda dt, c=item: sounds.fire_scan_chest_ping(c), delay)
        else:
            pyglet.clock.schedule_once(lambda dt, b=item: sounds.fire_scan_basket_ping(b), delay)


def basket_has_room(basket):
    """Unfound baskets are empty, so they always have room — and leading you
    to one doubles as finding it."""
    return not basket['discovered'] or len(basket['eggs']) < world.basket_cap()


# Two basket scans, because found and unfound baskets want different things
# from you and their chimes blur together once there are enough of them:
#   B  a basket you've FOUND that has room: somewhere to put what you carry
#   V  a basket you HAVEN'T found yet: exploring, and growing your capacity
# One key used to do both, picking whichever was nearer, and you couldn't tell
# which kind it had chosen until it spoke.

def _nearest_basket(wanted):
    best, best_d = None, float('inf')
    for b in state.baskets:
        if not wanted(b):
            continue
        d = math.hypot(b['x'] - state.player['x'], b['y'] - state.player['y'])
        if d <= config.SCAN_RANGE and d < best_d:
            best, best_d = b, d
    return best, best_d


def try_scan_found_baskets():
    """Bound to B. Lead to the nearest basket you've found that has room."""
    sounds.fire_scan_start()
    best, best_d = _nearest_basket(lambda b: b['discovered'] and basket_has_room(b))
    if best is None:
        stop_scan_guide()
        sounds.fire_fumble()
        speech.say('No found basket with room in range.')
        return
    sounds.fire_scan_basket_ping(best)
    start_scan_guide('basket', best)
    speech.say(f'Found basket with room, {int(round(best_d))} metres.')


def try_scan_unfound_baskets():
    """Bound to V. Lead to the nearest basket you haven't found yet."""
    sounds.fire_scan_start()
    best, best_d = _nearest_basket(lambda b: not b['discovered'])
    if best is None:
        stop_scan_guide()
        sounds.fire_fumble()
        speech.say('No unfound basket in range.')
        return
    sounds.fire_scan_basket_ping(best)
    start_scan_guide('unfound basket', best)
    speech.say(f'Unfound basket, {int(round(best_d))} metres.')


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
    # Nothing is leading you any more, so the park comes straight back up
    # rather than waiting out the last blip's hold.
    sounds.stop_ducking()


def _scan_guide_still_wanted(g, dist):
    if g['kind'] == 'picked chest':
        # Chosen from the chest list (eggpark/chestlist.py): full or not, near
        # or far, you asked for this one, so it leads until you're on it.
        return g['target'] in state.chests and dist > config.CHEST_DEPOSIT_RADIUS
    if dist > GUIDE_GIVE_UP:
        return False
    if g['kind'] == 'egg':
        # Collected, or hatched on the ground: it's no longer in the world.
        return g['target'] in state.eggs and dist > world.collect_radius()
    target = g['target']
    if g['kind'] == 'unfound chest':
        return target in state.chests and not target['discovered']
    if g['kind'] == 'chest':
        return (target in state.chests and len(target['eggs']) < world.chest_cap()
                and dist > config.CHEST_DEPOSIT_RADIUS)
    if g['kind'] == 'unfound basket':
        # Finding it is arriving: its discovery chime takes over from here.
        return target in state.baskets and not target['discovered']
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
