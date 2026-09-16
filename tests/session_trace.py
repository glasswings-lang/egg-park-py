# SPDX-License-Identifier: CC0-1.0
"""Record a long scripted session, to prove a rearrangement changed nothing.

    python tests/session_trace.py <game folder> <trace file>

Run it on two copies of the game (say, the last commit and your working
copy), then compare the two trace files. Same script, same random seed,
same fake clock: copies that behave identically write identical traces.

Every spoken line and every sound played (category, position, volume,
pitch) goes in the trace, with snapshots of the park along the way and the
saved park at the end. The session goes through the menu, settings, the
sound test, every park key, a long stretch of walking, running and scanning,
and the rarer moments on purpose: full hands, a full basket, eggs hatching
in hand, nowhere with room.

Written to check the 2026-09-16 split of main.py into eggpark/: the old and
new games wrote the same 24,151 lines. Not a pass/fail test; a tool for the
next time code moves around without meant to change what it does.
"""
import json
import math
import os
import random
import sys
import time

ROOT, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(ROOT, 'tests'))

fake_now = [1000.0]
time.monotonic = lambda: fake_now[0]
random.seed(12345)

import _game_harness  # noqa: E402
from _game_harness import run_game  # noqa: E402
from pyglet.window import key  # noqa: E402

trace = []


def r(v):
    return round(v, 3) if isinstance(v, float) else v


