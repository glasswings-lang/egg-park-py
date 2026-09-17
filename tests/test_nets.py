# SPDX-License-Identifier: CC0-1.0
"""Nets from chests, scooping every egg in reach, and footsteps on baskets and
chests that can be told apart from the ground and from each other.

Run: python tests/test_nets.py

Runs the real game, safely: see _game_harness.py.
"""
import json
import math
import random

import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import check, finish, run_game

import numpy as np


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False
    spoken, collects, refusals = [], [], []
    G['say'] = spoken.append
    G['_play'] = lambda src, **kw: None
    G['fire_collect_sound'] = lambda: collects.append(1)
    G['fire_refuse_sound'] = lambda: refusals.append(1)
    settings = G['settings']
    settings['enable_ground_hatching'] = False
    P, eggs, held, chests, progress = G['player'], G['eggs'], G['held'], G['chests'], G['progress']

    def egg_at(x, y, laid=True):
        e = {'x': x, 'y': y, 'z': 0.0, 'freq_idx': 0, 'hatch_timer': 999.0, 'laid': laid}
        eggs.append(e)
        return e

    def chest_at(x, y):
        c = {'x': x, 'y': y, 'z': 0.0, 'discovered': False, 'eggs': [], 'gifts': [], 'clutch_bonus': 0}
        chests.append(c)
        return c

    def fresh_park():
        G['reset_world']()
        eggs.clear()
        held.clear()
        chests.clear()
        spoken.clear()
        collects.clear()
        refusals.clear()
        P.update(x=0.0, y=0.0)

    G['start_game']()

    print('how often a chest has a net:')
    random.seed(11)
    share = sum(G['roll_net']() for _ in range(4000)) / 4000
    check(f'about half of chests ({share:.0%})', 0.45 < share < 0.55)
    progress['nets'] = 6                          # 14 m: one short of the most
    share = sum(G['roll_net']() for _ in range(4000)) / 4000
    check(f'still about half with one net to go ({share:.0%})', 0.45 < share < 0.55)
    progress['nets'] = 7                          # 16 m: the most
    check('none at all once reach is maxed', not any(G['roll_net']() for _ in range(4000)))
    progress['nets'] = 0

    print('finding a chest with a net:')
    fresh_park()
    check('a new park has no nets and a 2 m reach', progress['nets'] == 0 and G['collect_radius']() == 2.0)
    G['roll_net'] = lambda: True
    c = chest_at(100.0, 0.0)
    P.update(x=100.0, y=0.0)
    G['try_discover_chest']()
    check('the net is yours', progress['nets'] == 1 and c['net'] is True)
    check(f'reach is now 4 m ({G["collect_radius"]()})', G['collect_radius']() == 4.0)
    check(f'and it says so ({spoken[-1]!r})', 'And a net. You pick up eggs from 4 metres.' in spoken[-1])
    G['roll_net'] = lambda: False
    c2 = chest_at(200.0, 0.0)
    P.update(x=200.0, y=0.0)
    G['try_discover_chest']()
    check('a chest without one gives none, and says nothing about nets',
          progress['nets'] == 1 and c2['net'] is False and 'net' not in spoken[-1])
    G['announce_status']()
    check(f'P mentions it ({spoken[-1]!r})', '1 net, picking up eggs from 4 metres' in spoken[-1])
    progress['nets'] = 50
    check(f'reach stops at {G["NET_REACH_MAX"]} m, short of where new eggs appear '
          f'({G["EGG_MIN_FROM_PLAYER"]} m)',
          G['collect_radius']() == G['NET_REACH_MAX'] < G['EGG_MIN_FROM_PLAYER'])

    print('scooping:')
    fresh_park()
    G['CARRY_START'] = 20
    near, mid, far = egg_at(1.5, 0.0), egg_at(0.0, 5.0), egg_at(-9.0, 0.0)
    G['try_collect_eggs']()
    check('no nets: only the egg underfoot', len(held) == 1 and near not in eggs and mid in eggs)
    progress['nets'] = 4                         # 10 m
    spoken.clear()
    collects.clear()
    G['try_collect_eggs']()
    check('four nets: both others come up in one go', mid not in eggs and far not in eggs and len(held) == 3)
    check(f'one sound, one line ({spoken!r})',
          len(collects) == 1 and spoken == [f'Scooped 2 eggs. 3 of {G["player_carry_cap"]()} held.'])

    print('scooping with not enough room:')
    fresh_park()
    G['CARRY_START'] = 3
    progress['nets'] = 4
    for a in np.linspace(0, 6, 6):
        egg_at(3.0 * math.cos(a), 3.0 * math.sin(a))
    for _ in range(120):
        G['try_collect_eggs']()
    check(f'fills your hands ({len(held)} of 3) and leaves the rest', len(held) == 3 and len(eggs) == 3)
    check(f'says so once, in the same line ({spoken!r})',
          spoken == ['Scooped 3 eggs. 3 of 3 held. Hands full.'])
    check('no separate refusal sound over the pickup', not refusals and len(collects) == 1)
    # Told once and then left alone: walking with full hands through a park
    # of thousands of eggs used to be a running commentary. See test_movement.
    spoken.clear()
    P.update(x=50.0)
    G['try_collect_eggs']()
    P.update(x=0.0)
    G['try_collect_eggs']()
    check(f'walk away and back: not told again ({spoken!r})', not spoken and not refusals)
    G['forget_hands_full']()                   # what depositing does
    G['try_collect_eggs']()
    check(f'after a deposit it is news again ({spoken[-1]!r})',
          len(refusals) == 1 and spoken[-1].startswith('Hands full'))

    print('wild eggs picked up by a net come back far away:')
    fresh_park()
    progress['nets'] = 7
    G['CARRY_START'] = 30
    for i in range(6):
        egg_at(4.0 + i, 0.0, laid=False)
    for _ in range(60):
        G['update'](1 / 60)
    closest = min(math.hypot(e['x'] - P['x'], e['y'] - P['y']) for e in eggs)
    check(f'6 scooped, 6 replaced, none within reach (closest {closest:.0f} m)',
          len(held) == 6 and len(eggs) == 6 and closest > G['collect_radius']())
    G['CARRY_START'] = 1

    print('scan guide stops at your reach:')
    fresh_park()
    progress['nets'] = 3                         # 8 m
    target = egg_at(0.0, 7.0)
    G['start_scan_guide']('egg', target)
    G['tick_scan_guide'](G['now']())
    check('an egg already in reach has no guide left to follow', G['_scan_guide'] is None)

    print('saving nets:')
    fresh_park()
    progress['nets'] = 3
    G['save_park']('test')
    G['reset_world']()
    check('reset clears nets', progress['nets'] == 0)
    check('the park loads with its nets', G['load_park']() and progress['nets'] == 3)
    path = G['PARK_SAVE_FILE']
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    del data['progress']['nets']
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    check('a park saved before nets loads with none', G['load_park']() and progress['nets'] == 0)

    print('what your feet land on:')
    fired = []
    G['_play'] = lambda src, **kw: fired.append(src)
    fresh_park()
    chest_at(300.0, 0.0)
    basket = G['baskets'][0]

    def step_at(x, y):
        fired.clear()
        P.update(x=x, y=y)
        G['fire_footstep']()
        return fired[0]

    settings['prefer_samples'] = False
    check('open ground', step_at(20.0, 20.0) is G['_footstep_source'])
    check('on a basket', step_at(basket['x'] + 1.5, basket['y']) is G['_footstep_basket_source'])
    check('on a chest, 4.8 m from its middle', step_at(304.8, 0.0) is G['_footstep_chest_source'])
    check('5.3 m out: ground again', step_at(305.3, 0.0) is G['_footstep_source'])

    print('the three surfaces sound different:')

    def audio(src):
        d = src.get_queue_source().get_audio_data(10 ** 7)
        return np.frombuffer(d.data, dtype=np.int16).astype(float) / 32767, src.audio_format.sample_rate

    def spectrum(src):
        x, sr = audio(src)
        p = np.abs(np.fft.rfft(x * np.hanning(len(x)), 1 << 16)) ** 2
        return p, np.fft.rfftfreq(1 << 16, 1 / sr)

    def peak_hz(src):
        p, f = spectrum(src)
        return f[np.argmax(p)]

    def tonal_share(src, hz):
        """Energy within 40 Hz of a note, of the whole sound."""
        p, f = spectrum(src)
        return p[np.abs(f - hz) < 40].sum() / p.sum()

    ground, bsk, cst = G['_footstep_source'], G['_footstep_basket_source'], G['_footstep_chest_source']
    b_hz, c_hz = peak_hz(bsk), peak_hz(cst)
    check(f'basket step rings at its note ({b_hz:.0f} Hz)', abs(b_hz - G['FOOTSTEP_BASKET_KNOCK_HZ']) < 15)
    check(f'chest step rings at its note ({c_hz:.0f} Hz), {b_hz - c_hz:.0f} Hz below the basket',
          abs(c_hz - G['FOOTSTEP_CHEST_KNOCK_HZ']) < 15 and 250 < b_hz - c_hz < 350)
    g_b, b_b = tonal_share(ground, b_hz), tonal_share(bsk, b_hz)
    g_c, c_c = tonal_share(ground, c_hz), tonal_share(cst, c_hz)
    check(f'the ground has no such ring: at the basket note {g_b:.0%}, basket {b_b:.0%}',
          b_b > 5 * g_b and b_b > 0.2)
    check(f'at the chest note: ground {g_c:.0%}, chest {c_c:.0%}', c_c > 5 * g_c and c_c > 0.2)
    c_b = tonal_share(cst, b_hz)
    check(f'the chest step has little at the basket note ({c_b:.0%})', c_b < b_b / 5)
    for name, src in (('basket', bsk), ('chest', cst)):
        x, _sr = audio(src)
        check(f'{name} step never clips (peak {np.abs(x).max():.2f})', np.abs(x).max() < 0.999)
    rms = lambda s: np.sqrt((audio(s)[0] ** 2).mean())
    print(f'  loudness against the ground step: basket {20 * np.log10(rms(bsk) / rms(ground)):+.1f} dB, '
          f'chest {20 * np.log10(rms(cst) / rms(ground)):+.1f} dB')


run_game(run_checks)
finish('test_nets')
