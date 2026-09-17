# SPDX-License-Identifier: CC0-1.0
"""Chests: bigger places to keep eggs, each holding three random gifts."""
import math
import random

from eggpark import config, scan, sounds, speech, state, world

# ============================================================================
# Chests
# ============================================================================
#
# A chest is a basket's bigger cousin. You walk onto it to find it, press F
# to put eggs in, and they hatch into birds whose home is the chest. It's
# wider (CHEST_DEPOSIT_RADIUS, CHEST_DISCOVER_RADIUS), holds more
# (world.chest_cap), and has three gift slots, rolled once, the moment you
# find it.
#
# Each slot is any mix of three gifts, and every part rolls separately,
# CHEST_GIFT_MIN..CHEST_GIFT_MAX:
#   eggs     birds that hatch in THIS chest lay that many more per clutch
#   carry    you can carry that many more eggs, from now on
#   storage  every basket and chest holds that many more, from now on
# On top of the gifts, finding any chest adds one to what baskets and chests
# hold.

GIFT_KINDS = ('eggs', 'carry', 'storage')
# Every non-empty mix of the three: seven kinds of slot, equally likely.
SLOT_MIXES = [tuple(k for i, k in enumerate(GIFT_KINDS) if mask >> i & 1)
              for mask in range(1, 2 ** len(GIFT_KINDS))]


def roll_gifts():
    """Three slots, each a mix of gifts with its own amounts."""
    return [{kind: random.randint(config.CHEST_GIFT_MIN, config.CHEST_GIFT_MAX)
             for kind in random.choice(SLOT_MIXES)}
            for _ in range(config.CHEST_GIFT_SLOTS)]


def roll_net():
    """True if this chest holds a net. Rolled apart from the three slots.

    Never once your reach is at NET_REACH_MAX: a net that does nothing is a
    gift that isn't one, and hearing "and a net" would suggest it did."""
    if world.collect_radius() >= config.NET_REACH_MAX:
        return False
    return random.random() < config.NET_CHANCE


def gift_totals(gifts):
    return {kind: sum(slot.get(kind, 0) for slot in gifts) for kind in GIFT_KINDS}


def found_count():
    return sum(1 for c in state.chests if c['discovered'])


def chest_has_room(chest):
    return chest['discovered'] and len(chest['eggs']) < world.chest_cap()


# ---------------------------------------------------------------- spawning

def unfound_chests_in_reach():
    return [c for c in state.chests
            if not c['discovered']
            and math.hypot(c['x'] - state.player['x'], c['y'] - state.player['y']) <= config.CHEST_AUDIBLE]


def forget_distant_chests():
    """Unfound chests far behind you are dropped, like unfound baskets.
    A found chest is never removed: it holds eggs and gave you gifts."""
    for c in list(state.chests):
        if c['discovered']:
            continue
        if math.hypot(c['x'] - state.player['x'], c['y'] - state.player['y']) > config.CHEST_FORGET_DISTANCE:
            state.chests.remove(c)
            world.log_counts('unfound chest forgotten, far behind')


def maybe_spawn_chest():
    """Keep CHEST_TARGET_UNFOUND unfound chests within earshot, placed like
    baskets but further out, and clear of every basket and chest."""
    if len(unfound_chests_in_reach()) >= config.CHEST_TARGET_UNFOUND:
        return
    for _attempt in range(config.CHEST_PLACE_ATTEMPTS):
        angle = random.uniform(0.0, 2.0 * math.pi)
        dist = random.uniform(config.CHEST_SPAWN_MIN, config.CHEST_SPAWN_MAX)
        x = state.player['x'] + math.cos(angle) * dist
        y = state.player['y'] + math.sin(angle) * dist
        if any(math.hypot(o['x'] - x, o['y'] - y) < config.CHEST_MIN_SEPARATION
               for o in state.baskets + state.chests):
            continue
        state.chests.append({
            'x': x, 'y': y, 'z': 0.0,
            'discovered': False,
            'eggs': [],
            'gifts': [],
            'clutch_bonus': 0,
        })
        return


# ---------------------------------------------------------------- finding

def gift_speech(totals):
    parts = []
    if totals['carry']:
        parts.append(f'Carry {totals["carry"]} more.')
    parts.append(f'Baskets and chests hold {totals["storage"] + 1} more.')
    if totals['eggs']:
        parts.append(f'Birds hatched here lay {totals["eggs"]} more eggs a clutch.')
    return ' '.join(parts)


def try_discover_chest():
    """Walk within CHEST_DISCOVER_RADIUS of an unfound chest: find it, roll and
    apply its gifts, and say what they were."""
    for c in state.chests:
        if c['discovered']:
            continue
        if math.hypot(c['x'] - state.player['x'], c['y'] - state.player['y']) > config.CHEST_DISCOVER_RADIUS:
            continue
        c['discovered'] = True
        c['gifts'] = roll_gifts()
        totals = gift_totals(c['gifts'])
        state.progress['carry_bonus'] += totals['carry']
        state.progress['storage_bonus'] += totals['storage']
        c['clutch_bonus'] = totals['eggs']
        c['net'] = roll_net()
        net_line = ''
        if c['net']:
            state.progress['nets'] += 1
            net_line = f'And a net. You pick up eggs from {world.collect_radius():g} metres. '
        world.log_counts(f'chest found, gifts {c["gifts"]}, net {c["net"]}')
        sounds.fire_chest_discover(c)
        speech.say(
            f'Chest found. {gift_speech(totals)} {net_line}'
            f'Carry capacity {world.player_carry_cap()}. '
            f'Basket capacity {world.basket_cap()}. Chest capacity {world.chest_cap()}.')
        return


def current_chest():
    for c in state.chests:
        if math.hypot(c['x'] - state.player['x'], c['y'] - state.player['y']) <= config.CHEST_DEPOSIT_RADIUS:
            return c
    return None


# ---------------------------------------------------------------- scanning

def _nearest_chest(wanted):
    best, best_d = None, float('inf')
    for c in state.chests:
        if not wanted(c):
            continue
        d = math.hypot(c['x'] - state.player['x'], c['y'] - state.player['y'])
        if d <= config.SCAN_RANGE and d < best_d:
            best, best_d = c, d
    return best, best_d


def try_scan_found_chests():
    """Bound to C. Lead to the nearest chest you've found that has room."""
    sounds.fire_scan_start()
    best, best_d = _nearest_chest(chest_has_room)
    if best is None:
        scan.stop_scan_guide()
        sounds.fire_fumble()
        speech.say('No found chest with room in range.')
        return
    sounds.fire_scan_chest_ping(best)
    scan.start_scan_guide('chest', best)
    speech.say(f'Found chest with room, {int(round(best_d))} metres.')


def try_scan_unfound_chests():
    """Bound to Shift+C. Lead to the nearest chest you haven't found."""
    sounds.fire_scan_start()
    best, best_d = _nearest_chest(lambda c: not c['discovered'])
    if best is None:
        scan.stop_scan_guide()
        sounds.fire_fumble()
        speech.say('No unfound chest in range.')
        return
    sounds.fire_scan_chest_ping(best)
    scan.start_scan_guide('unfound chest', best)
    speech.say(f'Unfound chest, {int(round(best_d))} metres.')


def nearest_audible_chest():
    best, best_d = None, float('inf')
    for c in state.chests:
        d = math.hypot(c['x'] - state.player['x'], c['y'] - state.player['y'])
        if d <= config.CHEST_AUDIBLE and d < best_d:
            best, best_d = c, d
    return best
