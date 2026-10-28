# SPDX-License-Identifier: CC0-1.0
"""F1 in the sound test: the Windows Open dialog, Preview on Alt+P, and the
choice written into sounds.txt and loaded.

Run: python tests/test_choose_recording.py

Runs the real game, safely: see _game_harness.py. The dialog is the real one,
on the hidden desktop with the game window. Nobody is there to press its
buttons, so a timer does, from inside the dialog's own message loop: the
dialog is modal, and the game is blocked in it exactly as it would be with a
person at the keyboard.
"""
import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import TEST_DIR, check, finish, run_game

import ctypes
import math
import os
import struct
import threading
import time
import wave
from ctypes import wintypes

from pyglet.window import key

user32 = ctypes.WinDLL('user32', use_last_error=True)
user32.FindWindowW.restype = wintypes.HWND
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.EnumDesktopWindows.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.LPARAM]
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
WM_COMMAND, BM_CLICK, IDOK, IDCANCEL = 0x0111, 0x00F5, 1, 2


def _watchdog():
    # A dialog nobody closes would hang the suite for ever. Better a loud end.
    time.sleep(90)
    print('  FAIL the file dialog was still open after 90 seconds', flush=True)
    os._exit(1)


threading.Thread(target=_watchdog, daemon=True).start()


def make_wav(path):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b''.join(struct.pack('<h', int(8000 * math.sin(i / 20)))
                               for i in range(4800)))


def text_of(h):
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(h, buf, 512)
    return buf.value


def preview_button(dialog_hwnd):
    kids = []
    user32.EnumChildWindows(dialog_hwnd, WNDENUMPROC(lambda h, _: kids.append(h) or True), 0)
    found = [h for h in kids if text_of(h) == '&Preview']
    return found[0] if found else None


def find_dialog():
    """The dialog's window on the hidden desktop, or None. Found by listing the
    desktop rather than FindWindow, which only searches the caller's own."""
    import _isolated_desktop
    from eggpark import filepick
    found = []
    user32.EnumDesktopWindows(
        _isolated_desktop._HANDLE,
        WNDENUMPROC(lambda h, _: (text_of(h) == filepick.TITLE and found.append(h)) or True), 0)
    return found[0] if found else None


def drive(G, steps):
    """Press F1 and play the person at the dialog: each step is fn(dialog_hwnd),
    run in turn from a second thread once the dialog is up. Returns its title.

    A second thread, because the game's thread is inside the dialog until it
    closes. A timer on that thread never fired while the game window was there
    with it, so the steps are sent in as window messages from outside instead,
    which is what a keyboard does anyway.
    """
    titles = []

    def person():
        dlg = None
        for _ in range(100):
            dlg = find_dialog()
            if dlg:
                break
            time.sleep(0.1)
        if not dlg:
            return
        titles.append(text_of(dlg))
        time.sleep(0.5)                 # let it finish laying out
        for step in steps:
            step(dlg)
            time.sleep(0.4)

    helper = threading.Thread(target=person)
    helper.start()
    G['on_key_press'](key.F1, 0)
    helper.join()
    return titles


def type_into_file_name(dlg, text):
    """Type into the File name box a key at a time, as a keyboard would."""
    kids = []
    user32.EnumChildWindows(dlg, WNDENUMPROC(lambda h, _: kids.append(h) or True), 0)
    buf = ctypes.create_unicode_buffer(64)
    edits = [h for h in kids if user32.GetDlgCtrlID(h) == 0x47C
             and user32.GetClassNameW(h, buf, 64) and buf.value == 'Edit']
    for ch in text:
        user32.SendMessageW(edits[0], 0x0102, ord(ch), 0)          # WM_CHAR