def checks(G):
    G['write_sounds_template'] = lambda *a, **k: False
    G['save_settings'] = lambda: trace.append('settings saved')

    def fake_play(source, *, position=None, volume=1.0, category=None,
                  min_distance=None, max_distance=None, pitch=1.0):
        pos = None if position is None else tuple(round(p, 2) for p in position)
        trace.append(f'play {category} pos={pos} vol={volume:.3f} pitch={pitch:.3f} '
                     f'min={min_distance} max={max_distance}')
    G['_play'] = fake_play
    G['say'] = lambda text: trace.append(f'say {text}')
    G['pyglet'].clock.schedule_once = lambda fn, delay, *a, **k: trace.append(f'scheduled {delay:.3f}')
    G['pyglet'].app.exit = lambda: trace.append('app exit')
    keys = G['keys']

    def press(sym, mods=0):
        trace.append(f'-- press {key.symbol_string(sym)}')
        res = G['on_key_press'](sym, mods)
        trace.append(f'   handled={res}')

    def frames(n, dt=1 / 60):
        for _ in range(n):
            fake_now[0] += dt
            G['update'](dt)

    def snapshot(label):
        p = G['player']
        trace.append(
            f'== {label}: player=({p["x"]:.2f},{p["y"]:.2f},{p["yaw"]:.3f}) '
            f'held={len(G["held"])} eggs={[(round(e["x"],1), round(e["y"],1)) for e in G["eggs"]]} '
            f'baskets={[(round(b["x"],1), round(b["y"],1), b["discovered"], len(b["eggs"])) for b in G["baskets"]]} '
            f'birds={len(G["birds"])} found={G["discovered_count"]()} cap={G["player_carry_cap"]()}/{G["basket_cap"]()}')

    # ---- main menu, settings, sound test, controls
    for sym in (key.DOWN, key.DOWN, key.UP, key.RETURN):      # Settings
        press(sym)
    for sym in (key.DOWN, key.RIGHT, key.RIGHT, key.LEFT, key.DOWN, key.SPACE,
                key.UP, key.UP, key.LEFT, key.RETURN):
        press(sym)
    press(key.ESCAPE)                                          # back to menu
    for sym in (key.DOWN, key.DOWN, key.RETURN):               # Sound test
        press(sym)
    for sym in (key.DOWN, key.SPACE, key.RETURN, key.DOWN, key.DOWN, key.S, key.SPACE, key.S,
                key.E, key.UP):
        press(sym)
    press(key.ESCAPE)
    for sym in (key.DOWN, key.DOWN, key.DOWN, key.RETURN):     # Controls
        press(sym)
    press(key.ESCAPE)                                          # Escape on first menu
    for sym in (key.UP, key.UP, key.UP, key.UP, key.UP):
        press(sym)
    G['_main_menu_focus'] = 0
    press(key.RETURN)                                          # Walk in the park
    snapshot('park started')

    # ---- in the park: every key
    G['settings']['hatch_time'] = 25.0
    for sym in (key.H, key.P, key.SPACE, key.B, key.F, key.BRACKETLEFT, key.BRACKETRIGHT,
                key.R, key.SLASH):
        press(sym)
        frames(30)
    press(key.O)
    press(key.DOWN)
    press(key.ESCAPE)
    press(key.ESCAPE)                                          # to menu
    press(key.RETURN)                                          # back to park
    snapshot('after keys')

    # ---- scripted play: walk, turn, run, scan, and go to things
    rng = random.Random(99)
    for step in range(400):
        choice = rng.random()
        if choice < 0.25:
            target = min(G['eggs'], key=lambda e: math.hypot(e['x'] - G['player']['x'], e['y'] - G['player']['y']))
            G['player']['yaw'] = math.atan2(target['y'] - G['player']['y'], target['x'] - G['player']['x'])
        elif choice < 0.45:
            found = [b for b in G['baskets']] or G['baskets']
            target = min(found, key=lambda b: math.hypot(b['x'] - G['player']['x'], b['y'] - G['player']['y']))
            G['player']['yaw'] = math.atan2(target['y'] - G['player']['y'], target['x'] - G['player']['x'])
        held_keys = []
        if rng.random() < 0.8:
            held_keys.append(key.W)
        if rng.random() < 0.3:
            held_keys.append(key.LSHIFT)
        if rng.random() < 0.15:
            held_keys.append(rng.choice([key.Q, key.E, key.A, key.D]))
        for k in held_keys:
            keys.on_key_press(k, 0)
        frames(rng.randint(10, 90))
        for k in held_keys:
            keys.on_key_release(k, 0)
        roll = rng.random()
        if roll < 0.1:
            press(key.SPACE)
        elif roll < 0.18:
            press(key.B)
        elif roll < 0.3:
            press(key.F)
        elif roll < 0.33:
            press(key.P)
        if step % 25 == 0:
            snapshot(f'step {step}')
        if step % 50 == 0:
            G['player'].update(x=G['baskets'][0]['x'], y=G['baskets'][0]['y'])
            frames(2)
            press(key.F)
    frames(60 * 40)                                            # let things hatch
    snapshot('after hatching')

    # ---- the rarer moments, reached on purpose
    P, E, B = G['player'], G['eggs'], G['baskets']
    for b in list(B)[:6]:                                      # find several baskets
        P.update(x=b['x'], y=b['y'])
        keys.on_key_press(key.W, 0)
        frames(20)                                              # footsteps on a basket
        keys.on_key_release(key.W, 0)
        P.update(x=b['x'], y=b['y'])
        frames(2)
    snapshot('found baskets')
    G['settings']['enable_hand_hatching'] = True
    G['settings']['hatch_time'] = 6.0
    for _ in range(G['player_carry_cap']() + 1):               # fill hands, then refuse
        egg = E[0]
        P.update(x=egg['x'], y=egg['y'])
        frames(3)
    press(key.SPACE)
    frames(60 * 8)                                              # held eggs hatch and fly off
    for _ in range(12):                                         # fill one basket to the brim
        egg = E[0]
        P.update(x=egg['x'], y=egg['y'])
        frames(2)
        P.update(x=B[0]['x'], y=B[0]['y'])
        frames(2)
        press(key.F)
    for b in B:
        b['discovered'] = True
        b['eggs'] = [{'hatch_timer': 999.0, 'next_warning': 0.0}] * 999
    press(key.B)                                                # nothing with room
    frames(60 * 10)
    snapshot('rare moments')

    # ---- saving, new park, quitting
    G['save_park']('equivalence')
    with open(G['PARK_SAVE_FILE'], encoding='utf-8') as f:
        saved = json.load(f)
    trace.append('saved park: ' + json.dumps(saved, sort_keys=True, default=r))
    press(key.ESCAPE)
    press(key.DOWN)
    press(key.RETURN)
    press(key.RETURN)                                          # confirm new park
    snapshot('new park')
    G['quit_game']()


run_game(checks)
with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(trace))
print(f'{len(trace)} trace lines')
