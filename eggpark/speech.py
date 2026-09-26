# SPDX-License-Identifier: CC0-1.0
"""Speaking through the screen reader, and the play log that records it."""
import os
import time

from eggpark import config

try:
    from accessible_output2 import outputs
    _speech = outputs.auto.Auto()
except Exception as exc:
    print(f'[warning] accessible_output2 unavailable: {exc}')
    _speech = None


# ============================================================================
# Play log
# ============================================================================
#
# play-log.txt, next to main.py: everything the game said aloud, and the
# numbers behind it at each moment that matters (finds, pickups, refusals,
# deposits, new parks). The previous session's log is kept as
# play-log-previous.txt.
#
# It exists so a bug noticed while PLAYING can be tracked down without the
# player having to catch it by ear, in a busy park, and report it exactly.
# Play normally; the log is read afterwards. Timestamps are seconds since the
# game opened.

# Tests set EGG_PARK_PLAY_LOG so running them never rotates away a real
# session's log before it has been read.
PLAY_LOG_FILE = (os.environ.get('EGG_PARK_PLAY_LOG')
                 or os.path.join(config._script_dir, 'play-log.txt'))
_play_log = None
_play_log_start = time.monotonic()


def _open_play_log():
    global _play_log
    try:
        previous = PLAY_LOG_FILE.replace('.txt', '-previous.txt')
        if os.path.isfile(PLAY_LOG_FILE):
            os.replace(PLAY_LOG_FILE, previous)
        _play_log = open(PLAY_LOG_FILE, 'w', encoding='utf-8', buffering=1)
        _play_log.write(f'Egg Park play log, {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
    except Exception as exc:
        print(f'[play log] could not open: {exc}')
        _play_log = None


def log_event(text):
    """One line in the play log. Never raises: a log must not break the game."""
    if _play_log is None:
        return
    try:
        _play_log.write(f'{time.monotonic() - _play_log_start:9.2f}  {text}\n')
    except Exception:
        pass


# crash-log.txt, next to main.py. The game runs under pythonw, which has no
# console, so a crash used to take the window away and leave NOTHING behind:
# no message, no traceback, nowhere to look. The one crash that prompted this
# (Space, with hundreds of eggs in range) was invisible from the inside.
#
# Appended to rather than replaced, and stamped, so a crash that only happens
# once in a while builds a history instead of overwriting the last one.
CRASH_LOG_FILE = (os.environ.get('EGG_PARK_CRASH_LOG')
                  or os.path.join(config._script_dir, 'crash-log.txt'))


def log_crash(text):
    """Write a crash to crash-log.txt and the play log. Never raises: this
    runs while the game is already falling over."""
    log_event('CRASH: ' + text.replace('\n', ' | '))
    try:
        with open(CRASH_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f'\n===== {time.strftime("%Y-%m-%d %H:%M:%S")} =====\n{text}\n')
    except Exception as exc:
        print(f'[crash log] could not write: {exc}')


# Each new line cuts off the one before it. NVDA queues otherwise, and a busy
# park queued so much that pressing a key meant waiting through a backlog of
# old news before hearing the answer: "I can't scroll down the list, I can't
# do anything" (25 Sep 2026). Lines spoken within SAY_TOGETHER seconds of
# each other are one moment, though, and queue: the chest list's opening line
# and its first chest are said together, not one cutting the other off.
SAY_TOGETHER = 0.25
_last_said_at = -1e9


def say(text):
    """Speak a line via the user's screen reader, interrupting older speech."""
    global _last_said_at
    log_event(f'said: {text}')
    now = time.monotonic()
    interrupt = now - _last_said_at > SAY_TOGETHER
    _last_said_at = now
    if _speech:
        try:
            _speech.speak(text, interrupt=interrupt)
        except TypeError:
            _speech.speak(text)