def run_checks(G):
    from eggpark import filepick, soundtest
    take = os.path.join(TEST_DIR, 'my step.wav')
    make_wav(take)

    spoken, played = [], []
    G['say'] = spoken.append
    real_play = G['_play']

    def record(source, **k):
        played.append(k.get('category'))
        return real_play(source, **k)

    G['_play'] = record

    soundtest.open_sound_test()
    cues = [c for c, *_ in G['SOUND_CATALOGUE']]
    G['_sound_test_focus'] = cues.index('footstep')

    print('choosing a recording:')
    spoken.clear()
    played.clear()                      # opening the sound test chimed

    def type_path(dlg):
        type_into_file_name(dlg, take)

    def press_preview(dlg):
        user32.SendMessageW(preview_button(dlg), BM_CLICK, 0, 0)

    def press_open(dlg):
        user32.PostMessageW(dlg, WM_COMMAND, IDOK, 0)

    def playing(category):
        # Under the harness sounds go the player-per-sound way (silent driver).
        return sum(1 for p in G['_active_players']
                   if getattr(p, '_eggpark_category', None) == category)

    during = []

    def count_footsteps(dlg):
        during.append(playing('footstep'))

    titles = drive(G, [type_path, press_preview, press_preview, count_footsteps, press_open])
    check(f'F1 opens the dialog, titled {titles[0] if titles else None!r}',
          titles == [filepick.TITLE])
    check(f'Preview played the file as a footstep ({played})',
          played == ['footstep', 'footstep'])
    check(f'Preview pressed twice: one playing, not two over each other ({during})',
          during == [1])
    check('and the preview stops when the dialog closes', playing('footstep') == 0)
    check('the choice is written into sounds.txt',
          f'footstep = {take}' in open(G['SOUNDS_LIST_FILE'], encoding='utf-8').read())
    check('and loaded at once, no R needed',
          G['has_recording']('footstep') and G['sound_list_path_for']('footstep') == take)
    check(f'and said: {spoken[-1] if spoken else None!r}',
          spoken[-1:] == ['Footstep set to my step.wav.'])
    check('no "window lost focus" over the dialog',
          not any('focus' in s.lower() for s in spoken))

    print('cancelling, and Preview with nothing chosen:')
    spoken.clear()
    played.clear()
    before = open(G['SOUNDS_LIST_FILE'], encoding='utf-8').read()

    def press_cancel(dlg):
        user32.PostMessageW(dlg, WM_COMMAND, IDCANCEL, 0)

    drive(G, [press_preview, press_cancel])
    check('Preview with nothing selected says so, and plays nothing',
          played == [] and any(s.startswith('Nothing to play') for s in spoken))
    check(f'Cancel says so: {spoken[-1] if spoken else None!r}',
          spoken[-1:] == ['Cancelled. Footstep is unchanged.'])
    check('and sounds.txt is untouched',
          open(G['SOUNDS_LIST_FILE'], encoding='utf-8').read() == before)

    print('the sound test plays one sound at a time:')
    G['_sound_test_focus'] = cues.index('wind')
    G['on_key_press'](key.RETURN, 0)
    G['on_key_press'](key.RETURN, 0)
    check(f'Enter twice on the wind: one wind playing ({playing("wind")})', playing('wind') == 1)
    G['on_key_press'](key.DOWN, 0)
    check('Down stops it, so it does not run on under the next sound', playing('wind') == 0)
    G['on_key_press'](key.RETURN, 0)
    G['on_key_press'](key.UP, 0)
    check('Up does too', playing(cues[cues.index('wind') + 1]) == 0)
    G['on_key_press'](key.RETURN, 0)
    G['on_key_press'](key.ESCAPE, 0)
    check('and so does leaving the sound test', playing('wind') == 0)
    soundtest.open_sound_test()

    print('the one sound that cannot be replaced here:')
    spoken.clear()
    G['_sound_test_focus'] = cues.index('egg-warning')
    G['on_key_press'](key.F1, 0)
    check('the egg warning is two sounds, and F1 says so instead of opening',
          len(spoken) == 1 and 'two sounds' in spoken[0])


run_game(run_checks)
finish('test_choose_recording')
