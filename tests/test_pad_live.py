# SPDX-License-Identifier: CC0-1.0
"""Boot the game with a REAL controller, on pyglet's own event loop.

This is the one check that would have caught the crash that shipped: a pad
already plugged in reports its resting state the moment the game opens,
pyglet dispatches that, and a handler written to the wrong shape ends the
process before the menu finishes speaking. Every other pad check calls the
handlers itself, which only proves the handlers agree with the test.

Needs a controller plugged in. With none, it says so and passes: a machine
without a pad is not a broken machine, and this must not fail in CI or on
someone else's computer.

Run: python tests/test_pad_live.py

Runs the real game, safely: see _game_harness.py.
"""
import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import check, finish, run_game

import pyglet

REAL_RUN = pyglet.app.run              # before run_game swaps it out

SECONDS = 3


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False
    G['say'] = lambda text: None
    G['_play'] = lambda *a, **k: None

    if not G['connected']():
        print('  no controller plugged in, so nothing to check here.')
        return

    name = getattr(G['_controller'], 'name', '?')
    print(f'  a real pad is open: {name}')
    G['start_game']()
    G['player'].update(x=0.0, y=0.0, yaw=0.0)
    frames = [0]
    pyglet.clock.schedule_interval(lambda dt: frames.__setitem__(0, frames[0] + 1), 1 / 60)
    pyglet.clock.schedule_once(lambda dt: pyglet.app.exit(), SECONDS)
    # The real loop. A wrong handler signature raises out of here, exactly as
    # it did in play.
    REAL_RUN()
    check(f'the game survives {SECONDS} s with a live pad ({frames[0]} frames ran)',
          frames[0] > SECONDS * 30)
    drift = abs(G['player']['x']) + abs(G['player']['y']) + abs(G['player']['yaw'])
    check(f'and an untouched pad does not move you ({drift:.4f})', drift < 0.01)


run_game(run_checks)
finish('test_pad_live')
