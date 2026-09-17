# SPDX-License-Identifier: CC0-1.0
"""Eggs and baskets: capacity, spawning, picking up, finding, depositing."""
import math
import random

from eggpark import config, prefs, scan, sounds, speech, state

# ============================================================================
# Capacity helpers
# ============================================================================

def discovered_count():
    return sum(1 for b in state.baskets if b['discovered'])


def player_carry_cap():
    """Starts at CARRY_START; +1 per CARRY_BUMP_EVERY baskets discovered."""
    return config.CARRY_START + (discovered_count() // config.CARRY_BUMP_EVERY)


def basket_cap():
    """Each basket holds one egg per basket discovered, and never less than
    you can carry: one trip's worth must always fit in one basket. Today the
    found count is always the bigger of the two, but carrying is meant to be
    boosted by chests, and this has to stay true when it is."""
    return max(1, discovered_count(), player_carry_cap())


def log_counts(event):
    """A play-log line with every number capacity depends on, as it is now."""
    speech.log_event(
        f'{event} | found {discovered_count()} | carry {len(state.held)} of '
        f'{player_carry_cap()} | basket cap {basket_cap()} | '
        f'baskets in world {len(state.baskets)} | eggs in world {len(state.eggs)} | '
        f'at ({state.player["x"]:.1f}, {state.player["y"]:.1f})')


# Watchdog for the play log. Finds can only go up within a park, so if either
# of these ever drops without a new park, something is wrong and the log
# says exactly when.
_last_seen_counts = {'found': 0, 'carry': 0}


def watch_counts():
    found, carry = discovered_count(), player_carry_cap()
    if found < _last_seen_counts['found'] or carry < _last_seen_counts['carry']:
        log_counts(f'UNEXPECTED DROP (was found {_last_seen_counts["found"]}, '
                   f'carry cap {_last_seen_counts["carry"]})')
    _last_seen_counts.update(found=found, carry=carry)


# ============================================================================
# Egg lifecycle
# ============================================================================

def spawn_egg_far_from_player():
    """A new egg EGG_SPAWN_MIN..MAX from a random found basket, at least
    EGG_MIN_SEPARATION from the other eggs and EGG_MIN_FROM_PLAYER from you.

    Unlike a basket, an egg can't just wait for the next frame if there's no
    room: one is always owed the moment you pick one up. So if no try clears
    the spacing, it takes the try that was furthest from its nearest egg.
    """
    anchors = [(b['x'], b['y']) for b in state.baskets if b['discovered']] or [(0.0, 0.0)]
    return _place_egg(anchors, config.EGG_SPAWN_MIN, config.EGG_SPAWN_MAX,
                      config.EGG_MIN_SEPARATION)


def lay_egg_near(home_x, home_y, grid=None):
    """An egg laid by a bird: close to its home basket, marked as laid.

    Laid eggs are not replaced when picked up. Only wild eggs are, so the wild
    supply stays what it was and every extra egg in the park came from a bird.

    Laying a whole clutch? Pass one grid (egg_grid) and grid_add each egg to
    it, so the park is sorted once per clutch, not once per egg.
    """
    egg = _place_egg([(home_x, home_y)], config.LAID_EGG_MIN, config.LAID_EGG_MAX,
                     config.LAID_EGG_MIN_SEPARATION, grid)
    egg['laid'] = True
    return egg


# Egg placement asks "how close is the nearest egg to this spot?" up to
# EGG_PLACE_ATTEMPTS times per egg. Asking every egg in the park each time was
# fine with four eggs and not with clutches: at 10,000 eggs, one clutch of ten
# took about four million distance checks, because eggs bunch around a bird's
# home and few tries succeed first time.
#
# So eggs are sorted into square cells the size of the separation being
# checked. Any egg close enough to matter lies in the spot's own cell or one
# of the eight around it, so only those are looked at. The answer to "is
# anything within `separation`?" is exactly the same, and so is the distance
# when something is, so the same spot is chosen as before. Proven by laying
# clutches from the same random seed with both versions.

def egg_grid(cell):
    grid = {}
    for egg in state.eggs:
        grid_add(grid, cell, egg)
    return grid


def grid_add(grid, cell, egg):
    grid.setdefault((math.floor(egg['x'] / cell), math.floor(egg['y'] / cell)), []).append(egg)


def _nearest_egg_within_reach(grid, cell, x, y):
    """Distance to the nearest egg in the 3x3 cells around (x, y), or infinity.
    Exact whenever the true nearest egg is closer than `cell`."""
    cx, cy = math.floor(x / cell), math.floor(y / cell)
    best = float('inf')
    for gx in (cx - 1, cx, cx + 1):
        for gy in (cy - 1, cy, cy + 1):
            for e in grid.get((gx, gy), ()):
                d = math.hypot(e['x'] - x, e['y'] - y)
                if d < best:
                    best = d
    return best


def _place_egg(anchors, dist_min, dist_max, separation, grid=None):
    """An egg dist_min..dist_max from a random anchor, `separation` from the
    other eggs and EGG_MIN_FROM_PLAYER from you, as far as possible."""
    if grid is None:
        grid = egg_grid(separation)
    best, best_gap = None, -1.0
    for _attempt in range(config.EGG_PLACE_ATTEMPTS):
        ax, ay = random.choice(anchors)
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(dist_min, dist_max)
        x = ax + math.cos(angle) * dist
        y = ay + math.sin(angle) * dist
        if math.hypot(x - state.player['x'], y - state.player['y']) < config.EGG_MIN_FROM_PLAYER:
            continue
        gap = _nearest_egg_within_reach(grid, separation, x, y)
        if gap > best_gap:
            best, best_gap = (x, y), gap
        if gap >= separation:
            break
    if best is None:
        # Every try landed at your feet. Put it on the far side of the anchor
        # from you, at the furthest distance allowed.
        ax, ay = random.choice(anchors)
        away = math.atan2(ay - state.player['y'], ax - state.player['x'])
        best = (ax + math.cos(away) * dist_max, ay + math.sin(away) * dist_max)
    x, y = best
    return {
        'x': x,
        'y': y,
        'z': 0.0,
        'freq_idx': random.randrange(len(config.PENTATONIC_FREQS)),
        'hatch_timer': prefs.settings['hatch_time'],
    }


def reset_world():
    """Wipe every trace of the current park, ready for a fresh spawn.

    Everything mutable in World state gets cleared here. If you add a new
    piece of per-park state up there, clear it here too — a leftover that
    survives a restart shows up as a ghost: a bird calling from a park that
    no longer exists, and no way to work out where it came from.

    Lists are emptied in place rather than rebound, because other modules
    and closures hold references to these exact objects.
    """
    state.eggs.clear()
    state.held.clear()
    state.birds.clear()
    # Baskets are REBUILT, not just reset: generated ones have to go, or a
    # new park inherits every basket the last one grew.
    state.baskets.clear()
    state.baskets.extend(dict(b, eggs=[]) for b in state.INITIAL_BASKETS)
    state.player.update({'x': 0.0, 'y': 0.0, 'z': 0.0, 'yaw': 0.0})
    _last_seen_counts.update(found=0, carry=0)
    log_counts('world reset for a new park')
    # A guide left over would lead toward a basket from the old park.
    scan.stop_scan_guide()


def initial_spawn():
    """Stagger initial eggs in known directions.

    Assumes an empty world — it only appends. Call `reset_world()` first if
    a park already exists, or you get two parks overlaid on each other.
    """
    presets = [
        (30.0,   0.0),
        ( 0.0,  30.0),
        (-30.0,  0.0),
        ( 0.0, -30.0),
    ]
    for i in range(config.NUM_EGGS):
        x, y = presets[i] if i < len(presets) else (
            random.uniform(-50, 50), random.uniform(-50, 50)
        )
        state.eggs.append({
            'x': x, 'y': y, 'z': 0.0,
            'freq_idx': i % len(config.PENTATONIC_FREQS),
            'hatch_timer': prefs.settings['hatch_time'],
        })


def try_collect_eggs():
    """Auto-collect any egg within COLLECT_RADIUS, respecting carry cap."""
    if not prefs.settings['enable_pickup']:
        return
    for egg in list(state.eggs):
        dx = egg['x'] - state.player['x']
        dy = egg['y'] - state.player['y']
        if math.hypot(dx, dy) > config.COLLECT_RADIUS:
            # Stepped away: the next time you reach it, it may tell you again.
            egg.pop('refused', None)
            continue
        if len(state.held) >= player_carry_cap():
            # Once per visit. This runs every frame, and it used to refuse
            # every frame: a play log caught 465 "Hands full" sounds and
            # spoken lines in eight seconds of standing on one egg.
            if not egg.get('refused'):
                egg['refused'] = True
                log_counts('egg refused, hands full')
                sounds.fire_refuse_sound()
                speech.say(f'Hands full. {len(state.held)} eggs held.')
            # Don't dequeue — egg stays so the player can come back after
            # depositing.
            return
        # Collect: move this egg's hatch timer into hand.
        # next_warning is a per-egg countdown to the next warning chirp;
        # it only matters once hatch_timer drops below WARNING_WINDOW.
        #
        # With ground hatching on, the egg has been counting down where it
        # lay, and it keeps what it has left: picking one up at the last
        # second must not wind it back to full.
        #
        # With it off, eggs on the ground never tick, so the clock genuinely
        # starts when you lift it, and reading the setting here means the
        # slider takes effect on the very next egg you pick up.
        if prefs.settings['enable_ground_hatching']:
            timer = egg.get('hatch_timer', prefs.settings['hatch_time'])
        else:
            timer = prefs.settings['hatch_time']
        state.held.append({'hatch_timer': timer, 'next_warning': 0.0})
        sounds.fire_collect_sound()
        speech.say(f'Egg collected. {len(state.held)} of {player_carry_cap()} held.')
        state.eggs.remove(egg)
        if not egg.get('laid'):
            # Only wild eggs come back. A laid egg was a bird's gift, not
            # part of the wild supply, so taking it doesn't summon another.
            state.eggs.append(spawn_egg_far_from_player())
        log_counts('egg collected')
        return


# ============================================================================
# Basket lifecycle
# ============================================================================

def unfound_baskets_in_reach():
    """Unclaimed baskets close enough to be heard from where the player is.

    'In reach' is the audible radius rather than some larger planning
    distance on purpose: a basket you cannot hear may as well not exist, so
    it shouldn't count toward the world feeling stocked.
    """
    return [b for b in state.baskets
            if not b['discovered']
            and math.hypot(b['x'] - state.player['x'], b['y'] - state.player['y']) <= config.BASKET_AUDIBLE]


def forget_distant_baskets():
    """Drop unclaimed baskets the player has left far behind.

    ONLY undiscovered ones, and only well outside earshot. A discovered
    basket is part of the park — it holds eggs, it counts toward capacity,
    and you may be walking back to it. Removing one of those would delete
    eggs mid-hatch, from a place the player is deliberately returning to.
    """
    for b in list(state.baskets):
        if b['discovered']:
            continue
        if math.hypot(b['x'] - state.player['x'], b['y'] - state.player['y']) > config.BASKET_FORGET_DISTANCE:
            state.baskets.remove(b)
            log_counts('unfound basket forgotten, far behind')


def maybe_spawn_basket():
    """Keep unclaimed baskets available near wherever the player has walked.

    Called every frame; almost always a cheap count that does nothing. One
    basket per call at most, so wandering into empty territory fills it in
    over a few seconds rather than dropping a cluster at once.

    Placement is a random bearing at BASKET_SPAWN_MIN..MAX. Never closer
    than the minimum, so a basket can't appear underfoot — a chime starting
    up two metres away from a spot you already walked past reads as a bug,
    not as discovery.
    """
    if len(unfound_baskets_in_reach()) >= config.BASKET_TARGET_UNFOUND:
        return

    for _attempt in range(config.BASKET_PLACE_ATTEMPTS):
        angle = random.uniform(0.0, 2.0 * math.pi)
        dist = random.uniform(config.BASKET_SPAWN_MIN, config.BASKET_SPAWN_MAX)
        x = state.player['x'] + math.cos(angle) * dist
        y = state.player['y'] + math.sin(angle) * dist
        if any(math.hypot(b['x'] - x, b['y'] - y) < config.BASKET_MIN_SEPARATION
               for b in state.baskets):
            continue
        state.baskets.append({
            'x': x, 'y': y, 'z': 0.0,
            'freq_idx': len(state.baskets) % len(config.PENTATONIC_FREQS),
            'discovered': False,
            'eggs': [],
        })
        return
    # Ran out of attempts: the area is crowded. Nothing to report — the next
    # frame tries again, and by then the player has usually moved.


def try_discover_basket():
    """Walk within BASKET_DISCOVER_RADIUS of an undiscovered basket → discover."""
    for b in state.baskets:
        if b['discovered']:
            continue
        dx = b['x'] - state.player['x']
        dy = b['y'] - state.player['y']
        if math.hypot(dx, dy) <= config.BASKET_DISCOVER_RADIUS:
            b['discovered'] = True
            log_counts('basket found')
            sounds.fire_basket_discover(b)
            n = discovered_count()
            # No denominator any more. The total grows as you walk, so
            # "3 of 5" followed later by "4 of 7" reads as the goal moving
            # away from you — the opposite of what finding one means.
            speech.say(
                f'Basket discovered. {n} found. '
                f'Basket capacity {basket_cap()}. '
                f'Carry capacity {player_carry_cap()}.'
            )
            return


def try_deposit():
    """Bound to F. Drop everything from hand into the basket you're on."""
    on = current_basket()
    if on is None:
        sounds.fire_fumble()
        speech.say('Not standing on a basket.')
        return
    if not on['discovered']:
        # Standing on an undiscovered basket — discover first, then deposit
        # can be retried on next press.
        try_discover_basket()
        return
    if not state.held:
        sounds.fire_fumble()
        speech.say('No eggs to deposit.')
        return
    cap = basket_cap()
    room = cap - len(on['eggs'])
    if room <= 0:
        sounds.fire_basket_full_sound()
        speech.say(f'Basket full. Holds {cap}.')
        return
    n = min(room, len(state.held))
    for _ in range(n):
        on['eggs'].append(state.held.pop(0))
    sounds.fire_deposit_sound(on)
    log_counts(f'deposited {n}, basket now {len(on["eggs"])}')
    if n < len(state.held) + n:
        speech.say(f'Deposited {n}. Basket {len(on["eggs"])} of {cap}. {len(state.held)} still held.')
    else:
        speech.say(f'Deposited {n}. Basket {len(on["eggs"])} of {cap}.')


def current_basket():
    """Return the basket the player is standing on, or None."""
    for b in state.baskets:
        if math.hypot(b['x'] - state.player['x'], b['y'] - state.player['y']) <= config.BASKET_DEPOSIT_RADIUS:
            return b
    return None
