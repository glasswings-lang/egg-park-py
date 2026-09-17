# SPDX-License-Identifier: CC0-1.0
"""Eggs spread out around your baskets, and stay there.

Run: python tests/test_egg_spread.py

Plays the loop a real play log showed, 200 times: walk to the nearest egg,
pick it up, carry it back to the nearest basket. Measures after each pickup
where the eggs are. Runs the real game, safely: see _game_harness.py.
"""
import math
import random
import statistics

import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import check, finish, run_game


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False
    random.seed(1)
    G['start_game']()
    G['say'] = lambda text: None
    eggs, held, player, baskets = G['eggs'], G['held'], G['player'], G['baskets']
    for b in baskets:
        b['discovered'] = True
    dist = lambda a, b: math.hypot(a['x'] - b['x'], a['y'] - b['y'])
    to_home = lambda e: min(dist(e, b) for b in baskets if b['discovered'])

    closest_pairs, furthest_from_home, underfoot, in_earshot = [], [], [], []
    for n in range(200):
        held.clear()
        egg = min(eggs, key=lambda e: dist(e, player))
        player.update(x=egg['x'], y=egg['y'])
        G['try_collect_eggs']()
        underfoot.append(dist(eggs[-1], player))      # the egg that just appeared
        home = min(baskets, key=lambda b: dist(b, player))
        player.update(x=home['x'], y=home['y'])        # carry it back
        closest_pairs.append(min(dist(a, b) for i, a in enumerate(eggs) for b in eggs[i + 1:]))
        furthest_from_home.append(max(to_home(e) for e in eggs))
        in_earshot.append(sum(1 for e in eggs if dist(e, player) <= G['EGG_AUDIBLE']))
        if not any(dist(e, player) <= G['SCAN_RANGE'] for e in eggs):
            print(f'  nothing in scan range after pickup {n + 1}')

    print(f'  closest two eggs: median {statistics.median(closest_pairs):.0f} m, '
          f'worst {min(closest_pairs):.0f} m')
    print(f'  eggs you can hear calling from a basket: median '
          f'{statistics.median(in_earshot):.0f} of 4, fewest {min(in_earshot)}')
    sep = G['EGG_MIN_SEPARATION']
    kept_apart = sum(1 for d in closest_pairs if d >= sep) / len(closest_pairs)
    check(f'eggs kept {sep:.0f} m apart after {kept_apart:.0%} of pickups', kept_apart >= 0.95)
    check(f'never bunched (worst {min(closest_pairs):.0f} m)', min(closest_pairs) >= 15)
    check(f'no drift: after 200 pickups every egg is still within '
          f'{G["EGG_SPAWN_MAX"]:.0f} m of a found basket (worst {max(furthest_from_home):.0f} m)',
          max(furthest_from_home) <= G['EGG_SPAWN_MAX'] + 0.01)
    check(f'never appears underfoot (closest {min(underfoot):.0f} m)',
          min(underfoot) >= G['EGG_MIN_FROM_PLAYER'])
    silent = sum(1 for n in in_earshot if n == 0) / len(in_earshot)
    print(f'  back at a basket with no egg close enough to hear: {silent:.0%} of the time')
    scan_finds = all(any(dist(e, b) <= G['SCAN_RANGE'] for e in eggs) for b in baskets)
    check('a scan from any basket finds an egg', scan_finds)
    check('still four eggs', len(eggs) == G['NUM_EGGS'])

    print('the park grows, and eggs follow:')
    far = {'x': 600.0, 'y': 0.0, 'z': 0.0, 'freq_idx': 0, 'discovered': True, 'eggs': []}
    baskets.append(far)
    near_far = sum(1 for _ in range(100) if dist(G['spawn_egg_far_from_player'](), far) <= 90)
    check(f'a newly found distant basket gets eggs around it ({near_far} of 100)', 10 <= near_far <= 60)

    print('baskets appear inside earshot:')
    # A basket placed past earshot doesn't count as one waiting nearby, so
    # another would be made at once, and baskets pile up. Two hundred walks
    # into empty ground, spawning until the game says there are enough.
    extra = 0
    for trial in range(200):
        G['reset_world']()
        player.update(x=5000.0 + trial * 400.0, y=5000.0)
        for _ in range(20):
            G['maybe_spawn_basket']()
        extra += len(baskets) - 3 - G['BASKET_TARGET_UNFOUND']
    check(f'200 walks into empty ground: extra baskets beyond the {G["BASKET_TARGET_UNFOUND"]} wanted: {extra}',
          extra == 0)
    G['reset_world']()
    for b in baskets:
        b['discovered'] = True

    print('before any basket is found:')
    for b in baskets:
        b['discovered'] = False
    origin = {'x': 0.0, 'y': 0.0}
    spawns = [G['spawn_egg_far_from_player']() for _ in range(50)]
    check('eggs appear around where the park began',
          all(dist(e, origin) <= G['EGG_SPAWN_MAX'] + 0.01 for e in spawns))

    print('if every spot is at your feet:')
    G['EGG_MIN_FROM_PLAYER'] = 10_000.0
    player.update(x=0.0, y=0.0)
    e = G['spawn_egg_far_from_player']()
    check(f'still places an egg, well away ({dist(e, player):.0f} m)',
          dist(e, player) >= G['EGG_SPAWN_MAX'] - 0.01)


run_game(run_checks)
finish('test_egg_spread')
