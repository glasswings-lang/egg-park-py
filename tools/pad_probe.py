# SPDX-License-Identifier: CC0-1.0
"""What is your controller actually sending?

Prints what the pad reports, ten times a second, for fifteen seconds. Push
the sticks, squeeze the triggers, press the buttons. Nothing about the game
is involved: this only asks the controller what it thinks its own state is.

    python tools/pad_probe.py

Written for the question "I don't think the run thing on the controller
works" — running is the right trigger, and the only way to know whether the
trigger is reaching the game is to watch the number it sends.
"""
import time

import pyglet


def main():
    controllers = pyglet.input.get_controllers()
    if not controllers:
        print('No controller found. Is it plugged in?')
        return
    pad = controllers[0]
    pad.open()
    print(f'Watching {pad.name} for 15 seconds.')
    print('Squeeze the RIGHT TRIGGER (that is run), push the sticks, press buttons.')
    print('Anything over 0.15 on a trigger counts as pulled.\n')

    buttons = ('a', 'b', 'x', 'y', 'leftshoulder', 'rightshoulder',
               'start', 'back', 'leftstick', 'rightstick')
    seen_buttons = set()
    biggest_right = 0.0
    biggest_left = 0.0
    end = time.monotonic() + 15.0
    while time.monotonic() < end:
        pyglet.clock.tick()
        rt = pad.righttrigger
        lt = pad.lefttrigger
        biggest_right = max(biggest_right, rt)
        biggest_left = max(biggest_left, lt)
        for name in buttons:
            if getattr(pad, name, False):
                seen_buttons.add(name)
        print(f'  left stick {pad.leftx:+.2f},{pad.lefty:+.2f}   '
              f'right stick {pad.rightx:+.2f},{pad.righty:+.2f}   '
              f'triggers L {lt:.2f} R {rt:.2f}'
              f'{"   RUNNING" if rt > 0.15 else ""}')
        time.sleep(0.1)

    pad.close()
    print(f'\nHighest the right trigger reached: {biggest_right:.2f} '
          f'(needs to pass 0.15 to run)')
    print(f'Highest the left trigger reached:  {biggest_left:.2f}')
    print('Buttons that reported a press: '
          + (', '.join(sorted(seen_buttons)) if seen_buttons else 'none'))
    if biggest_right <= 0.15:
        print('\nThe right trigger never got above the line, so running would '
              'never start. That is the bug, and it is in the reading, not in you.')


if __name__ == '__main__':
    main()
