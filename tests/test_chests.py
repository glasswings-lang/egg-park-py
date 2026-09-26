# SPDX-License-Identifier: CC0-1.0
"""Chests: spawning, finding, three gift slots, capacity, depositing, hatching,
scanning with C and Shift+C, saving, and a voice unlike anything else.

Run: python tests/test_chests.py

Runs the real game, safely: see _game_harness.py.
"""
import math
import random

import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import check, finish, run_game

import numpy as np
from pyglet.window import key


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False
    spoken = []
    G['say'] = spoken.append
    G['_play'] = lambda src, **kw: None
    settings = G['settings']
    settings['enable_ground_hatching'] = False
    state = {n: G[n] for n in ('player', 'eggs', 'baskets', 'chests', 'held', 'birds', 'progress')}
    P, chests, baskets = state['player'], state['chests'], state['baskets']

    def chest_at(x, y, found=False):
        c = {'x': x, 'y': y, 'z': 0.0, 'discovered': found, 'eggs': [], 'gifts': [], 'clutch_bonus': 0}
        chests.append(c)
        return c

    def frames(seconds):
        for _ in range(int(seconds * 60)):
            G['update'](1 / 60)

    print('a new park:')
    G['start_game']()
    check('starts with no chests and no gift bonuses',
          not chests and state['progress'] == {'carry_bonus': 0, 'storage_bonus': 0, 'nets': 0})
    frames(0.1)
    check(f'one unfound chest appears within earshot ({len(chests)})', len(chests) == 1)
    c = chests[0]
    d = math.hypot(c['x'], c['y'])
    check(f'further out than baskets start ({d:.0f} m)', G['CHEST_SPAWN_MIN'] <= d <= G['CHEST_SPAWN_MAX'])
    check('clear of every basket', all(math.hypot(b['x'] - c['x'], b['y'] - c['y']) >= G['CHEST_MIN_SEPARATION']
                                       for b in baskets))
    frames(1)
    check('and no more pile up while one is waiting', len(chests) == 1)
    # Once was luck. Two hundred fresh parks: never a second chest at the start.
    extra = 0
    for _ in range(200):
        G['reset_world']()
        G['maybe_spawn_chest']()
        G['maybe_spawn_chest']()
        extra += len(chests) - 1
    check(f'200 fresh parks, extra chests spawned at the start: {extra}', extra == 0)

    print('gift rolls:')
    random.seed(5)
    mixes, amounts = set(), set()
    for _ in range(4000):
        gifts = G['roll_gifts']()
        if len(gifts) != 3:
            break
        for slot in gifts:
            mixes.add(tuple(sorted(slot)))
            amounts.update(slot.values())
    check('always three slots', len(gifts) == 3)
    check(f'all fifteen mixes of eggs, clutches, carry and storage turn up ({len(mixes)})', len(mixes) == 15)
    check(f'every amount is 1 to 5 ({sorted(amounts)})', amounts == {1, 2, 3, 4, 5})
    rolls = [G['roll_gifts']() for _ in range(3000)]
    both = [s for g in rolls for s in g if 'carry' in s and 'storage' in s]
    check('parts of a mixed slot roll separately', any(s['carry'] != s['storage'] for s in both))

    print('finding a chest:')
    G['reset_world']()
    for b in baskets[:2]:
        b['discovered'] = True
    carry0, basket0, chest0 = G['player_carry_cap'](), G['basket_cap'](), G['chest_cap']()
    check(f'with 2 baskets found, a chest holds {chest0}: 5 plus 2 per basket',
          chest0 == 5 + 2 * 2)
    c = chest_at(100.0, 0.0)
    G['roll_net'] = lambda: False          # nets: see test_nets.py
    G['roll_gifts'] = lambda: [{'carry': 3}, {'storage': 2, 'eggs': 4, 'clutches': 2},
                               {'eggs': 1, 'carry': 1, 'storage': 5, 'clutches': 1}]
    P.update(x=100.0 - 7.2, y=0.0)
    G['try_discover_chest']()
    check('7.2 m away: not found yet', not c['discovered'])
    P.update(x=100.0 - 6.8, y=0.0)
    G['try_discover_chest']()
    check('6.8 m away: found (a chest is wider than a basket)', c['discovered'])
    check(f'carry gifts add up: +4 ({carry0} -> {G["player_carry_cap"]()})',
          G['player_carry_cap']() == carry0 + 4)
    # A basket never holds less than you carry, so the carry gift lifts that
    # floor first (2 baskets found, now carrying 5), then storage adds on top.
    check(f'basket capacity: at least what you carry (5), +7 storage, +1 for finding a chest '
          f'({basket0} -> {G["basket_cap"]()})', G['basket_cap']() == max(2, 5) + 8)
    check(f'chest capacity gets the same +8 ({chest0} -> {G["chest_cap"]()})', G['chest_cap']() == chest0 + 8)
    check('egg gifts belong to this chest: +5 a clutch', c['clutch_bonus'] == 5)
    check('clutch gifts belong to this chest: +3 clutches', c['extra_clutches'] == 3)
    check(f'says what it gave ({spoken[-1]!r})',
          'Chest found. Carry 4 more. Baskets and chests hold 8 more. '
          'Birds hatched here lay 5 more eggs a clutch. '
          'Birds hatched here lay 3 more clutches before flying off.' in spoken[-1])
    check('one clutch is said as one clutch',
          'lay 1 more clutch before' in G['gift_speech']({'eggs': 0, 'clutches': 1, 'carry': 0, 'storage': 0}))
    check('no clutch gift, nothing said about clutches',
          'clutch' not in G['gift_speech']({'eggs': 0, 'clutches': 0, 'carry': 2, 'storage': 0}))

    print('chests grow twice as fast as baskets:')
    before_b, before_c = G['basket_cap'](), G['chest_cap']()
    baskets[2]['discovered'] = True
    check(f'finding a basket: baskets +1 ({before_b} -> {G["basket_cap"]()}), chests +2 ({before_c} -> {G["chest_cap"]()})',
          G['basket_cap']() == before_b + 1 and G['chest_cap']() == before_c + 2)

    print('depositing and hatching:')
    settings['hatch_time'] = 10.0
    G['CLUTCH_MIN'] = G['CLUTCH_MAX'] = 2
    state['held'].clear()
    state['held'].extend({'hatch_timer': 10.0, 'next_warning': 0.0} for _ in range(3))
    P.update(x=100.0 - 4.8, y=0.0)
    G['try_deposit']()
    check(f'F from 4.8 m puts eggs in the chest ({len(c["eggs"])})', len(c['eggs']) == 3 and not state['held'])
    check(f'and says so ({spoken[-1]!r})', spoken[-1].startswith('Deposited 3. Chest 3 of'))
    P.update(x=500.0, y=500.0)
    state['birds'].clear()
    frames(10.5)
    home = [b for b in state['birds'] if (b['home_x'], b['home_y']) == (100.0, 0.0)]
    check(f'eggs hatch in the chest into birds living there ({len(home)})', len(home) == 3)
    check('each carries the chest\'s egg gift', all(b['clutch_bonus'] == 5 for b in home))
    sizes = [G['clutch_size'](b) for b in home]
    check(f'so their clutches are 2 + 5 = {sizes[0]}', sizes == [7, 7, 7])
    lives = [b['clutches_left'] for b in home]
    check(f'and they lay 3 more clutches than a plain bird before flying off ({lives})',
          all(G['CLUTCHES_MIN'] + 3 <= n <= G['CLUTCHES_MAX'] + 3 for n in lives))
    c['eggs'] = [{'hatch_timer': 999.0}] * G['chest_cap']()
    state['held'].append({'hatch_timer': 999.0, 'next_warning': 0.0})
    P.update(x=100.0, y=0.0)
    G['try_deposit']()
    check(f'a full chest says so ({spoken[-1]!r})', spoken[-1].startswith('Chest full.'))
    c['eggs'] = []
    state['held'].clear()

    print('C and Shift+C:')
    G['reset_world']()
    near_found = chest_at(40.0, 0.0, found=True)
    full_found = chest_at(10.0, 0.0, found=True)
    full_found['eggs'] = [{'hatch_timer': 999.0}] * 999
    unfound = chest_at(0.0, 30.0)
    far_unfound = chest_at(0.0, -150.0)
    P.update(x=0.0, y=0.0)
    G['on_key_press'](key.C, 0)
    g = G['_scan_guide']
    check('C skips a full chest and an unfound one, leads to the found one with room',
          g is not None and g['kind'] == 'chest' and g['target'] is near_found)
    check(f'says which ({spoken[-1]!r})', spoken[-1].startswith('Found chest with room, 40'))
    G['on_key_press'](key.C, key.MOD_SHIFT)
    g = G['_scan_guide']
    check('Shift+C leads to the nearest unfound chest', g is not None and g['kind'] == 'unfound chest'
          and g['target'] is unfound)
    check(f'says which ({spoken[-1]!r})', spoken[-1].startswith('Unfound chest, 30'))
    P.update(x=0.0, y=24.0)
    G['try_discover_chest']()
    G['tick_scan_guide'](G['now']())
    check('finding it ends the guide', G['_scan_guide'] is None)
    far_unfound['discovered'] = True
    P.update(x=0.0, y=0.0)
    G['on_key_press'](key.C, key.MOD_SHIFT)
    check('Shift+C with none left says so', G['_scan_guide'] is None and 'No unfound chest' in spoken[-1])
    baskets[1]['discovered'] = False
    G['on_key_press'](key.B, key.MOD_SHIFT)
    check('Shift+B leads to unfound baskets, like V', G['_scan_guide'] is not None
          and G['_scan_guide']['kind'] == 'unfound basket')
    check('C, Shift+C and Shift+B are handled',
          all(G['on_key_press'](sym, mod) is not None for sym, mod in
              ((key.C, 0), (key.C, key.MOD_SHIFT), (key.B, key.MOD_SHIFT))))

    print('saving:')
    G['reset_world']()
    saved_chest = chest_at(60.0, 60.0, found=True)
    saved_chest['gifts'] = [{'eggs': 2}, {'carry': 1}, {'storage': 3, 'carry': 2}]
    saved_chest['clutch_bonus'] = 2
    saved_chest['eggs'] = [{'hatch_timer': 7.5, 'next_warning': 0.0}]
    state['progress'].update(carry_bonus=3, storage_bonus=3)
    caps = (G['player_carry_cap'](), G['basket_cap'](), G['chest_cap']())
    G['save_park']('test')
    G['reset_world']()
    check('reset clears chests and bonuses', not chests and state['progress']['carry_bonus'] == 0)
    check('the park loads', G['load_park']())
    back = chests[0] if chests else {}
    check('the chest comes back with its gifts, bonus and eggs',
          back.get('gifts') == saved_chest['gifts'] and back.get('clutch_bonus') == 2
          and back.get('eggs') and back['eggs'][0]['hatch_timer'] == 7.5)
    check(f'and every capacity comes back ({caps})',
          (G['player_carry_cap'](), G['basket_cap'](), G['chest_cap']()) == caps)

    print('a chest sounds like struck metal:')
    def audio(src):
        d = src.get_queue_source().get_audio_data(10 ** 7)
        return np.frombuffer(d.data, dtype=np.int16).astype(float), src.audio_format.sample_rate

    def off_harmonic_share(src, f0):
        """How much of the sound's energy sits away from whole-number multiples
        of its note. Clean tones: almost none. A bell: a lot."""
        x, sr = audio(src)
        n = min(len(x), int(0.4 * sr))
        x = x[:n] * np.hanning(n)
        p = np.abs(np.fft.rfft(x, 1 << 17)) ** 2
        f = np.fft.rfftfreq(1 << 17, 1 / sr)
        band = (f > 50) & (f < 5000)
        harmonic = np.zeros_like(f, dtype=bool)
        for h in range(1, int(5000 / f0) + 1):
            harmonic |= np.abs(f - h * f0) < 12
        return p[band & ~harmonic].sum() / p[band].sum()

    bell = off_harmonic_share(G['_chest_chime_source'], G['CHEST_BELL_HZ'])
    others = {
        'basket chime': off_harmonic_share(G['_basket_chime_sources'][4], G['PENTATONIC_FREQS'][4] * G['BASKET_OCTAVE']),
        'found basket': off_harmonic_share(G['_basket_chime_found_sources'][4], G['PENTATONIC_FREQS'][4] * G['BASKET_OCTAVE']),
        'egg call': off_harmonic_share(G['_egg_call_sources'][0], G['PENTATONIC_FREQS'][0]),
        'scan guide': off_harmonic_share(G['_scan_guide_source'], 659.25),
    }
    worst = max(others.values())
    check(f'chest bell: {bell:.0%} of its sound between the harmonics; '
          f'baskets, eggs and the guide at most {worst:.0%}', bell > 0.3 and worst < 0.1)
    nearest_note = min(G['PENTATONIC_FREQS'] + [f * G['BASKET_OCTAVE'] for f in G['PENTATONIC_FREQS']],
                       key=lambda f: abs(f - G['CHEST_BELL_HZ']))
    check(f'and its note ({G["CHEST_BELL_HZ"]} Hz) isn\'t any basket or egg note (nearest {nearest_note} Hz)',
          abs(nearest_note - G['CHEST_BELL_HZ']) > 5)


run_game(run_checks)
finish('test_chests')
