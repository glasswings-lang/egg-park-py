# SPDX-License-Identifier: CC0-1.0
"""Eggs and baskets: capacity, spawning, picking up, finding, depositing."""
import math
import random
import time

from eggpark import chests, config, pad, prefs, scan, sounds, speech, state, tally

# ============================================================================
# Capacity helpers
# ============================================================================

def discovered_count():
    return sum(1 for b in state.baskets if b['discovered'])


def player_carry_cap():
    """Starts at CARRY_START; +1 per CARRY_BUMP_EVERY baskets discovered, plus
    every carry gift from chests."""
    return (config.CARRY_START + (discovered_count() // config.CARRY_BUMP_EVERY)
            + state.progress['carry_bonus'])


def collect_radius():
    """How far away you pick an egg up: COLLECT_RADIUS, plus NET_REACH_EACH per
    net chests have given you, up to NET_REACH_MAX."""
    return min(config.NET_REACH_MAX,
               config.COLLECT_RADIUS + config.NET_REACH_EACH * state.progress['nets'])


def chests_found():
    return sum(1 for c in state.chests if c['discovered'])


def storage_extra():
    """Added to every basket and chest: storage gifts, plus one per chest found."""
    return state.progress['storage_bonus'] + chests_found()


def basket_cap():
    """Each basket holds one egg per basket discovered, and never less than
    you can carry: one trip's worth must always fit in one basket. Chests'
    storage gifts, and finding chests at all, add on top."""
    return max(1, discovered_count(), player_carry_cap()) + storage_extra()


def chest_cap():
    """Chests start bigger and grow twice as fast per basket found, never hold
    less than you can carry, and get the same storage additions as baskets."""
    base = config.CHEST_START_CAPACITY + config.CHEST_CAPACITY_PER_BASKET * discovered_count()
    return max(base, player_carry_cap()) + storage_extra()


def log_counts(event):
    """A play-log line with every number capacity depends on, as it is now."""
    speech.log_event(
        f'{event} | found {discovered_count()} | chests {chests_found()} | carry {len(state.held)} of '
        f'{player_carry_cap()} | basket cap {basket_cap()} | chest cap {chest_cap()} | '
        f'gift bonuses {state.progress} | '
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
    anchors = ([(b['x'], b['y']) for b in state.baskets + state.chests if b['discovered']]
               or [(0.0, 0.0)])
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


def egg_grid_near(x, y, radius, cell):
    """A grid of only the eggs within `radius` of (x, y).

    A clutch lands within LAID_EGG_MAX of one basket, so the thousands of
    eggs elsewhere in the park cannot possibly be its neighbours — sorting
    them into cells for every clutch was most of the cost of laying one. A
    box test is the whole filter: cheap, and generous enough that no egg that
    could matter is left out.
    """
    grid = {}
    for egg in state.eggs:
        if -radius <= egg['x'] - x <= radius and -radius <= egg['y'] - y <= radius:
            grid_add(grid, cell, egg)
    return grid


def grid_add(grid, cell, egg):
    grid.setdefault((math.floor(egg['x'] / cell), math.floor(egg['y'] / cell)), []).append(egg)


def _crowded_within(x, y, separation):
    """True as soon as ONE egg is found within `separation` of (x, y).

    STOPS AT THE FIRST ONE, and that is the whole point. The caller asks "is
    this spot free?", and once a single egg that close has been found the answer
    cannot change. Without the early stop, a park where birds have laid for an
    hour has hundreds of eggs in every neighbourhood and nothing anywhere is far
    from its neighbours, so every one of the 40 attempts per egg measured every
    egg nearby and found no spot regardless. A profile of twenty seconds of
    walking in a 10,000-egg park: 43 million distance checks, a worst frame of
    3.6 seconds, and footsteps arriving whenever the game came back.
    """
    return state.eggs.any_within(x, y, separation)


def _gap_to_nearest(x, y, separation):
    """Exactly how far the nearest egg is, for choosing between cramped spots.

    A stopped-early answer is no good here: it is just the first neighbour that
    turned up. Using the cheap answer for this question is what made eggs bunch
    -- measured over 40 clutches, the gap between neighbouring eggs halved, from
    a median of 3.6 m to 1.4 m, and it was reported from play as everything
    being clustered together.
    """
    found = state.eggs.nearest(x, y, separation)
    if found is None:
        return float('inf')
    return math.hypot(found['x'] - x, found['y'] - y)


def _nearest_egg_within_reach(grid, cell, x, y, stop_at=0.0):
    """How close the nearest egg is, looking only at the 3x3 cells around
    (x, y). Exact whenever the true nearest egg is closer than `cell`.

    STOPS EARLY at `stop_at`. The caller asks one question — "is anything
    within the separation?" — and once an egg that close has been found, the
    answer cannot change, so there is no reason to keep measuring.

    This is not a micro-optimisation, it is the difference between a playable
    park and a stalling one. The grid keeps each look-up to nine cells, but in
    a park where birds have laid for an hour those nine cells hold hundreds of
    eggs each, and nothing anywhere is 8 m from its neighbours any more — so
    every one of the 40 attempts per egg scanned every egg nearby and found no
    spot regardless. A profile of twenty seconds of walking in a 10,000-egg
    park: 43 million distance checks, a worst frame of 3.6 seconds, and
    footsteps arriving whenever the game came back. With the early stop the
    dense case costs a handful of checks instead of hundreds.
    """
    cx, cy = math.floor(x / cell), math.floor(y / cell)
    best = float('inf')
    for gx in (cx - 1, cx, cx + 1):
        for gy in (cy - 1, cy, cy + 1):
            for e in grid.get((gx, gy), ()):
                d = math.hypot(e['x'] - x, e['y'] - y)
                if d < best:
                    best = d
                    if best <= stop_at:
                        return best
    return best


# How hard to look for a free spot.
#
# EGG_PLACE_ATTEMPTS tries is right for a park with room in it. In a park with
# forty thousand eggs there IS no spot thirty metres from every other egg, so all
# forty tries fail, every time, for every egg placed -- and eggs are placed about
# ten times a second, because ground eggs keep hatching and every wild one owes a
# replacement. Measured: five milliseconds a frame spent proving the impossible,
# out of the sixteen a frame has.
#
# So when the park stops having room, the search gets short. Sampling six cramped
# spots and taking the roomiest is barely different from sampling forty -- they
# are all cramped -- and the moment a free spot IS found, the full search comes
# back for the next egg. Nothing changes for a park that isn't full.
_SATURATED_AFTER = 3          # this many failed placements in a row
_SATURATED_ATTEMPTS = 6       # then try this many spots instead
_SATURATED_CANDIDATES = 4     # and compare this many of them exactly
_failures_in_a_row = 0


def placement_effort():
    """(attempts, fallback candidates) for the next egg placed."""
    if _failures_in_a_row >= _SATURATED_AFTER:
        return _SATURATED_ATTEMPTS, _SATURATED_CANDIDATES
    return config.EGG_PLACE_ATTEMPTS, config.EGG_FALLBACK_CANDIDATES


def _place_egg(anchors, dist_min, dist_max, separation, grid=None):
    """An egg dist_min..dist_max from a random anchor, `separation` from the
    other eggs and EGG_MIN_FROM_PLAYER from you, as far as possible.

    `grid` is accepted and ignored: state.eggs is itself a grid now (see
    eggpark/eggfield.py), so there is nothing to build. Building one here was
    the most expensive thing in a crowded park -- it walked every egg in the
    park, and one wild egg is replaced for every wild egg picked up, which with
    nets is hundreds in a single frame. That was 40,000 x 272 pieces of work in
    one frame, and it read as the game freezing.
    """
    del grid
    # TWO QUESTIONS, AND THEY NEED DIFFERENT ANSWERS.
    #
    # "Is this spot free?" only needs to find ONE egg inside the separation,
    # so it stops there — that is what keeps a full park playable.
    #
    # "Which of these cramped spots is roomiest?" needs the distance to the
    # NEAREST egg, and a stopped-early answer is just the first neighbour
    # that turned up. Using the cheap answer for the second question is what
    # made eggs bunch: in a park with no free spot left, the fallback is the
    # only thing choosing, and it was choosing on noise. Measured over 40
    # clutches, the gap between neighbouring eggs halved, from a median of
    # 3.6 m to 1.4 m, and it was reported from play as everything being
    # clustered together.
    #
    # So the tries are collected first, cheaply, and if none of them is free
    # the roomiest is picked from the first EGG_FALLBACK_CANDIDATES of them
    # using exact distances. Bounded work, and the spacing comes back.
    global _failures_in_a_row
    attempts, candidates = placement_effort()
    best, best_gap = None, -1.0
    tried = []
    for _attempt in range(attempts):
        ax, ay = random.choice(anchors)
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(dist_min, dist_max)
        x = ax + math.cos(angle) * dist
        y = ay + math.sin(angle) * dist
        if math.hypot(x - state.player['x'], y - state.player['y']) < config.EGG_MIN_FROM_PLAYER:
            continue
        if not _crowded_within(x, y, separation):
            best, best_gap = (x, y), separation
            _failures_in_a_row = 0
            break
        tried.append((x, y))
    else:
        _failures_in_a_row += 1
    if best is None and tried:
        for x, y in tried[:candidates]:
            gap = _gap_to_nearest(x, y, separation)   # exact
            if gap > best_gap:
                best, best_gap = (x, y), gap
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
    _refused_eggs.clear()
    state.birds.clear()
    # Baskets are REBUILT, not just reset: generated ones have to go, or a
    # new park inherits every basket the last one grew.
    state.baskets.clear()
    state.baskets.extend(dict(b, eggs=[]) for b in state.INITIAL_BASKETS)
    state.chests.clear()
    state.progress.update(carry_bonus=0, storage_bonus=0, nets=0)
    state.player.update({'x': 0.0, 'y': 0.0, 'z': 0.0, 'yaw': 0.0})
    _last_seen_counts.update(found=0, carry=0)
    forget_hands_full()
    tally.forget_all()
    pad.forget_run()
    from eggpark import chestlist      # late: chestlist imports this file
    chestlist.forget()
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


# "Hands full" is ONE message, however many eggs you walk past.
#
# It was once per egg, with a flag on each egg so standing on one couldn't
# repeat it. That held up while there were four eggs in the park. Birds lay
# clutches, nothing eats eggs, and a real park reached four thousand of them:
# walking with full hands then crossed a new egg every stride, each one a
# fresh egg with no flag on it, and a play log caught 204 spoken "Hands full"
# lines in a minute. With NVDA asleep — which is how the game is meant to be
# played — you cannot even interrupt them.
#
# So it is said once and then held back until something you did changes the
# situation: you deposit, or REFUSE_REPEAT_SECONDS pass. Being told your hands
# are full is worth one sentence. It is not worth a running commentary.
_last_hands_full_at = None

# The eggs currently carrying a 'refused' flag, so the flag can be cleared
# when you walk away from them without touching every egg in the park.
_refused_eggs = []


def _may_say_hands_full():
    global _last_hands_full_at
    now = time.monotonic()
    if (_last_hands_full_at is not None
            and now - _last_hands_full_at < config.REFUSE_REPEAT_SECONDS):
        return False
    _last_hands_full_at = now
    log_counts('egg refused, hands full')
    return True


def forget_hands_full():
    """Next full-handed egg may speak again. Called when you deposit: your
    hands just changed, so the message is news rather than nagging."""
    global _last_hands_full_at
    _last_hands_full_at = None


def try_collect_eggs():
    """Pick up every egg within collect_radius(), nearest first, up to carry cap.

    With no nets that radius is 2 m and it's one egg at a time, as it always
    was. Nets widen it, and then everything in reach comes up in one go, with
    one sound and one spoken line rather than a burst of each.
    """
    # The grid is rebuilt here if anything has changed the egg list behind its
    # back. One comparison, every frame, and then nothing downstream has to
    # wonder whether the cells are true.
    state.eggs.settle()
    if not prefs.settings['enable_pickup']:
        return
    reach = collect_radius()
    px, py = state.player['x'], state.player['y']
    room = player_carry_cap() - len(state.held)

    # Eggs you have walked away from may speak to you again. There are never many
    # of them, so they are measured one by one rather than by rebuilding the set
    # of everything in reach.
    if _refused_eggs:
        for egg in list(_refused_eggs):
            if math.hypot(egg['x'] - px, egg['y'] - py) > reach:
                egg.pop('refused', None)
                _refused_eggs.remove(egg)

    # NOTHING IS ASKED FOR BEYOND WHAT YOUR HANDS CAN HOLD.
    #
    # This is the one that made standing in a heap unplayable, and the keeper
    # found it by experiment: sit still in a dense patch and it stumbles, walk out
    # of it and it clears, make a new dense patch and it stumbles again. With
    # seven nets the reach is 16 metres, and in the crowded corner of a park that
    # circle holds about thirty thousand eggs. Measuring every one of them, every
    # frame, in order to pick up at most a handful, is work that grows with how
    # many eggs are standing around you -- which is exactly the shape of what they
    # described.
    #
    # One more than there is room for is all that is needed: it says something was
    # left behind, which is the only other thing this function has to know.
    if room <= 0:
        if state.eggs.any_within(px, py, reach) and _may_say_hands_full():
            sounds.fire_refuse_sound()
            speech.say(f'Hands full. {len(state.held)} eggs held.')
        return

    in_reach = state.eggs.nearest_many(px, py, reach, room + 1)
    if not in_reach:
        return

    collected = 0
    left_behind = []
    for _d, egg in in_reach:
        if len(state.held) >= player_carry_cap():
            left_behind.append(egg)
            continue
        # With ground hatching on, the egg has been counting down where it
        # lay, and it keeps what it has left: picking one up at the last
        # second must not wind it back to full.
        #
        # With it off, eggs on the ground never tick, so the clock genuinely
        # starts when you lift it, and reading the setting here means the
        # slider takes effect on the very next egg you pick up.
        #
        # next_warning is a per-egg countdown to the next warning chirp;
        # it only matters once hatch_timer drops below WARNING_WINDOW.
        if prefs.settings['enable_ground_hatching']:
            timer = egg.get('hatch_timer', prefs.settings['hatch_time'])
        else:
            timer = prefs.settings['hatch_time']
        state.held.append({'hatch_timer': timer, 'next_warning': 0.0})
        state.eggs.remove(egg)
        if not egg.get('laid'):
            # Only wild eggs come back. A laid egg was a bird's gift, not
            # part of the wild supply, so taking it doesn't summon another.
            state.eggs.append(spawn_egg_far_from_player())
        collected += 1
        log_counts('egg collected')

    # Hands full: told ONCE, then left alone. See _may_say_hands_full.
    for egg in left_behind:
        egg['refused'] = True
        if egg not in _refused_eggs:
            _refused_eggs.append(egg)
    say_full = left_behind and _may_say_hands_full()

    held = f'{len(state.held)} of {player_carry_cap()} held.'
    if collected:
        sounds.fire_collect_sound()
        line = ('Egg collected. ' if collected == 1 else f'Scooped {collected} eggs. ') + held
        if say_full:
            line += ' Hands full.'
        speech.say(line)
    elif say_full:
        sounds.fire_refuse_sound()
        speech.say(f'Hands full. {len(state.held)} eggs held.')


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
    """Bound to F. Drop everything from hand into the chest or basket you're on."""
    on, name, cap = chests.current_chest(), 'Chest', chest_cap()
    if on is None:
        on, name, cap = current_basket(), 'Basket', basket_cap()
    if on is None:
        sounds.fire_fumble()
        speech.say('Not standing on a basket or chest.')
        return
    if not on['discovered']:
        # Standing on an undiscovered one — discover first, then deposit
        # can be retried on next press.
        if name == 'Chest':
            chests.try_discover_chest()
        else:
            try_discover_basket()
        return
    if not state.held:
        sounds.fire_fumble()
        speech.say('No eggs to deposit.')
        return
    room = cap - len(on['eggs'])
    if room <= 0:
        sounds.fire_basket_full_sound()
        speech.say(f'{name} full. Holds {cap}.')
        return
    n = min(room, len(state.held))
    for _ in range(n):
        on['eggs'].append(state.held.pop(0))
    sounds.fire_deposit_sound(on)
    forget_hands_full()
    log_counts(f'deposited {n}, {name.lower()} now {len(on["eggs"])}')
    if n < len(state.held) + n:
        speech.say(f'Deposited {n}. {name} {len(on["eggs"])} of {cap}. {len(state.held)} still held.')
    else:
        speech.say(f'Deposited {n}. {name} {len(on["eggs"])} of {cap}.')


def current_basket():
    """Return the basket the player is standing on, or None."""
    for b in state.baskets:
        if math.hypot(b['x'] - state.player['x'], b['y'] - state.player['y']) <= config.BASKET_DEPOSIT_RADIUS:
            return b
    return None
