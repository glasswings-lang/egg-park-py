# SPDX-License-Identifier: CC0-1.0
"""Playing on a controller: analog sticks, the button map, and menus.

The keyboard hurts to play on for long, and holding a turn key is
all-or-nothing, so every correction overshoots. A stick is analog: a small
push is a small turn. These checks drive a stand-in controller, because the
maths and the mapping are what can be wrong in code — whether it FEELS right
is for the person holding the pad.

Run: python tests/test_pad.py

Runs the real game, safely: see _game_harness.py.
"""
import math

import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import check, finish, run_game


class FakePad:
    """A controller at rest, whose sticks a test can push."""

    name = 'test pad'

    def __init__(self):
        self.leftx = self.lefty = 0.0
        self.rightx = self.righty = 0.0
        self.lefttrigger = self.righttrigger = 0.0

    def open(self):
        pass

    def close(self):
        pass

    def push_handlers(self, **kw):
        pass


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False
    spoken = []
    G['say'] = spoken.append
    G['_play'] = lambda *a, **k: None
    settings = G['settings']
    player = G['player']

    fake = FakePad()
    G['_controller'] = fake                     # stand in for a real pad
    settings['enable_controller'] = True
    G['start_game']()
    G['eggs'].clear()
    check('the game knows a pad is there', G['connected']())

    def frames(n, dt=1 / 60):
        for _ in range(n):
            G['update'](dt)

    def walk_for(seconds):
        player.update(x=0.0, y=0.0, yaw=0.0)
        frames(int(seconds * 60))
        return math.hypot(player['x'], player['y'])

    print('the deadzone:')
    fake.leftx = fake.lefty = 0.0
    moved = walk_for(1)
    check(f'a stick at rest does not move you ({moved:.3f} m)', moved < 1e-9)
    fake.lefty = G['PAD_DEADZONE'] * 0.9
    check(f'nor does a push inside the deadzone ({G["PAD_DEADZONE"]:.2f})', walk_for(1) < 1e-9)

    print('how far you push is how fast you go:')
    settings['walk_speed'] = 2.0
    fake.lefty = 1.0
    full = walk_for(1)
    fake.lefty = 0.5
    half = walk_for(1)
    check(f'fully forward walks at the walk speed ({full:.2f} m in a second)',
          abs(full - 2.0) < 0.05)
    check(f'half forward is slower, not the same ({half:.2f} m)', 0.1 < half < full * 0.8)
    fake.lefty = -1.0
    player.update(x=0.0, y=0.0, yaw=0.0)
    frames(60)
    check(f'back on the stick walks backwards ({player["x"]:.2f} m)', player['x'] < -1.5)
    fake.lefty = 0.0
    fake.leftx = 1.0
    player.update(x=0.0, y=0.0, yaw=0.0)
    frames(60)
    check(f'the stick sideways strafes ({player["x"]:.2f}, {player["y"]:.2f})',
          abs(player['x']) < 0.2 and player['y'] < -1.5)
    fake.leftx = 0.0

    print('and the same for turning, which is the point:')
    settings['turn_speed'] = math.pi / 2
    fake.rightx = 1.0
    player.update(yaw=0.0)
    frames(60)
    hard = player['yaw']
    fake.rightx = 0.25
    player.update(yaw=0.0)
    frames(60)
    gentle = player['yaw']
    check(f'right on the stick turns right ({math.degrees(hard):.0f} degrees a second)',
          hard < -1.0)
    check(f'a quarter push turns far less ({math.degrees(gentle):.0f} degrees against '
          f'{math.degrees(hard):.0f})', -0.2 < gentle < 0.0)
    check('the curve bends it, so small pushes are gentler than their share',
          abs(gentle) < abs(hard) * 0.25)
    fake.rightx = -1.0
    player.update(yaw=0.0)
    frames(60)
    check(f'and left on the stick turns left ({math.degrees(player["yaw"]):.0f} degrees)',
          player['yaw'] > 1.0)
    fake.rightx = 0.0

    print('the right trigger runs:')
    settings['run_speed'] = 5.0
    fake.lefty = 1.0
    fake.righttrigger = 1.0
    ran = walk_for(1)
    fake.righttrigger = 0.0
    walked = walk_for(1)
    check(f'held, you run ({ran:.1f} m a second against {walked:.1f} walking)',
          abs(ran - 5.0) < 0.1 and walked < ran)
    fake.lefty = 0.0

    print('the buttons:')
    fired = []
    real = {}
    for name in ('try_scan', 'try_deposit', 'announce_status', 'try_scan_found_baskets',
                 'try_scan_unfound_baskets', 'try_scan_found_chests',
                 'try_scan_unfound_chests', 'open_settings', 'open_main_menu'):
        real[name] = G[name]
        G[name] = (lambda n: lambda *a, **k: fired.append(n))(name)

    def press(button):
        fired.clear()
        G['_on_button'](fake, button)
        return fired

    check('A scans', press('a') == ['try_scan'])
    check('B deposits', press('b') == ['try_deposit'])
    check('X says your status', press('x') == ['announce_status'])
    check('Start opens the menu', press('start') == ['open_main_menu'])
    check('Back opens settings', press('back') == ['open_settings'])
    fired.clear()
    G['_on_button'](fake, 'y')
    check(f'Y reads out the controller controls ({spoken[-1][:28]!r}...)',
          'Left stick walks' in spoken[-1])

    print('the D-pad leads you places:')

    def dpad(left=False, right=False, up=False, down=False):
        fired.clear()
        G['_on_dpad'](fake, left, right, up, down)
        return fired

    check('up: a basket you have found', dpad(up=True) == ['try_scan_found_baskets'])
    check('down: a basket you have not', dpad(down=True) == ['try_scan_unfound_baskets'])
    check('right: a chest you have found', dpad(right=True) == ['try_scan_found_chests'])
    check('left: a chest you have not', dpad(left=True) == ['try_scan_unfound_chests'])
    check('letting go does nothing', dpad() == [])

    print('volume, on the bumpers:')
    settings['master_volume'] = 1.0
    G['_on_button'](fake, 'leftshoulder')
    down = settings['master_volume']
    G['_on_button'](fake, 'rightshoulder')
    G['_on_button'](fake, 'rightshoulder')
    check(f'left lowers it ({down:.1f}) and right raises it ({settings["master_volume"]:.1f})',
          down < 1.0 < settings['master_volume'])
    settings['master_volume'] = 1.0

    print('in a menu, the pad still works:')
    moves = []
    G['main_menu_focus_move'] = moves.append
    picked = []
    G['main_menu_activate'] = lambda: picked.append(1)
    G['open_main_menu'] = real['open_main_menu']        # the real one again
    G['open_main_menu']()
    G['_on_dpad'](fake, False, False, True, False)
    check(f'D-pad up moves the focus up ({moves!r})', moves == [-1])
    G['_on_button'](fake, 'a')
    check('A picks the item', picked == [1])
    # The stick moves through a menu too, one step per push rather than sixty
    # a second, or the list runs past you while you hold it.
    moves.clear()
    fake.lefty = 1.0
    frames(30)
    check(f'holding the stick up is ONE step, not thirty ({moves!r})', moves == [-1])
    fake.lefty = 0.0
    frames(2)
    fake.lefty = 1.0
    frames(2)
    check(f'letting go and pushing again is another step ({moves!r})', moves == [-1, -1])
    fake.lefty = 0.0

    print('switching it off:')
    settings['enable_controller'] = False
    fake.lefty = 1.0
    fake.rightx = 1.0
    G['resume_game']()
    player.update(x=0.0, y=0.0, yaw=0.0)
    frames(60)
    check('with Controller off, a pushed stick does nothing',
          abs(player['x']) < 1e-9 and abs(player['yaw']) < 1e-9)
    settings['enable_controller'] = True

    print('and the keyboard is untouched:')
    from pyglet.window import key
    fake.lefty = fake.rightx = 0.0
    keys = G['keys']
    keys.on_key_press(key.W, 0)
    settings['walk_speed'] = 2.0
    by_key = walk_for(1)
    keys.on_key_release(key.W, 0)
    check(f'W still walks at the full walk speed ({by_key:.2f} m in a second)',
          abs(by_key - 2.0) < 0.05)

    G['_controller'] = None


run_game(run_checks)
finish('test_pad')
