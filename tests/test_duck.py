# SPDX-License-Identifier: CC0-1.0
"""The park steps back while the scan is talking.

Reported as: "I literally can't hear it under everything else in an active
park." No volume slider fixes that — turning the scan up turns the park up
with it, because the park is what is covering it. So the scan cues duck
everything else, including sounds already playing.

Run: python tests/test_duck.py

Runs the real game, safely: see _game_harness.py.
"""
import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import check, finish, run_game

from pyglet.window import key


class FakePlayer:
    """Stands in for a pyglet Player: only volume and position are touched."""

    def __init__(self):
        self.volume = 1.0
        self.position = (0.0, 0.0, 0.0)
        self.pitch = 1.0
        self.min_distance = 0.0
        self.max_distance = 0.0
        self.queued = None

    def queue(self, source):
        self.queued = source

    def push_handlers(self, **kw):
        pass

    def play(self):
        pass


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False
    G['say'] = lambda text: None
    settings = G['settings']
    settings['master_volume'] = 1.0
    settings['duck_level'] = 0.35
    G['start_game']()

    import pyglet
    real_player = pyglet.media.Player
    pyglet.media.Player = FakePlayer
    active = G['_active_players']

    def fire(name, *a, **kw):
        active.clear()
        G[name](*a, **kw)
        return next(iter(active)) if active else None

    print('with nothing scanning:')
    G['stop_ducking']()
    egg = {'x': 1.0, 'y': 0.0, 'z': 0.0, 'freq_idx': 0, 'hatch_timer': 99.0}
    call = fire('fire_egg_call', egg)
    plain = call.volume
    check(f'an egg call plays at its own level ({plain:.2f})', plain > 0)

    print('while a scan is answering:')
    G['duck_for']()
    ducked = fire('fire_egg_call', egg).volume
    check(f'the same call is pulled down to {ducked / plain:.0%} of it '
          f'(DUCK_LEVEL {G["duck_level"]():.0%})',
          abs(ducked / plain - G['duck_level']()) < 1e-6)
    scan_ping = fire('fire_scan_egg_ping', egg).volume
    G['stop_ducking']()
    scan_plain = fire('fire_scan_egg_ping', egg).volume
    check(f'but the scan itself is never ducked ({scan_ping:.2f} either way)',
          abs(scan_ping - scan_plain) < 1e-6)
    check('so the scan is louder than the park it is over, which is the point',
          scan_ping > ducked)

    print('sounds already playing come down too:')
    # This is the case that matters: the wash you are under at the moment you
    # press Space must not ride over the answer.
    G['stop_ducking']()
    active.clear()
    for _ in range(6):
        G['fire_egg_call'](egg)
    G['fire_bird_ambient_at'](position=(2.0, 0.0, 0.0))
    before = sorted(p.volume for p in active)
    G['fire_scan_start']()                    # a scan cue: ducks everything
    after = sorted(p.volume for p in active if getattr(p, '_eggpark_category', '')
                   not in G['DUCKING_CATEGORIES'])
    check(f'{len(after)} sounds already playing were pulled down',
          len(after) == len(before) and all(a < b for a, b in zip(after, before)))

    print('and it lifts again:')
    G['stop_ducking']()
    G['update_listener']()
    up = sorted(p.volume for p in active if getattr(p, '_eggpark_category', '')
                not in G['DUCKING_CATEGORIES'])
    check('back to where they were, with no drift',
          all(abs(a - b) < 1e-6 for a, b in zip(up, before)))

    print('the hold, and what renews it:')
    G['stop_ducking']()
    check('nothing scanning: no duck', G['duck_factor']('egg-call') == 1.0)
    G['duck_for'](0.05)
    check('a scan cue ducks', G['duck_factor']('egg-call') == G['duck_level']())
    import time
    time.sleep(0.08)
    check('and it lifts on its own once the hold runs out',
          G['duck_factor']('egg-call') == 1.0)
    G['duck_for'](0.05)
    G['duck_for'](G['DUCK_HOLD'])
    check('a later cue renews the hold rather than shortening it',
          G['duck_factor']('egg-call') == G['duck_level']())

    print('a guide keeps the park down while it leads you, and no longer:')
    G['stop_ducking']()
    G['eggs'].clear()
    target = {'x': 0.0, 'y': 30.0, 'z': 0.0, 'freq_idx': 0, 'hatch_timer': 999.0}
    G['eggs'].append(target)
    G['player'].update(x=0.0, y=0.0, yaw=1.5707963)
    G['on_key_press'](key.SPACE, 0)
    check('pressing Space ducks the park', G['duck_factor']('egg-call') == G['duck_level']())
    G['stop_scan_guide']()
    check('and dropping the guide lets it straight back up',
          G['duck_factor']('egg-call') == 1.0)

    pyglet.media.Player = real_player
    active.clear()


run_game(run_checks)
finish('test_duck')
