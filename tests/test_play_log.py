# SPDX-License-Identifier: CC0-1.0
"""The play log records what the game said and the numbers behind it.

Run: python tests/test_play_log.py

Runs the real game, safely: see _game_harness.py.
"""
import math
import os

import _game_harness
from _game_harness import check, finish, run_game

REAL_LOG = os.path.join(_game_harness.ROOT, 'play-log.txt')
real_log_before = os.path.getmtime(REAL_LOG) if os.path.isfile(REAL_LOG) else None


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False
    G['start_game']()
    p = G['player']
    for _ in range(3):
        b = next(b for b in G['baskets'] if not b['discovered'])
        p.update(x=b['x'], y=b['y'])
        G['update'](1 / 60)
    egg = G['eggs'][0]
    p.update(x=egg['x'], y=egg['y'])
    G['update'](1 / 60)
    G['baskets'][0]['discovered'] = False      # something that should never happen
    G['update'](1 / 60)

    lines = open(_game_harness.PLAY_LOG, encoding='utf-8').read().splitlines()
    found = [l for l in lines if 'basket found' in l]
    check(f'every find logged ({len(found)} of 3)', len(found) == 3)
    check('third find shows carry cap 2', 'found 3 | carry 0 of 2' in found[-1])
    check('spoken lines are logged', any('said: Basket discovered. 3 found.' in l for l in lines))
    check('pickup logged with its numbers', any('egg collected | found 3 | carry 1 of 2' in l for l in lines))
    check('a find going missing is flagged', any('UNEXPECTED DROP' in l for l in lines))
    for l in lines[-4:]:
        print('    ' + l)


run_game(run_checks)
real_log_after = os.path.getmtime(REAL_LOG) if os.path.isfile(REAL_LOG) else None
check('the real play-log.txt was not touched', real_log_before == real_log_after)
finish('test_play_log')
