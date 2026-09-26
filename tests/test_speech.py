# SPDX-License-Identifier: CC0-1.0
"""Speech cuts itself off, except within one moment.

NVDA queues whatever it is given. In a busy park that meant pressing a key
and waiting through a backlog of old lines before hearing the answer. Now
each line interrupts the last, unless they come within SAY_TOGETHER seconds
of each other, which is one moment said in parts.

Run: python tests/test_speech.py
"""
import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import check, finish, run_game


class FakeReader:
    def __init__(self):
        self.calls = []

    def speak(self, text, interrupt=False):
        self.calls.append((text, interrupt))


def run_checks(G):
    import time
    reader = FakeReader()
    G['_speech'] = reader
    say = G['say']
    time.sleep(G['SAY_TOGETHER'] + 0.1)     # clear of the game's own startup line
    say('first')
    check('a line on its own interrupts', reader.calls[-1] == ('first', True))
    say('second, straight after')
    check('a line in the same moment queues behind it', reader.calls[-1] == ('second, straight after', False))
    time.sleep(G['SAY_TOGETHER'] + 0.1)
    say('later')
    check('a line after a pause cuts off the one before', reader.calls[-1] == ('later', True))

    class OldReader:
        def __init__(self):
            self.said = []

        def speak(self, text):
            self.said.append(text)
    old = OldReader()
    G['_speech'] = old
    time.sleep(G['SAY_TOGETHER'] + 0.1)
    say('still heard')
    check('a reader with no interrupt option still speaks', old.said == ['still heard'])
    G['_speech'] = None


run_game(run_checks)
finish('test_speech')
