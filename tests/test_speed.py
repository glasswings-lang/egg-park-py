# SPDX-License-Identifier: CC0-1.0
"""Speed you can hear: acceleration, and wind that rises with it.

Running used to be a number changing. Speed showed up only as footstep
cadence, and barely — a running stride is longer, so five metres a second
sounded much like two. It was reported as "running? that's not running".

Two changes answer that, and these are the checks for both: speed now BUILDS
instead of snapping, and a wind loop follows the speed you actually have.

Run: python tests/test_speed.py

Runs the real game, safely: see _game_harness.py.
"""
import math

import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import check, finish, run_game

from pyglet.window import key


class FakeWind:
    """Stands in for the wind player: only volume, pitch and playing matter."""

    def __init__(self):
        self.volume = 0.0
        self.pitch = 1.0
        self.position = (0.0, 0.0, 0.0)
        self.loop = False
        self.playing = False
        self.min_distance = self.max_distance = 0.0

    def queue(self, source):
        pass

    def play(self):
        self.playing = True

    def pause(self):
        self.playing = False


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False
    G['say'] = lambda text: None
    G['_play'] = lambda *a, **k: None
    settings = G['settings']
    settings['master_volume'] = 1.0
    settings['vol_wind'] = 1.0
    settings['walk_speed'] = 2.0
    settings['run_speed'] = 5.0
    settings['enable_wind'] = True
    player, keys = G['player'], G['keys']
    G['start_game']()
    G['eggs'].clear()

    def frames(n):
        for _ in range(n):
            G['update'](1 / 60)

    def hold(k, seconds, *also):
        for extra in (k,) + also:
            keys.on_key_press(extra, 0)
        frames(int(seconds * 60))

    def let_go(*ks):
        for k in ks:
            keys.on_key_release(k, 0)

    print('speed builds instead of snapping:')
    player.update(x=0.0, y=0.0, yaw=0.0)
    hold(key.W, 0.1)
    early = G['_speed']
    frames(int(0.9 * 60))
    settled = G['_speed']
    check(f'a tenth of a second in you are still speeding up ({early:.2f} m/s '
          f'of {settled:.2f})', 0.0 < early < settled * 0.8)
    check(f'and by a second you are at the walk speed ({settled:.2f})',
          abs(settled - 2.0) < 0.02)
    reach = G['ACCELERATION']
    check(f'which takes about {2.0 / reach:.2f} s at {reach:g} m/s/s, as configured',
          2.0 / reach < 0.5)

    print('and running builds on top of that:')
    keys.on_key_press(key.LSHIFT, 0)
    speeds = []
    for _ in range(45):
        G['update'](1 / 60)
        speeds.append(G['_speed'])
    check(f'the first frames after Shift are between the two speeds '
          f'({speeds[3]:.2f} m/s)', 2.0 < speeds[3] < 5.0)
    check(f'and it arrives at the run speed ({speeds[-1]:.2f})', abs(speeds[-1] - 5.0) < 0.05)
    climbing = all(b >= a - 1e-9 for a, b in zip(speeds, speeds[1:]))
    check('speed only ever climbs on the way up, never jumps about', climbing)

    print('letting go coasts to a stop, rather than stopping dead:')
    let_go(key.W, key.LSHIFT)
    was = player['x']
    frames(int(1.0 * 60))
    coast = player['x'] - was
    check(f'you carry on for {coast:.2f} m and then stop '
          f'({G["_speed"]:.2f} m/s left)', 0.3 < coast < 3.0 and G['_speed'] == 0.0)

    print('the wind follows the speed you actually have:')
    wind = FakeWind()
    import pyglet
    real_player = pyglet.media.Player
    pyglet.media.Player = lambda: wind
    G['_wind_player'] = None
    G['_wind_level'] = 0.0

    def wind_after(seconds, *held):
        for k in held:
            keys.on_key_press(k, 0)
        frames(int(seconds * 60))
        return wind.volume, wind.pitch, G['wind_level']()

    at_rest = wind_after(0.5)
    check(f'standing still: silent, and not even playing ({at_rest[0]:.4f})',
          at_rest[0] == 0.0 and not wind.playing)
    walking = wind_after(1.5, key.W)
    check(f'walking: you can hear it ({walking[0]:.4f}, level {walking[2]:.2f})',
          walking[0] > 0.0 and wind.playing)
    running = wind_after(1.5, key.LSHIFT)
    check(f'running: louder than walking ({running[0]:.4f} against {walking[0]:.4f})',
          running[0] > walking[0] * 1.5)
    check(f'and higher in pitch ({running[1]:.3f} against {walking[1]:.3f})',
          running[1] > walking[1])
    check(f'at a full run the level is near its top ({running[2]:.2f})', running[2] > 0.9)
    # The curve is what keeps a gentle walk from sounding like a gale.
    share = walking[2] / running[2]
    check(f'a walk is a whisper of a run, not half of it ({share:.0%} of the level '
          f'for {2.0 / 5.0:.0%} of the speed)', share < 0.4 * 0.9)

    print('it swells and falls away rather than switching:')
    let_go(key.W, key.LSHIFT)
    levels = []
    for _ in range(90):                        # a second and a half
        G['update'](1 / 60)
        levels.append(G['wind_level']())
    check(f'stopping fades it out over a moment, not at once '
          f'({levels[0]:.2f}, {levels[15]:.2f}, {levels[-1]:.2f})',
          levels[0] > levels[15] > levels[-1] and levels[-1] < 0.05
          and levels[5] > 0.2)

    print('and it can be switched off:')
    settings['enable_wind'] = False
    G['_wind_level'] = 0.0
    wind_after(1.5, key.W)
    check('with Wind off, nothing plays however fast you go',
          wind.volume == 0.0 and not wind.playing)
    settings['enable_wind'] = True
    let_go(key.W)

    print('the wind is wind, not hiss:')
    pyglet.media.Player = real_player
    import numpy as np
    src = G['_wind_source']
    d = src.get_queue_source().get_audio_data(10 ** 7)
    x = np.frombuffer(d.data, dtype=np.int16).astype(float) / 32767
    sr = src.audio_format.sample_rate
    power = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(len(x), 1 / sr)
    above = power[freqs > 4000].sum() / power.sum()
    check(f'almost nothing above 4 kHz ({above:.2%})', above < 0.02)
    check(f'cut between the ambience bed and the footsteps '
          f'({G["WIND_CUTOFF_HZ"]:g} Hz, bed 200, steps {G["FOOTSTEP_LOWPASS_HZ"]:g})',
          200 < G['WIND_CUTOFF_HZ'] < G['FOOTSTEP_LOWPASS_HZ'])
    check(f'it loops long enough not to tick ({len(x) / sr:.1f} s)', len(x) / sr >= 2.0)
    check(f'never clips (peak {np.abs(x).max():.2f})', np.abs(x).max() < 0.999)


run_game(run_checks)
finish('test_speed')
