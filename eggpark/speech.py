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


def say(text):
    """Speak a line via the user's screen reader."""
    log_event(f'said: {text}')
    if _speech:
        _speech.speak(text)
