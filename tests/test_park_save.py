# SPDX-License-Identifier: CC0-1.0
"""The park survives closing the game.

Run: python tests/test_park_save.py

Runs the real game several times over, as separate processes sharing one
save file, so "close and reopen" is tested for real rather than imitated.
Each session runs safely: see _game_harness.py.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def session(name):
    """One game session, run in a child process. Prints check lines."""
    import math
    import _game_harness
    from _game_harness import check, finish, run_game

    save = _game_harness.PARK_SAVE

    def checks(G):
        G['write_sounds_template'] = lambda *a, **k: False
        spoken = []
        real_say = G['say']
        G['say'] = lambda text: (spoken.append(text), real_say(text))
        first_item = G['main_menu_items']()[0][0]

        if name == 'play':
            check('no save yet: menu offers a fresh walk', first_item == 'Walk in the park')
            G['start_game']()
            check('starting a park saves it straight away', os.path.isfile(save))
            p = G['player']
            for _ in range(3):
                b = next(b for b in G['baskets'] if not b['discovered'])
                p.update(x=b['x'], y=b['y'])
                G['update'](1 / 60)
            egg = G['eggs'][0]
            p.update(x=egg['x'], y=egg['y'])
            G['update'](1 / 60)                       # picks it up
            found = next(b for b in G['baskets'] if b['discovered'])
            found['eggs'].append({'hatch_timer': 12.5, 'next_warning': 0.0})
            G['hatch_into_your_bird'](found)
            p.update(x=7.25, y=-3.5, yaw=1.25)
            check(f'played: 3 found, carrying 1 of 2, 1 bird '
                  f'(found {G["discovered_count"]()}, carry {len(G["held"])} of '
                  f'{G["player_carry_cap"]()}, birds {len(G["birds"])})',
                  G['discovered_count']() == 3 and G['player_carry_cap']() == 2
                  and len(G['held']) == 1 and len(G['birds']) == 1)
            before = os.path.getmtime(save)
            G['_next_autosave_at'] = 0.0
            G['update'](1 / 60)
            check('autosave writes while playing', os.path.getmtime(save) >= before
                  and json.load(open(save))['player']['x'] == 7.25)
            G['open_main_menu']()
            p.update(x=8.0)                           # moved after the menu save...
            G['pyglet'].app.exit = lambda: None
            G['quit_game']()                          # ...so only quitting saves this
            check('quitting saves', json.load(open(save))['player']['x'] == 8.0)

        elif name == 'reopen':
            check('reopened: menu offers to continue', first_item == 'Continue your park')
            check('nothing loaded until asked', G['discovered_count']() == 0)
            G['continue_saved_park']()
            b = [b for b in G['baskets'] if b['eggs']]
            bird = G['birds'][0] if G['birds'] else None
            t = G['time'].monotonic()
            check(f'finds came back (found {G["discovered_count"]()})', G['discovered_count']() == 3)
            check(f'THE BUG: carrying capacity came back '
                  f'({len(G["held"])} of {G["player_carry_cap"]()})',
                  G['player_carry_cap']() == 2 and len(G['held']) == 1)
            check('where you stood and faced came back',
                  (G['player']['x'], G['player']['y'], G['player']['yaw']) == (8.0, -3.5, 1.25))
            # 12.5 s when laid; it ticks down a little during the frames played.
            check('eggs in baskets came back with their time left',
                  len(b) == 1 and any(12.0 < e['hatch_timer'] <= 12.5 for e in b[0]['eggs']))
            check('the bird came back, with its next call soon, not in the past or far future',
                  bird is not None and t <= bird['next_call_at'] <= t + 20)
            check('welcome back says where you stand',
                  any('Welcome back. 3 baskets found. 1 of 2 eggs held. 1 bird.' in s for s in spoken))
            G['update'](1 / 60)
            G['open_main_menu']()
            items = [label for label, _ in G['main_menu_items']()]
            new_park = items.index('Start a new park')
            G['_main_menu_focus'] = new_park
            G['main_menu_activate']()
            check('new park needs a second Enter', G['discovered_count']() == 3
                  and 'Press Enter again' in spoken[-1])
            G['main_menu_focus_move'](+1)
            G['main_menu_focus_move'](-1)
            G['main_menu_activate']()
            check('moving away cancels it', G['discovered_count']() == 3)
            G['main_menu_activate']()
            check('second Enter starts fresh', G['discovered_count']() == 0)
            backup = save.replace('.json', '-previous.json')
            check('old park kept as a backup',
                  os.path.isfile(backup) and
                  sum(b['discovered'] for b in json.load(open(backup))['baskets']) == 3)
            check('save now holds the new park',
                  sum(b['discovered'] for b in json.load(open(save))['baskets']) == 0)

        elif name == 'broken':
            with open(save, 'w') as f:
                f.write('{ this is not a park')
            first_item = G['main_menu_items']()[0][0]
            check('a broken save still offers to continue', first_item == 'Continue your park')
            G['continue_saved_park']()
            unreadable = save.replace('.json', '-unreadable.json')
            check('broken save is kept aside, not overwritten',
                  open(unreadable).read() == '{ this is not a park')
            check('and a fresh park starts instead of a crash',
                  G['_game_started'] and G['discovered_count']() == 0
                  and any('could not be read' in s for s in spoken))

    run_game(checks)
    finish(f'session {name}')


if len(sys.argv) > 1:
    sys.path.insert(0, HERE)
    session(sys.argv[1])
    sys.exit(0)

shared = tempfile.mkdtemp(prefix='eggpark-save-test-')
env = dict(os.environ, EGG_PARK_TEST_DIR=shared)
failed = False
for name in ('play', 'reopen', 'broken'):
    print(f'{name}:')
    result = subprocess.run([sys.executable, os.path.abspath(__file__), name],
                            env=env, capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if line.startswith(('  ok', '  FAIL')) or 'Traceback' in line or 'Error' in line:
            print(line)
    if result.returncode != 0:
        failed = True
        print(result.stderr[-2000:])

real = os.path.join(os.path.dirname(HERE), 'park.json')
print('your own save:')
print('  ok   untouched' if not os.path.isfile(real) or
      os.path.getmtime(real) < os.path.getmtime(shared) else '  FAIL park.json changed')
if failed:
    print('\ntest_park_save: FAILED')
    sys.exit(1)
print('\ntest_park_save: all checks passed')
