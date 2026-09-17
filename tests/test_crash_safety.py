# SPDX-License-Identifier: CC0-1.0
"""A scan in a full park must not end the game, and a crash must leave a log.

The bug this is built around: Space pinged every egg within 200 m. After a few
clutches that was hundreds of sounds at once, the audio card ran out of
sources at 256 (measured on the machine it happened on), and the exception
closed the window with no message and no saved park.

Run: python tests/test_crash_safety.py

Runs the real game, safely: see _game_harness.py.
"""
import os
import sys

import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import CRASH_LOG, check, finish, run_game

import pyglet
from pyglet.window import key


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False
    spoken = []
    G['say'] = spoken.append
    P, eggs = G['player'], G['eggs']

    print('a scan in a park full of eggs:')
    G['start_game']()
    scheduled = []
    real_schedule = pyglet.clock.schedule_once
    pyglet.clock.schedule_once = lambda fn, delay, *a, **k: scheduled.append((fn, delay))
    eggs.clear()
    P.update(x=0.0, y=0.0)
    for i in range(400):
        eggs.append({'x': 3.0 + i * 0.4, 'y': 0.0, 'z': 0.0, 'freq_idx': i % 5,
                     'hatch_timer': 999.0, 'laid': True})
    G['try_scan']()
    pyglet.clock.schedule_once = real_schedule
    per_kind = G['SCAN_MAX_PINGS_PER_KIND']
    check(f'400 eggs in range: {len(scheduled)} pings, not 400',
          len(scheduled) <= per_kind + 2 * per_kind)      # eggs + baskets + chests
    check(f'the count spoken is still the true one ({spoken[-1]!r})',
          '403 items in range' in spoken[-1])
    check('and every ping still lands inside the sweep',
          all(0.0 <= delay <= G['SCAN_DURATION'] + 0.01 for _fn, delay in scheduled))

    print('what the pings themselves do:')
    played = []
    real_player = pyglet.media.Player

    class Refusing(real_player):
        def play(self):
            raise Exception('OpenAL Exception [40965: Out of Memory]: Failed to create source.')

    active = G['_active_players']
    active.clear()
    pyglet.media.Player = Refusing
    try:
        for _ in range(50):
            G['fire_scan_egg_ping'](eggs[0])
    except Exception as exc:
        check(f'a sound the card refuses does not reach the game: {exc!r}', False)
    else:
        check('a sound the card refuses is dropped, not raised', True)
    pyglet.media.Player = real_player
    check('and no dead players are left behind', not active)
    log = open(G['PLAY_LOG_FILE'], encoding='utf-8').read()
    check('the play log says it could not play', 'COULD NOT PLAY' in log)

    print('the most that can play at once:')
    active.clear()
    played.clear()

    class Counting(real_player):
        def play(self):
            played.append(1)

    pyglet.media.Player = Counting
    for _ in range(300):
        G['fire_scan_egg_ping'](eggs[0])
    pyglet.media.Player = real_player
    check(f'300 sounds asked for, {len(played)} played, capped at {G["MAX_VOICES"]}',
          len(played) == G['MAX_VOICES'] < 256)
    check('the play log says some were dropped', 'dropped a scan-egg-ping' in
          open(G['PLAY_LOG_FILE'], encoding='utf-8').read())
    active.clear()

    print('Space in a full park, for real, with nothing faked:')
    G['reset_world']()
    eggs.clear()
    for i in range(400):
        eggs.append({'x': 3.0 + i * 0.4, 'y': 0.0, 'z': 0.0, 'freq_idx': i % 5,
                     'hatch_timer': 999.0, 'laid': True})
    P.update(x=0.0, y=0.0)
    G['on_key_press'](key.SPACE, 0)
    for _ in range(int(4 * 60)):           # let the whole sweep play out
        G['update'](1 / 60)
    check('the game is still running', True)

    print('a crash leaves something to read:')
    # The hook also prints the traceback for anyone at a console. Silenced
    # here, or a test that passes looks like a test that blew up.
    sys.__excepthook__ = lambda *a: None
    if os.path.isfile(CRASH_LOG):
        os.remove(CRASH_LOG)
    G['CARRY_START'] = 1
    G['save_park']('before the crash')
    try:
        raise ValueError('a pretend crash, from the test')
    except ValueError as exc:
        G['_on_crash'](type(exc), exc, exc.__traceback__)
    written = open(CRASH_LOG, encoding='utf-8').read() if os.path.isfile(CRASH_LOG) else ''
    check('crash-log.txt exists and holds the traceback',
          'a pretend crash, from the test' in written and 'Traceback' in written)
    check('it names the file and line it happened in', 'test_crash_safety.py' in written)
    check(f'and the game says where to look ({spoken[-1]!r})',
          'crash log dot text' in spoken[-1])
    check('the play log records it too',
          'CRASH:' in open(G['PLAY_LOG_FILE'], encoding='utf-8').read())
    check('the park was saved on the way down', os.path.isfile(G['PARK_SAVE_FILE']))
    before = written
    try:
        raise ValueError('a second pretend crash')
    except ValueError as exc:
        G['_on_crash'](type(exc), exc, exc.__traceback__)
    after = open(CRASH_LOG, encoding='utf-8').read()
    check('a second crash is added, not written over the first',
          before in after and 'a second pretend crash' in after)


run_game(run_checks)
finish('test_crash_safety')
