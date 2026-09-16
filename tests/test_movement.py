# SPDX-License-Identifier: CC0-1.0
"""Running with Shift, and footsteps that thud rather than hiss.

Run: python tests/test_movement.py

Runs the real game, safely: see _game_harness.py.
"""
import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import check, finish, run_game

import numpy as np
from pyglet.window import key


def samples(src):
    d = src.get_queue_source().get_audio_data(10 ** 7)
    return (np.frombuffer(d.data, dtype=np.int16).astype(float) / 32767,
            src.audio_format.sample_rate)


def share_above(x, sr, hz):
    power = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / sr)
    return power[f > hz].sum() / power.sum()


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False

    print('footsteps are low-passed:')
    raw, sr = samples(G['_noise_burst'](0.12, attack=0.005, decay=0.05, release=0.06))
    for name in ('_footstep_source', '_footstep_basket_source'):
        x, sr = samples(G[name])
        hiss_before, hiss_now = share_above(raw, sr, 8000), share_above(x, sr, 8000)
        check(f'{name}: energy above 8 kHz {hiss_before:.0%} before, {hiss_now:.1%} now',
              hiss_now < 0.05 and hiss_before > 0.4)
        check(f'{name}: never clips (peak {np.abs(x).max():.2f})', np.abs(x).max() < 0.999)
    # Body is judged over twenty fresh footsteps, not the one the game made:
    # each is new random noise, and a single one swings between 45% and 60%
    # below 3 kHz from run to run. Twenty average 54-57% (unfiltered noise:
    # 13-14%), so this can't fail by chance and still catches a lost filter.
    fresh = [samples(G['_lowpassed_noise_burst'](0.12, G['FOOTSTEP_LOWPASS_HZ'], attack=0.005,
                                                 decay=0.05, release=0.06)) for _ in range(20)]
    body = np.mean([1 - share_above(x, sr, 3000) for x, sr in fresh])
    check(f'footsteps still have body below 3 kHz ({body:.0%} of it, averaged over 20)',
          body > 0.45)
    x, sr = samples(G['_footstep_source'])
    rms = lambda v: np.sqrt((v ** 2).mean())
    print(f'  note loudness now {20 * np.log10(rms(x) / rms(raw)):+.1f} dB against the old hiss')

    print('Shift runs:')
    G['start_game']()
    player, keys = G['player'], G['keys']
    steps = []
    G['fire_footstep'] = lambda *a, **k: steps.append(1)

    def walk(seconds, shift):
        steps.clear()
        player.update(x=0.0, y=0.0, yaw=0.0)
        keys.on_key_press(key.W, 0)
        if shift:
            keys.on_key_press(key.LSHIFT, 0)
        for _ in range(int(seconds * 60)):
            G['update'](1 / 60)
        keys.on_key_release(key.W, 0)
        keys.on_key_release(key.LSHIFT, 0)
        return player['x'], len(steps)

    walked, walk_steps = walk(10, False)
    ran, run_steps = walk(10, True)
    check(f'walking: {walked:.1f} m in 10 s, {walk_steps} steps',
          abs(walked - G['settings']['walk_speed'] * 10) < 0.5 and 18 <= walk_steps <= 20)
    check(f'running: {ran:.1f} m in 10 s', abs(ran - G['settings']['run_speed'] * 10) < 0.5)
    check(f'running steps are quicker but not a drumroll ({run_steps / 10:.1f} a second, '
          f'walking {walk_steps / 10:.1f})', walk_steps < run_steps < 35)
    G['settings']['run_speed'] = 8.0
    ran, _ = walk(5, True)
    check(f'run speed setting is honoured ({ran:.1f} m in 5 s at 8 m/s)', abs(ran - 40) < 0.5)
    check('Shift on its own does nothing the game has to handle',
          G['on_key_press'](key.LSHIFT, 0) is None)

    print('hands full: told once, not every frame:')
    spoken, refusals = [], []
    G['say'] = spoken.append
    G['fire_refuse_sound'] = lambda: refusals.append(1)
    G['reset_world']()
    G['eggs'].clear()
    egg = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'freq_idx': 0, 'hatch_timer': 999.0}
    G['eggs'].append(egg)
    G['held'].extend({'hatch_timer': 999.0, 'next_warning': 0.0}
                     for _ in range(G['player_carry_cap']()))
    player.update(x=0.0, y=0.0)
    for _ in range(120):                       # two seconds stood on the egg
        G['update'](1 / 60)
    said = [s for s in spoken if s.startswith('Hands full')]
    check(f'two seconds on one egg: {len(refusals)} refusal sound, {len(said)} spoken',
          len(refusals) == 1 and len(said) == 1)
    player.update(x=10.0)
    G['update'](1 / 60)
    player.update(x=0.0)
    for _ in range(60):
        G['update'](1 / 60)
    check(f'step away and back: told again ({len(refusals)} in all)', len(refusals) == 2)
    G['held'].clear()
    G['update'](1 / 60)
    check('with room, the same egg is picked up', egg not in G['eggs'] and len(G['held']) == 1)


run_game(run_checks)
finish('test_movement')
