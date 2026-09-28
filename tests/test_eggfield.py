# SPDX-License-Identifier: CC0-1.0
"""The egg grid: is it always true, and does it actually make a crowded park cheap?

Run: python tests/test_eggfield.py

No window, no audio, no desktop switch — this is arithmetic. It builds a park the
shape of the real one that started all this (38,592 eggs, 23,100 of them inside
one 25-metre square) and times the three places that used to walk the whole list.
"""
import math
import os
import random
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from eggpark.eggfield import CELL, TICK_SLICES, EggField  # noqa: E402

failures = []


def check(label, ok):
    print(('  ok   ' if ok else '  FAIL ') + label)
    if not ok:
        failures.append(label)


def egg(x, y, note=0):
    return {'x': float(x), 'y': float(y), 'z': 0.0, 'freq_idx': note,
            'hatch_timer': 100.0}


def slow_near(eggs, x, y, radius):
    """What the answer should be, worked out the expensive way."""
    return [e for e in eggs
            if math.hypot(e['x'] - x, e['y'] - y) <= radius]


def main():
    print('the egg grid')

    # ── it is a list ─────────────────────────────────────────────────────────
    f = EggField([egg(1, 1), egg(2, 2)])
    check('it is a list and knows its length', isinstance(f, list) and len(f) == 2)
    check('it iterates like a list', [e['x'] for e in f] == [1.0, 2.0])
    f.append(egg(3, 3))
    f.extend([egg(4, 4), egg(5, 5)])
    check('append and extend both work', len(f) == 5 and f.check())
    f.remove(f[0])
    check('remove works and keeps the grid true', len(f) == 4 and f.check())
    f.clear()
    check('clear empties both', len(f) == 0 and f.cell_count() == 0 and f.check())

    # ── identical eggs in the same spot ──────────────────────────────────────
    # A crowded park has plenty of these, and they are equal as dictionaries.
    f = EggField()
    twins = [egg(10, 10), egg(10, 10), egg(10, 10)]
    f.extend(twins)
    f.remove(twins[1])
    check('removing one of three identical eggs takes that exact one',
          len(f) == 2 and all(e is not twins[1] for e in f) and f.check())

    # ── the answer matches the slow way, everywhere ──────────────────────────
    random.seed(7)
    scattered = EggField(egg(random.uniform(-300, 300), random.uniform(-300, 300))
                         for _ in range(4000))
    worst = 0
    for _ in range(200):
        px, py = random.uniform(-350, 350), random.uniform(-350, 350)
        radius = random.choice((2.0, 8.0, 25.0, 80.0, 200.0))
        want = slow_near(scattered, px, py, radius)
        got = [e for e in scattered.near(px, py, radius)
               if math.hypot(e['x'] - px, e['y'] - py) <= radius]
        if len(want) != len(got) or {id(e) for e in want} != {id(e) for e in got}:
            worst += 1
    check('200 random questions, every radius: the grid agrees with the slow way',
          worst == 0)

    # eggs exactly on a cell edge belong to exactly one cell and are still found
    edge = EggField([egg(CELL, CELL), egg(-CELL, -CELL), egg(0, 0)])
    found = [e for e in edge.near(CELL, CELL, 0.5)
             if math.hypot(e['x'] - CELL, e['y'] - CELL) <= 0.5]
    check('an egg on a cell boundary is still found',
          len(found) == 1 and found[0]['x'] == CELL and edge.check())

    # ── the guard repairs anything that gets past the methods ────────────────
    sneaky = EggField([egg(1, 1), egg(2, 2)])
    list.append(sneaky, egg(500, 500))          # straight past the override
    check('a change made behind its back is noticed', not sneaky.check())
    check('and settle() repairs it', sneaky.settle() and sneaky.check())
    check('settle() on a healthy field does nothing', not sneaky.settle())

    # ── a park the shape of the real one ─────────────────────────────────────
    random.seed(11)
    heap = EggField()
    # 23,100 in one 25 m square, the way baskets and birds actually pile them up.
    # The 25 is the real park's crowded cell, not this file's cell size: those are
    # different numbers and tying them together once made this test build a heap
    # four metres across and then wonder why no grid could help.
    HEAP_SIDE = 25.0
    for _ in range(23100):
        heap.append(egg(225 + random.uniform(0, HEAP_SIDE),
                        -175 + random.uniform(0, HEAP_SIDE)))
    # the rest spread over a few hundred metres
    for _ in range(38592 - 23100):
        heap.append(egg(random.uniform(-500, 800), random.uniform(-600, 400)))
    check(f'a park of {len(heap)} eggs in {heap.cell_count()} cells is consistent',
          len(heap) == 38592 and heap.check())

    px, py = 225 + HEAP_SIDE / 2, -175 + HEAP_SIDE / 2   # standing in the heap

    def timed(fn, rounds=20):
        got = []
        for _ in range(rounds):
            t0 = time.perf_counter()
            fn()
            got.append((time.perf_counter() - t0) * 1000)
        return statistics.median(got)

    reach = 2.0
    whole_list = timed(lambda: [e for e in heap
                               if abs(e['x'] - px) <= reach and abs(e['y'] - py) <= reach])
    with_grid = timed(lambda: [e for e in heap.near(px, py, reach)
                              if abs(e['x'] - px) <= reach and abs(e['y'] - py) <= reach])
    print(f'  picking up what is in reach, standing in the heap:')
    print(f'    whole list {whole_list:7.2f}ms   grid {with_grid:7.2f}ms   '
          f'{whole_list / max(with_grid, 1e-6):.0f}x faster')
    check('a frame of pickup work is well under a 60fps frame (16.7ms)',
          with_grid < 4.0)
    check('and it is at least four times faster than walking the list',
          with_grid * 4 < whole_list)

    audible = 80.0
    whole_list = timed(lambda: min((math.hypot(e['x'] - px, e['y'] - py) for e in heap),
                                   default=0.0))
    with_grid = timed(lambda: heap.nearest(px, py, audible))
    print(f'  choosing which egg calls, within {audible:g} m:')
    print(f'    whole list {whole_list:7.2f}ms   grid {with_grid:7.4f}ms   '
          f'{whole_list / max(with_grid, 1e-6):.0f}x faster')
    check('choosing an egg call is now a fraction of a millisecond',
          with_grid < 0.5)

    # and it must be the right egg, not merely a quick one
    wrong = 0
    for _ in range(50):
        qx = px + random.uniform(-200, 200)
        qy = py + random.uniform(-200, 200)
        by_grid = heap.nearest(qx, qy, audible)
        slow = slow_near(heap, qx, qy, audible)
        want = min(slow, key=lambda e: math.hypot(e['x'] - qx, e['y'] - qy),
                   default=None)
        if (by_grid is None) != (want is None):
            wrong += 1
        elif by_grid is not None:
            a = math.hypot(by_grid['x'] - qx, by_grid['y'] - qy)
            b = math.hypot(want['x'] - qx, want['y'] - qy)
            if abs(a - b) > 1e-9:
                wrong += 1
    check('and it is the genuinely nearest egg, checked against the slow way '
          '50 times', wrong == 0)

    # ── removing a scoop's worth, which is what nets do in one frame ─────────
    # The first version of the field searched the list for each egg removed. At
    # this size that cost 0.78 ms each, so one scoop of 272 eggs froze the game
    # for about a fifth of a second -- worse than what it replaced.
    victims = [heap[len(heap) // 2 + i] for i in range(272)]
    t0 = time.perf_counter()
    for doomed in victims:
        heap.remove(doomed)
    scoop = (time.perf_counter() - t0) * 1000
    print(f'  removing a scoop of 272 eggs from {len(heap) + 272}: {scoop:.2f}ms')
    check('a scoop of 272 removals costs well under one frame', scoop < 8.0)
    check('and the field is still consistent afterwards',
          len(heap) == 38592 - 272 and heap.check())
    check('every removed egg is really gone',
          all(all(e is not v for e in heap.near(v['x'], v['y'], 0.1))
              for v in victims[:20]))

    # ── the ticking slices cover everything, exactly once ───────────────────
    field = EggField([egg(i * 3, 0) for i in range(97)])
    dt = 1 / 60
    seen = []
    steps = set()
    for _ in range(TICK_SLICES):
        part, step = field.ticking(dt)
        steps.add(round(step, 9))
        seen.extend(id(e) for e in part)
    check(f'{TICK_SLICES} frames cover all 97 eggs exactly once',
          sorted(seen) == sorted(id(e) for e in field))
    check(f'and each frame advances its share by {TICK_SLICES} times the step',
          steps == {round(dt * TICK_SLICES, 9)})
    whole, step = field.ticking(1.0)
    check('a long step reaches every egg with the real step, not a share of it',
          len(whole) == len(field) and step == 1.0)
    empty = EggField()
    part, step = empty.ticking(dt)
    check('an empty park asks for nothing', list(part) == [] and step == dt)

    print()
    if failures:
        print(f'test_eggfield: {len(failures)} FAILED')
        for f_ in failures:
            print('  - ' + f_)
        return 1
    print('test_eggfield: all good')
    return 0


if __name__ == '__main__':
    sys.exit(main())
