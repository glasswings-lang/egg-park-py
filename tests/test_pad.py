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
import inspect
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

    # Speed builds (see test_speed.py), so every measured walk starts from a
    # standstill and expects top * T minus the ramp.
    def walk_for(seconds):
        G['_speed'] = 0.0
        player.update(x=0.0, y=0.0, yaw=0.0)
        frames(int(seconds * 60))
        return math.hypot(player['x'], player['y'])

    def expected(top, seconds):
        return top * seconds - top * top / (2 * G['ACCELERATION'])

    # THE CHECK THAT WOULD HAVE CAUGHT THE CRASH.
    #
    # The first version of this file crashed the game the moment a pad was
    # plugged in, because _on_dpad was written to take four booleans and
    # pyglet sends one vector — and the old test called the handler with four
    # booleans too, so it passed. A test that agrees with the code about a
    # thing they both got wrong is worse than no test.
    #
    # pyglet declares the shape of each event as a stub method on
    # Controller, so that is the thing to measure against, not my memory.
    from pyglet.input.base import Controller, ControllerManager
    for source, event, handler in (
            (Controller, 'on_dpad_motion', G['_on_dpad']),
            (Controller, 'on_button_press', G['_on_button']),
            (ControllerManager, 'on_connect', G['_on_connect']),
            (ControllerManager, 'on_disconnect', G['_on_disconnect'])):
        theirs = [p for p in inspect.signature(getattr(source, event)).parameters
                  if p != 'self']
        ours = list(inspect.signature(handler).parameters)
        check(f'{handler.__name__} matches pyglet {event}{tuple(theirs)}: {tuple(ours)}',
              len(ours) == len(theirs))

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
    check(f'fully forward walks at the walk speed ({full:.2f} m in a second, '
          f'{expected(2.0, 1):.2f} expected with the ramp)',
          abs(full - expected(2.0, 1)) < 0.05)
    check(f'half forward is slower, not the same ({half:.2f} m)', 0.1 < half < full * 0.8)
    fake.lefty = -1.0
    player.update(x=0.0, y=0.0, yaw=0.0)
    frames(60)
    check(f'back on the stick walks backwards ({player["x"]:.2f} m)', player['x'] < -1.5)  # noqa: E501
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
          abs(ran - expected(5.0, 1)) < 0.1 and walked < ran)
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
    # B is decided on release now: a tap deposits everything, a hold pours.
    press('b')
    check('B pressed does nothing yet: tap or hold is decided on release', fired == [])
    G['_on_release'](fake, 'b')
    check('B tapped deposits', fired == ['try_deposit'])
    check('X says your status', press('x') == ['announce_status'])
    check('Start opens the menu', press('start') == ['open_main_menu'])
    check('Back opens settings', press('back') == ['open_settings'])
    fired.clear()
    G['_on_button'](fake, 'y')
    G['_on_release'](fake, 'y')
    check(f'tapping Y reads out the controller controls ({spoken[-1][:28]!r}...)',
          'Left stick walks' in spoken[-1])

    print('the D-pad leads you places:')

    # pyglet sends ONE Vec2: x is -1 left / +1 right, y is -1 down / +1 up.
    # Calling the handler any other way is testing my memory of the library
    # rather than the library, which is how this shipped broken once.
    from pyglet.math import Vec2

    def dpad(x=0.0, y=0.0):
        fired.clear()
        G['_on_dpad'](fake, Vec2(x, y))
        return fired

    check('up: a basket you have found', dpad(y=1) == ['try_scan_found_baskets'])
    check('down: a basket you have not', dpad(y=-1) == ['try_scan_unfound_baskets'])
    check('right: a chest you have found', dpad(x=1) == ['try_scan_found_chests'])
    check('left: a chest you have not', dpad(x=-1) == ['try_scan_unfound_chests'])
    check('letting go does nothing', dpad() == [])

    print('holding Y asks questions instead, like Periphery does:')
    for name in ('announce_heading', 'announce_carrying', 'announce_park'):
        real[name] = G[name]
        G[name] = (lambda n: lambda *a, **k: fired.append(n))(name)
    G['_on_button'](fake, 'y')                 # held
    check('Y and up: which way am I facing', dpad(y=1) == ['announce_heading'])
    check('Y and down: what am I carrying', dpad(y=-1) == ['announce_carrying'])
    check('Y and left: what is in this park', dpad(x=-1) == ['announce_park'])
    check('Y and right: everything', dpad(x=1) == ['announce_status'])
    spoken.clear()
    G['_on_release'](fake, 'y')
    check('and letting Y go after using it does NOT also read the controls',
          not spoken)
    check('with Y let go, the D-pad leads you places again',
          dpad(y=1) == ['try_scan_found_baskets'])

    print('run is a toggle on the left stick click:')
    G['forget_run']()
    settings['walk_speed'] = 2.0
    settings['run_speed'] = 5.0
    spoken.clear()
    G['_on_button'](fake, 'leftstick')
    check(f'clicking it says so ({spoken[-1]!r})', spoken[-1] == 'Running.')
    check('and the pad reports running with nothing held', G['read']()[3] is True)
    fake.lefty = 1.0
    latched = walk_for(1)
    check(f'so you run without holding anything ({latched:.1f} m in a second, '
          f'{expected(5.0, 1):.1f} expected with the ramp)',
          abs(latched - expected(5.0, 1)) < 0.1)
    G['_on_button'](fake, 'leftstick')
    unlatched = walk_for(1)
    check(f'clicking again walks ({spoken[-1]!r}, {unlatched:.1f} m against '
          f'{latched:.1f} running)',
          spoken[-1] == 'Walking.' and abs(unlatched - expected(2.0, 1)) < 0.1)
    G['_on_button'](fake, 'leftstick')
    G['reset_world']()
    check('and a new park never starts you running', G['read']()[3] is False)
    fake.lefty = 0.0

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
    G['_on_dpad'](fake, Vec2(0.0, 1.0))
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
    G['_speed'] = 0.0                          # not coasting from the last check
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
    check(f'W still walks at the walk speed ({by_key:.2f} m in a second)',
          abs(by_key - expected(2.0, 1)) < 0.05)

    G['_controller'] = None


run_game(run_checks)
finish('test_pad')
