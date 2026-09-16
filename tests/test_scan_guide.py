# SPDX-License-Identifier: CC0-1.0
"""The scan guide and the B basket scan, checked inside the real game.

Run: python tests/test_scan_guide.py

Runs the real game, safely: see _game_harness.py.
"""
import math

import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import check, finish, run_game

import pyglet
from pyglet.window import key


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False   # never touch sounds.txt
    blip = G['scan_guide_blip']
    pi = math.pi

    print('how far -> speed and loudness; which way -> pitch:')
    far, near = blip(60, 0, 0), blip(3, 0, 0)
    check(f'faster up close ({far[0]:.2f}s far, {near[0]:.2f}s near)', near[0] < far[0] / 3)
    check(f'louder up close ({far[1]:.2f} far, {near[1]:.2f} near)', near[1] > far[1] * 3)
    check('facing it: pitch exactly steady', blip(20, 0, 0)[2] == 1.0 and blip(20, 0, 1)[2] == 1.0)
    ahead, behind = blip(20, 0, 0), blip(20, pi, 0)
    check('turning never changes speed or loudness', ahead[0] == behind[0] and ahead[1] == behind[1])
    check('behind: lower', blip(20, pi, 0)[2] < 1 and blip(20, pi, 1)[2] < 1)
    check('behind: wobbles blip to blip', abs(blip(20, pi, 0)[2] - blip(20, pi, 1)[2]) > 0.05)
    check('left and right mirror each other', blip(20, 1.0, 0) == blip(20, -1.0, 0))

    # A controlled park: one egg, a known basket layout.
    G['start_game']()
    eggs, baskets, player = G['eggs'], G['baskets'], G['player']
    fired = []
    real_fire = G['fire_scan_guide']
    G['fire_scan_guide'] = lambda pos, volume, pitch: fired.append((pos, volume, pitch))
    eggs.clear()
    player.update(x=0.0, y=0.0, yaw=math.pi / 2)          # facing +y
    egg = {'x': 0.0, 'y': 30.0, 'z': 0.0, 'freq_idx': 0, 'hatch_timer': 999.0}
    eggs.append(egg)

    print('Space leads to the nearest egg:')
    G['try_scan']()
    g = G['_scan_guide']
    check('guide started on that egg', g is not None and g['kind'] == 'egg' and g['target'] is egg)
    t = G['now']()
    G['tick_scan_guide'](t)
    check('first blip plays straight away', len(fired) == 1)
    pos = fired[-1][0]
    check(f'blip is placed toward the egg, close by ({pos[0]:.2f}, {pos[1]:.2f})',
          abs(pos[0]) < 1e-6 and abs(pos[1] - G['GUIDE_VOICE_DISTANCE']) < 1e-6)
    G['tick_scan_guide'](t + 0.01)
    check('does not blip again before its interval', len(fired) == 1)

    # Walk to it, one simulated frame at a time.
    gaps, last_blip, sim_t = [], t, t
    while G['_scan_guide'] is not None and sim_t < t + 60:
        sim_t += 1 / 60
        player['y'] += G['WALK_SPEED'] / 60
        before = len(fired)
        G['tick_scan_guide'](sim_t)
        if len(fired) > before:
            gaps.append(sim_t - last_blip)
            last_blip = sim_t
    check(f'blips speed up on the walk in ({gaps[0]:.2f}s -> {gaps[-1]:.2f}s)',
          gaps[0] > gaps[-1] * 2.5)
    check('pitch steady the whole way (walking straight at it)', all(f[2] == 1.0 for f in fired))
    check(f'stops on arrival ({30 - player["y"]:.1f} m left)',
          G['_scan_guide'] is None and 30 - player['y'] <= G['COLLECT_RADIUS'] + 0.1)

    print('the guide lets go when its egg is gone:')
    player.update(x=0.0, y=0.0)
    G['start_scan_guide']('egg', egg)
    eggs.remove(egg)
    G['tick_scan_guide'](G['now']())
    check('egg collected elsewhere -> guide stops', G['_scan_guide'] is None)

    print('B leads to found baskets with room, V to unfound ones:')
    baskets.clear()
    full_found = {'x': 10.0, 'y': 0.0, 'z': 0.0, 'freq_idx': 0, 'discovered': True, 'eggs': []}
    open_found = {'x': 0.0, 'y': 50.0, 'z': 0.0, 'freq_idx': 1, 'discovered': True, 'eggs': []}
    near_unfound = {'x': -30.0, 'y': 0.0, 'z': 0.0, 'freq_idx': 2, 'discovered': False, 'eggs': []}
    far_unfound = {'x': 0.0, 'y': -120.0, 'z': 0.0, 'freq_idx': 3, 'discovered': False, 'eggs': []}
    baskets.extend([full_found, open_found, near_unfound, far_unfound])
    # Well past any capacity: finding a basket raises every basket's cap.
    full_found['eggs'] = [{'hatch_timer': 999.0}] * 999
    spoken = []
    G['say'] = spoken.append

    G['on_key_press'](key.B, 0)
    g = G['_scan_guide']
    check('B skips a closer full basket AND a closer unfound one, picks the open found one',
          g is not None and g['target'] is open_found)
    check(f'and says which kind ({spoken[-1]!r})', spoken[-1].startswith('Found basket with room, 50'))
    open_found['eggs'] = [{'hatch_timer': 999.0}] * 999
    G['tick_scan_guide'](G['now']())
    check('it fills up -> guide stops', G['_scan_guide'] is None)
    G['on_key_press'](key.B, 0)
    check('B with no found basket with room says so, and never offers an unfound one',
          G['_scan_guide'] is None and 'No found basket with room' in spoken[-1])

    G['on_key_press'](key.V, 0)
    g = G['_scan_guide']
    check('V picks the nearest unfound basket', g is not None and g['target'] is near_unfound)
    check(f'and says which kind ({spoken[-1]!r})', spoken[-1].startswith('Unfound basket, 30'))
    player.update(x=near_unfound['x'], y=near_unfound['y'])
    G['try_discover_basket']()
    G['tick_scan_guide'](G['now']())
    check('finding it ends the guide', G['_scan_guide'] is None)
    player.update(x=0.0, y=0.0)
    G['on_key_press'](key.V, 0)
    check('V again moves on to the next unfound one', G['_scan_guide'] is not None
          and G['_scan_guide']['target'] is far_unfound)
    far_unfound['discovered'] = True
    G['on_key_press'](key.V, 0)
    check('V with none left says so', G['_scan_guide'] is None and 'No unfound basket' in spoken[-1])

    print('keys and restarts:')
    w = G['window']
    G['start_scan_guide']('basket', open_found)
    G['reset_world']()
    check('a new park drops the old guide', G['_scan_guide'] is None)
    check('B and V are handled by the game',
          G['on_key_press'](key.B, 0) == pyglet.event.EVENT_HANDLED
          and G['on_key_press'](key.V, 0) == pyglet.event.EVENT_HANDLED)
    w.dispatch_event('on_key_press', key.ESCAPE, 0)
    w.dispatch_pending_events()
    check('Escape still does not quit', not w.has_exit)

    print('the guide does not sound like an egg or a bird:')
    import numpy as np

    def voice(src, f0):
        d = src.get_queue_source().get_audio_data(10 ** 7)
        x = np.frombuffer(d.data, dtype=np.int16).astype(float)
        sr = src.audio_format.sample_rate
        w = x[:int(0.06 * sr)] * np.hanning(int(0.06 * sr))
        sp = np.abs(np.fft.rfft(w, 1 << 18))
        f = np.fft.rfftfreq(1 << 18, 1 / sr)
        amp = lambda h: sp[(f > h * f0 - 15) & (f < h * f0 + 15)].max()
        win = int(0.004 * sr)
        e = np.sqrt(np.convolve(x ** 2, np.ones(win) / win, 'same'))
        pk = e.argmax()
        ring = np.where(e[pk:] < e[pk] * 0.1)[0][0] / sr
        return amp(2) / amp(1), ring

    def glide(src):
        """Pitch at the start and end of a sound's first 80 ms."""
        d = src.get_queue_source().get_audio_data(10 ** 7)
        x = np.frombuffer(d.data, dtype=np.int16).astype(float)
        sr = src.audio_format.sample_rate
        w = int(0.025 * sr)

        def pitch(seg):
            sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 1 << 16))
            f = np.fft.rfftfreq(1 << 16, 1 / sr)
            band = (f > 150) & (f < 3000)
            return f[band][sp[band].argmax()]
        return pitch(x[:w]), pitch(x[int(0.08 * sr) - w:int(0.08 * sr)])

    # Against eggs (the triangle voice the guide was first confused with in
    # plain-sine form): brightness and ring time.
    g2, g_ring = voice(G['_scan_guide_source'], 659.25)
    e2, e_ring = voice(G['_egg_call_sources'][4], G['PENTATONIC_FREQS'][4])
    check(f'guide has a bright second harmonic ({g2:.2f}; eggs {e2:.2f})', g2 > 0.15 and e2 < 0.05)
    check(f'guide dies away much faster ({g_ring * 1000:.0f} ms; eggs {e_ring * 1000:.0f} ms)',
          g_ring * 2.5 < e_ring)
    # Against birds, which are bright plucks too now: the guide holds its
    # pitch inside a blip, and a bird slides.
    g0, g1 = glide(G['_scan_guide_source'])
    b0, b1 = glide(G['_bird_call_sources']['chirp'][2])
    check(f'guide holds its pitch ({g0:.0f} to {g1:.0f} Hz), a bird slides ({b0:.0f} to {b1:.0f} Hz)',
          abs(g1 - g0) < 15 and b1 > b0 * 1.15)

    print('the real sound path:')
    G['fire_scan_guide'] = real_fire
    made = []
    real_player = pyglet.media.Player

    class Spy(real_player):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            made.append(self)
    pyglet.media.Player = Spy
    try:
        G['fire_scan_guide']((1.0, 0.0, 0.0), volume=0.5, pitch=0.8)
    finally:
        pyglet.media.Player = real_player
    check('plays with the pitch it was given',
          len(made) == 1 and abs(made[0].pitch - 0.8) < 1e-6)


run_game(run_checks)
finish('test_scan_guide')
