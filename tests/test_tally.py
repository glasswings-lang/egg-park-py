# SPDX-License-Identifier: CC0-1.0
"""Repeated events are counted and reported once, never one sound per event.

The park that forced this: eggs hatching away on the ground fired a flyoff
each, twelve a frame, so all 64 sound slots held identical flyoffs and the
basket chimes and bird calls were dropped for want of a slot. The same shape
of bug sat in basket hatching (a spoken line per egg) and in the egg warning
(an alarm per egg).

Run: python tests/test_tally.py

Runs the real game, safely: see _game_harness.py.
"""
import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import check, finish, run_game


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False
    spoken, fired = [], []
    G['say'] = spoken.append
    settings = G['settings']
    settings['enable_ground_hatching'] = False
    settings['enable_basket_hatching'] = True
    settings['enable_hand_hatching'] = True
    settings['enable_egg_warnings'] = True
    settings['lay_time'] = 9000.0
    settings['hatch_time'] = 60.0
    settings['say_hatching'] = True       # the spoken line is off by default; its own check below
    player, eggs, held, birds = G['player'], G['eggs'], G['held'], G['birds']

    for name in ('fire_wild_bird_flyoff', 'fire_hatch_in_basket_at', 'fire_egg_warning'):
        G[name] = (lambda cue: lambda position=None: fired.append((cue, position)))(name)

    clock = [1000.0]

    def tick(seconds):
        """Run the hatch loop and the reporting, a frame at a time."""
        for _ in range(int(seconds * 60)):
            G['tick_hatching'](1 / 60)
            clock[0] += 1 / 60
            G['flush_all'](clock[0])

    def fresh():
        G['start_game']()
        G['forget_all']()
        spoken.clear()
        fired.clear()
        eggs.clear()
        held.clear()
        birds.clear()
        player.update(x=0.0, y=0.0)
        basket = G['baskets'][0]
        basket['discovered'] = True
        basket['eggs'] = []
        return basket

    print('a whole basket coming due in one frame:')
    basket = fresh()
    basket['eggs'] = [{'hatch_timer': 0.5, 'next_warning': 99.0} for _ in range(28)]
    tick(1.0)
    hatch_sounds = [f for f in fired if f[0] == 'fire_hatch_in_basket_at']
    said = [s for s in spoken if 'hatched' in s]
    check(f'28 birds are born ({len(birds)})', len(birds) == 28 and not basket['eggs'])
    check(f'one sound for the lot, not 28 ({len(hatch_sounds)})', len(hatch_sounds) == 1)
    check(f'one spoken line, with the number in it ({said!r})',
          len(said) == 1 and said[0] == '28 birds hatched. 28 birds in the park.')
    check('the sound came from the basket', hatch_sounds[0][1] == (basket['x'], basket['y'], basket['z']))

    print('one egg on its own still reads as one egg:')
    basket = fresh()
    basket['eggs'] = [{'hatch_timer': 0.5, 'next_warning': 99.0}]
    tick(1.0)
    check(f'says it in the singular ({spoken[-1]!r})',
          spoken[-1] == 'A bird hatched. 1 bird in the park.')

    print('eggs hatching in your hands:')
    fresh()
    held.extend({'hatch_timer': 0.5, 'next_warning': 99.0} for _ in range(6))
    tick(1.0)
    flyoffs = [f for f in fired if f[0] == 'fire_wild_bird_flyoff']
    check(f'all six are gone ({len(held)} left)', not held)
    check(f'one sound and one line for six losses ({len(flyoffs)} sounds, {spoken!r})',
          len(flyoffs) == 1 and spoken == ['6 eggs in your hands hatched. Those birds flew off.'])

    print('the alarm, with thirty eggs counting down at once:')
    basket = fresh()
    basket['eggs'] = [{'hatch_timer': 4.0, 'next_warning': 0.0} for _ in range(30)]
    tick(3.0)
    warnings = [f for f in fired if f[0] == 'fire_egg_warning']
    check(f'3 seconds, 30 eggs: {len(warnings)} alarms, about one a second',
          2 <= len(warnings) <= 4)
    check('and it sounds from the basket they are in',
          all(w[1] == (basket['x'], basket['y'], basket['z']) for w in warnings))

    print('the nearest one is the one you hear:')
    fresh()
    near = {'x': 5.0, 'y': 0.0, 'z': 0.0}
    far = {'x': 300.0, 'y': 0.0, 'z': 0.0}
    G['GROUND_FLYOFF'].add((far['x'], far['y'], far['z']))
    G['GROUND_FLYOFF'].add((near['x'], near['y'], near['z']))
    G['GROUND_FLYOFF'].add((far['x'], far['y'], far['z']))
    G['GROUND_FLYOFF'].flush(clock[0] + 100)
    heard = [f for f in fired if f[0] == 'fire_wild_bird_flyoff']
    check(f'three eggs, one sound, from the near one ({heard!r})',
          len(heard) == 1 and heard[0][1] == (5.0, 0.0, 0.0))

    print('the gap between reports:')
    fresh()
    tal = G['BIRD_HATCHED']
    tal.add((0.0, 0.0, 0.0))
    first = tal.flush(500.0)
    tal.add((0.0, 0.0, 0.0))
    during = tal.flush(500.0 + tal.gap / 2)
    check(f'a second report inside the gap waits ({during!r})', first and not during)
    held_over = tal.count
    later = tal.flush(500.0 + tal.gap + 0.01)
    check(f'and goes out after it, still counted ({later!r})', held_over == 1 and later)
    check('and one bird reads as one bird', 'A bird hatched. 0 birds in the park.' == later
          or later == 'A bird hatched. 1 bird in the park.')

    print('hatching is not spoken unless asked for:')
    settings['say_hatching'] = False
    basket = fresh()
    basket['eggs'] = [{'hatch_timer': 0.5, 'next_warning': 99.0} for _ in range(5)]
    tick(1.0)
    hatch_sounds = [f for f in fired if f[0] == 'fire_hatch_in_basket_at']
    check(f'five hatch: the sound plays, nothing is said ({spoken!r})',
          len(birds) == 5 and hatch_sounds and not any('hatched' in s for s in spoken))
    check('the setting is off by default',
          next(i for i in G['SETTINGS_MENU'] if i['key'] == 'say_hatching')['default'] is False)
    settings['say_hatching'] = True

    print('a new park does not inherit the last one:')
    tal.add((0.0, 0.0, 0.0))
    G['reset_world']()
    check('what was waiting is dropped', tal.count == 0 and tal.next_at == 0.0)

    print('a hundred birds shuffling about:')
    fresh()
    G['fire_bird_ambient_at'] = lambda position=None: fired.append(('rustle', position))
    settings['enable_bird_ambient'] = True
    basket = G['baskets'][0]
    for i in range(100):
        G['make_your_bird'](basket)
    for bird in birds:
        bird['next_ambient_at'] = 0.0          # every one of them, due at once
    fired.clear()
    for _ in range(int(2 * 60)):
        G['tick_birds'](1 / 60)
        clock[0] += 1 / 60
        G['flush_all'](clock[0])
    rustles = [f for f in fired if f[0] == 'rustle']
    most = 2 / G['RUSTLE'].gap + 1
    check(f'100 birds, 2 seconds: {len(rustles)} rustles, not 100 (at most {most:.0f})',
          0 < len(rustles) <= most)

    print('nothing starves the rest of the world:')
    # The original failure was other cues being dropped for want of a voice.
    # With one report per event kind per frame, a whole park hatching cannot
    # come near the 64 the game allows.
    basket = fresh()
    settings['enable_ground_hatching'] = True
    for i in range(400):
        eggs.append({'x': 2.0 + i * 0.5, 'y': 0.0, 'z': 0.0, 'freq_idx': 0,
                     'hatch_timer': 0.5, 'laid': True})
    basket['eggs'] = [{'hatch_timer': 0.5, 'next_warning': 0.0} for _ in range(20)]
    held.extend({'hatch_timer': 0.5, 'next_warning': 0.0} for _ in range(5))
    fired.clear()
    tick(1.0)
    check(f'a second of everything hatching at once made {len(fired)} sounds, not hundreds',
          len(fired) <= 6)
    settings['enable_ground_hatching'] = False


run_game(run_checks)
finish('test_tally')
