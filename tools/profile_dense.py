# SPDX-License-Identifier: CC0-1.0
"""Where does a frame actually go, standing in the crowded part of a real park?

    python tools/profile_dense.py [path-to-park.json]

Boots the real game on a hidden desktop with the silent audio driver, loads a copy
of a saved park (the keeper's own by default), puts the player in whichever
25-metre square holds the most eggs, and then profiles 300 frames and one scan.

It prints the functions a frame really spends its time in, worst first. This
exists because guessing was wrong twice: the fix that helped in a synthetic test
made the real game worse, and only the play log and a profile showed it.

Nothing is heard and nothing touches the real save: the park is copied first and
every write goes to a scratch folder.
"""
import cProfile
import os
import pstats
import shutil
import statistics
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'tests'))
sys.path.insert(0, ROOT)

SOURCE_PARK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'park.json')
if not os.path.isfile(SOURCE_PARK):
    print(f'no park to profile: {SOURCE_PARK}')
    sys.exit(2)

# The harness reads these at import, so the park copy has to be in place first.
SCRATCH = tempfile.mkdtemp(prefix='eggpark-profile-')
os.environ['EGG_PARK_TEST_DIR'] = SCRATCH
shutil.copy(SOURCE_PARK, os.path.join(SCRATCH, 'park.json'))

import _game_harness  # noqa: E402,F401  (hidden desktop, silence; must come first)
from _game_harness import run_game  # noqa: E402

FRAMES = 300
DT = 1 / 60


def densest_cell(eggs, side=25.0):
    cells = {}
    for egg in eggs:
        key = (int(egg['x'] // side), int(egg['y'] // side))
        cells[key] = cells.get(key, 0) + 1
    if not cells:
        return (0.0, 0.0), 0
    (cx, cy), n = max(cells.items(), key=lambda kv: kv[1])
    return (cx * side + side / 2, cy * side + side / 2), n


def checks(G):
    # update() does nothing at all while a menu is open, so the game has to be
    # out of the menu or the frame numbers are a measurement of nothing. A first
    # version of this file missed that and reported 0.00ms a frame.
    G['_in_main_menu'] = False
    G['_game_started'] = True
    G['_in_settings'] = False
    G['_in_sound_test'] = False
    G['load_park']()
    eggs = G['eggs']
    print(f'park: {len(eggs)} eggs, {len(G["birds"])} birds, '
          f'{len(G["baskets"])} baskets, {len(G["chests"])} chests')

    (px, py), n = densest_cell(eggs)
    print(f'standing where the eggs are: {n} of them in one 25 m square, '
          f'at ({px:.0f}, {py:.0f})')
    G['player'].update(x=px, y=py)
    G['update_listener']()

    update = G['update']

    # Warm once so first-call costs don't land in the numbers.
    update(DT)

    spent = []
    for _ in range(FRAMES):
        started = time.perf_counter()
        update(DT)
        spent.append((time.perf_counter() - started) * 1000)
    spent.sort()
    print(f'\n{FRAMES} frames:')
    print(f'  median {statistics.median(spent):.2f}ms   '
          f'90th {spent[int(len(spent) * 0.9)]:.2f}ms   '
          f'worst {spent[-1]:.2f}ms')
    print(f'  a frame at 60 per second has 16.7ms to spend')

    print('\none scan (the Space key):')
    started = time.perf_counter()
    G['try_scan']()
    print(f'  {(time.perf_counter() - started) * 1000:.1f}ms')

    print('\nwhere 60 frames go, worst first:')
    profile = cProfile.Profile()
    profile.enable()
    for _ in range(60):
        update(DT)
    profile.disable()
    stats = pstats.Stats(profile)
    stats.sort_stats('tottime')
    stats.stream = sys.stdout
    stats.print_stats(14)

    print('\nand where one scan goes:')
    profile = cProfile.Profile()
    profile.enable()
    G['try_scan']()
    profile.disable()
    stats = pstats.Stats(profile)
    stats.sort_stats('tottime')
    stats.stream = sys.stdout
    stats.print_stats(10)


try:
    run_game(checks)
finally:
    shutil.rmtree(SCRATCH, ignore_errors=True)
