# SPDX-License-Identifier: CC0-1.0
"""A park with thousands of eggs and hundreds of birds still runs smoothly.

Where this came from: a real park reached 10,000 eggs and 231 birds, and
walking in it stuttered so badly that footsteps arrived in clumps. A profile
found two causes, both algorithmic rather than anything to do with Python:

  * egg placement measured every nearby egg on every one of its 40 attempts,
    even though it only ever needed to know whether ONE was too close. 43
    million distance checks in twenty seconds of walking; worst frame 3.6 s.
  * birds hatch in batches, so their laying timers line up, and a whole
    flock came due in the same frame: dozens of clutches placed at once,
    290 ms in one frame.

The timing checks here are deliberately loose — this runs on whatever
machine it runs on, and the failure being guarded against is a hundredfold,
not a few percent.

Run: python tests/test_big_park.py

Runs the real game, safely: see _game_harness.py.
"""
import math
import random
import time

import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import check, finish, run_game

from pyglet.window import key

EGGS = 12000
BIRDS = 250
WALK_SECONDS = 8


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False
    G['say'] = lambda text: None
    G['log_event'] = lambda text: None
    G['_play'] = lambda *a, **k: None
    settings = G['settings']
    player, eggs, birds, baskets = G['player'], G['eggs'], G['birds'], G['baskets']

    G['start_game']()
    settings['enable_ground_hatching'] = True
    settings['hatch_time'] = 180.0
    settings['lay_time'] = 30.0

    # A park shaped like the real one: eggs clustered around a few baskets,
    # which is what makes placement hard — a uniform scatter would not.
    random.seed(4)
    eggs.clear()
    for b in baskets:
        b['discovered'] = True
    homes = [(b['x'], b['y']) for b in baskets]
    for i in range(EGGS):
        hx, hy = homes[i % len(homes)]
        a = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, 60)
        eggs.append({'x': hx + math.cos(a) * r, 'y': hy + math.sin(a) * r, 'z': 0.0,
                     'freq_idx': i % 5, 'hatch_timer': 180.0, 'laid': True})
    birds.clear()
    for i in range(BIRDS):
        G['make_your_bird'](baskets[i % len(baskets)])
    player.update(x=0.0, y=0.0, yaw=0.0)
    print(f'{len(eggs)} eggs, {len(birds)} birds, {len(baskets)} baskets')

    print('holding W:')
    G['keys'].on_key_press(key.W, 0)
    update = G['update']
    times = []
    for _ in range(int(WALK_SECONDS * 60)):
        t0 = time.perf_counter()
        update(1 / 60)
        times.append((time.perf_counter() - t0) * 1000.0)
    G['keys'].on_key_release(key.W, 0)
    ordered = sorted(times)
    median = ordered[len(ordered) // 2]
    worst = ordered[-1]
    p99 = ordered[int(len(ordered) * 0.99)]
    budget = 1000 / 60
    print(f'  median {median:.2f} ms, 99th {p99:.2f} ms, worst {worst:.2f} ms '
          f'(a frame is {budget:.1f} ms)')
    check(f'a typical frame is well inside its budget ({median:.2f} ms)', median < budget / 2)
    check(f'and the worst frame is not a stall ({worst:.0f} ms)', worst < 150)
    spent = sum(times) / 1000.0
    check(f'{WALK_SECONDS} s of walking costs {spent:.1f} s of work, not more than it simulates',
          spent < WALK_SECONDS * 0.6)

    print('a whole flock coming due at once:')
    clutches = []
    real_lay = G['lay_clutch']
    G['lay_clutch'] = lambda bird: clutches.append(bird) or real_lay(bird)
    for bird in birds:
        bird['lay_timer'] = 0.0001               # every bird, this frame
    per_frame = []
    for _ in range(5):
        clutches.clear()
        G['tick_laying'](1 / 60)
        per_frame.append(len(clutches))
    cap = G['LAY_CLUTCHES_PER_FRAME']
    check(f'250 birds due together lay {per_frame} over five frames, never more than {cap}',
          max(per_frame) <= cap)
    still_due = sum(1 for b in birds if b['lay_timer'] <= 0)
    check(f'the rest are still owed their clutch, not skipped ({still_due} waiting)',
          still_due >= BIRDS - sum(per_frame) - 1)
    G['lay_clutch'] = real_lay

    print('placing an egg in a park with no room left:')
    # Every spot near a basket is taken, so every attempt fails and the
    # fallback is used. This is the case that used to scan thousands of eggs
    # per attempt.
    t0 = time.perf_counter()
    for _ in range(20):
        G['spawn_egg_far_from_player']()
    each = (time.perf_counter() - t0) * 1000 / 20
    check(f'each placement costs {each:.1f} ms, not hundreds', each < 25)


run_game(run_checks)
finish('test_big_park')
