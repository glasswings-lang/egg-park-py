# SPDX-License-Identifier: CC0-1.0
"""The chest list: G on the keyboard, the left trigger on a controller.

Every found chest, nearest first, full ones included, each saying what its
birds get; picking one starts the scan guide to it. The park keeps running
while it's open, because it's a scan, not a menu.

Run: python tests/test_chest_list.py

Runs the real game, safely: see _game_harness.py.
"""
import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import check, finish, run_game

import pyglet
from pyglet.window import key


class FakePad:
    name = 'test pad'

    def __init__(self):
        self.leftx = self.lefty = self.rightx = self.righty = 0.0
        self.lefttrigger = self.righttrigger = 0.0

    def open(self):
        pass

    def close(self):
        pass

    def push_handlers(self, **kw):
        pass


class Vec:
    def __init__(self, x, y):
        self.x, self.y = x, y


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False
    spoken = []
    G['say'] = spoken.append
    G['_play'] = lambda *a, **k: None
    settings = G['settings']
    settings['enable_ground_hatching'] = False
    player, chests = G['player'], G['chests']

    def press(symbol, modifiers=0):
        return G['on_key_press'](symbol, modifiers)

    def frames(n):
        for _ in range(n):
            G['update'](1 / 60)

    def guide():
        return G['_scan_guide']

    def chest_at(x, y, eggs=0, more=0, held=0):
        c = {'x': x, 'y': y, 'z': 0.0, 'discovered': True, 'eggs': [{'hatch_timer': 999.0}] * held,
             'gifts': [], 'clutch_bonus': eggs, 'extra_clutches': more}
        chests.append(c)
        return c

    G['start_game']()
    G['maybe_spawn_chest'] = lambda: None        # no surprise chests mid-test
    chests.clear()
    player.update(x=0.0, y=0.0, yaw=0.0)

    print('with no chests found:')
    spoken.clear()
    press(key.G)
    check(f'G says there are none ({spoken[-1]!r})', spoken[-1] == 'No chests found yet.')
    check('and nothing is left open', not G['is_open']())

    print('opening the list:')
    far = chest_at(120.0, 0.0, eggs=4, more=2)
    near = chest_at(30.0, 0.0)
    full = chest_at(0.0, 60.0, more=1)
    chests.append({'x': 10.0, 'y': 0.0, 'z': 0.0, 'discovered': False, 'eggs': [], 'gifts': [],
                   'clutch_bonus': 0, 'extra_clutches': 0})
    # Filled last: each chest found raises what every chest holds.
    full['eggs'] = [{'hatch_timer': 999.0}] * G['chest_cap']()
    spoken.clear()
    press(key.G)
    check('G opens it', G['is_open']())
    check(f'says how many, nearest first ({spoken[0]!r})', spoken[0].startswith('3 chests found, nearest first.'))
    check(f'and reads the nearest ({spoken[-1]!r})',
          spoken[-1].startswith('Chest, 30 metres.') and 'Plain birds.' in spoken[-1]
          and spoken[-1].endswith('1 of 3.'))
    press(key.DOWN)
    check(f'down reads the next: the full one, marked full ({spoken[-1]!r})',
          spoken[-1].startswith('Chest, 60 metres. Full,') and 'lay 1 more clutch.' in spoken[-1])
    press(key.DOWN)
    check(f'then the far one, with both bird gifts ({spoken[-1]!r})',
          'Birds here lay 4 more eggs a clutch and 2 more clutches.' in spoken[-1]
          and spoken[-1].endswith('3 of 3.'))
    press(key.DOWN)
    check('down again wraps round to the first', spoken[-1].startswith('Chest, 30 metres.'))
    press(key.UP)
    check('up goes back', spoken[-1].startswith('Chest, 120 metres.'))

    print('the park keeps running:')
    G['hatch_into_your_bird'](G['baskets'][0])
    bird = G['birds'][-1]
    before = bird['lay_timer']
    frames(60)
    check(f'birds keep counting down with it open ({before:.0f} -> {bird["lay_timer"]:.0f} s)',
          bird['lay_timer'] < before - 0.9)
    check('and it stays open', G['is_open']())
    x0 = player['x']
    G['keys'].on_key_press(key.W, 0)
    frames(60)
    G['keys'].on_key_release(key.W, 0)
    check(f'W still walks ({player["x"] - x0:.1f} m)', player['x'] - x0 > 1.0)
    check('the up arrow is the list\'s, not a step', press(key.UP) == pyglet.event.EVENT_HANDLED)

    print('picking one:')
    player.update(x=0.0, y=0.0)
    press(key.ESCAPE)
    check('Escape closes it, and does not open the main menu',
          not G['is_open']() and not G['_in_main_menu'])
    press(key.G)
    press(key.DOWN)                                # the full one
    spoken.clear()
    press(key.RETURN)
    check('Enter closes the list', not G['is_open']())
    check(f'and leads to the chest picked ({spoken[-1]!r})',
          guide() and guide()['target'] is full and spoken[-1] == 'Leading you to the chest, 60 metres.')
    frames(30)
    check('a full chest is still led to: you picked it', guide() and guide()['target'] is full)
    player.update(x=0.0, y=58.0)
    frames(2)
    check('the guide ends when you are on it', guide() is None)

    print('a far one is led to, however far:')
    player.update(x=0.0, y=0.0)
    far.update(x=900.0)
    press(key.G)
    press(key.UP)                                  # last in the list: the far one
    press(key.RETURN)
    frames(30)
    check('900 m away, still leading', guide() and guide()['target'] is far)
    far.update(x=120.0)
    G['stop_scan_guide']()

    print('G twice:')
    press(key.G)
    press(key.G)
    check(f'G again closes it ({spoken[-1]!r})', not G['is_open']() and spoken[-1] == 'Chest list closed.')

    print('menus and new parks close it:')
    press(key.G)
    G['open_main_menu']()
    check('opening the main menu closes it', not G['is_open']())
    G['resume_game']()
    press(key.G)
    G['open_settings']()
    check('opening settings closes it', not G['is_open']())
    G['close_settings']()
    press(key.G)
    G['reset_world']()
    check('a new park closes it', not G['is_open']())

    print('on a controller:')
    fake = FakePad()
    G['_controller'] = fake
    settings['enable_controller'] = True
    chests.clear()
    player.update(x=0.0, y=0.0)
    near = chest_at(30.0, 0.0)
    far = chest_at(120.0, 0.0, eggs=2)
    fake.lefttrigger = 1.0
    frames(1)
    check('pulling the left trigger opens it', G['is_open']())
    frames(30)
    check('holding it does not flicker it shut', G['is_open']())
    fake.lefttrigger = 0.0
    frames(1)
    check('letting go leaves it open', G['is_open']())
    G['_on_dpad'](fake, Vec(0, -1))
    check(f'D-pad down moves ({spoken[-1]!r})', spoken[-1].startswith('Chest, 120 metres.'))
    check('and does not start the unfound-basket scan', guide() is None)
    G['_on_dpad'](fake, Vec(0, 1))
    check('D-pad up moves back', spoken[-1].startswith('Chest, 30 metres.'))
    G['_on_button'](fake, 'b')
    check('B closes it', not G['is_open']())
    fake.lefttrigger = 1.0
    frames(1)
    fake.lefttrigger = 0.0
    frames(1)
    G['_on_dpad'](fake, Vec(0, -1))
    G['_on_button'](fake, 'a')
    check('A picks, and the guide leads there', not G['is_open']() and guide() and guide()['target'] is far)
    fake.lefttrigger = 1.0
    frames(1)
    fake.lefttrigger = 0.0
    frames(1)
    fake.lefttrigger = 1.0
    frames(1)
    check('a second pull closes it', not G['is_open']())
    fake.lefttrigger = 0.0
    frames(1)
    fake.lefty = 1.0
    x0 = player['x']
    fake.lefttrigger = 1.0
    frames(1)
    fake.lefttrigger = 0.0
    frames(60)
    check(f'the left stick still walks with it open ({abs(player["x"] - x0):.1f} m)',
          G['is_open']() and abs(player['x'] - x0) > 1.0)
    fake.lefty = 0.0
    check('the controller help mentions it', 'left trigger lists every chest' in G['PAD_HELP'])
    G['_controller'] = None


run_game(run_checks)
finish('test_chest_list')
