# SPDX-License-Identifier: CC0-1.0
"""Saving and loading the park."""
import json
import os
import threading
import time

import pyglet

from eggpark import config, game, menu, sounds, speech, state, world

# ============================================================================
# Saving the park
# ============================================================================
#
# park.json, next to main.py. Without it, closing the game threw the whole
# park away: every basket found, every egg in them, every bird, and your
# carrying capacity with it. Which looked exactly like "finding baskets
# doesn't raise capacity", because the next session started from zero.
#
# Saved every PARK_AUTOSAVE_INTERVAL seconds while playing, whenever the menu
# opens, and on quitting (menu or window close). Written to a .tmp first and
# swapped in, so a crash mid-save leaves the last good save rather than half
# a file.
#
# Timers are saved as time LEFT, not as clock readings: the clock restarts
# with the game, so an absolute time would be meaningless next session. Time
# doesn't pass while the game is closed: an egg in your hand is exactly as
# close to hatching as when you left.
#
# Starting a new park over a saved one takes Enter twice, and the old save is
# kept as park-previous.json. It's hours of collecting, one key from gone.

PARK_SAVE_FILE = (os.environ.get('EGG_PARK_SAVE')
                  or os.path.join(config._script_dir, 'park.json'))
PARK_PREVIOUS_FILE = PARK_SAVE_FILE.replace('.json', '-previous.json')
PARK_BROKEN_FILE = PARK_SAVE_FILE.replace('.json', '-unreadable.json')
PARK_SAVE_VERSION = 1
PARK_AUTOSAVE_INTERVAL = 30.0

_next_autosave_at = 0.0
_new_park_armed = False


def _park_to_dict():
    t = time.monotonic()
    return {
        'version': PARK_SAVE_VERSION,
        'player': dict(state.player),
        'held': [dict(h) for h in state.held],
        'eggs': [dict(e) for e in state.eggs],
        'baskets': [dict(b, eggs=[dict(e) for e in b['eggs']]) for b in state.baskets],
        # gifts copied too: an autosave is written on another thread, so
        # nothing it holds may be a list the game is still changing.
        'chests': [dict(c, eggs=[dict(e) for e in c['eggs']],
                        **({'gifts': list(c['gifts'])} if 'gifts' in c else {}))
                   for c in state.chests],
        'progress': dict(state.progress),
        'birds': [dict(bird,
                       next_call_at=bird['next_call_at'] - t,
                       next_ambient_at=bird['next_ambient_at'] - t)
                  for bird in state.birds],
    }


# THE AUTOSAVE FROZE THE GAME. 28 Oct 2026: a park of half a million eggs
# took 3.4 seconds to write with indent=1 (pure-Python encoder), and the whole
# game stopped while it did, every 30 seconds. That was the stutter, and the
# lurch after it walked you straight past baskets. Now the save is compact
# (the fast encoder, 0.9 s for the same park), and an autosave copies the park
# on this thread (about 0.1 s) and writes it on another, a slice at a time so
# the game keeps getting its turn. Menu and quit saves still wait for it.
# Each slice is one call into the C encoder, which holds the interpreter until
# it is done, so the game cannot run during it. At 2000 eggs a slice that was
# 5 ms, and frames during a save went to 50-60 ms. At 300 it is under 1 ms,
# and the writer sleeps between slices so the game always gets the next turn.
SAVE_SLICE = 300    # eggs/birds encoded per slice by the background writer
SAVE_YIELD = 0.001  # seconds the background writer steps aside between slices

_save_thread = None


def _write_park(data, path, pause=0.0):
    """Compact JSON, long lists written a slice at a time. Each slice is one
    quick call to the fast encoder, so a writer on another thread lets go
    between slices (sleeping `pause`) and the game never waits on the whole
    park at once."""
    tmp = path + '.tmp'
    enc = json.JSONEncoder(separators=(',', ':')).encode
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('{')
        for i, (k, v) in enumerate(data.items()):
            f.write((',' if i else '') + enc(k) + ':')
            if isinstance(v, list) and len(v) > SAVE_SLICE:
                f.write('[')
                for start in range(0, len(v), SAVE_SLICE):
                    chunk = enc(v[start:start + SAVE_SLICE])[1:-1]
                    f.write((',' if start else '') + chunk)
                    if pause:
                        time.sleep(pause)
                f.write(']')
            else:
                f.write(enc(v))
        f.write('}')
    os.replace(tmp, path)


def _write_in_background(data, reason):
    try:
        started = time.perf_counter()
        _write_park(data, PARK_SAVE_FILE, pause=SAVE_YIELD)
        speech.log_event(f'park written ({reason}) in {time.perf_counter() - started:.1f}s')
    except Exception as exc:
        speech.log_event(f'COULD NOT SAVE PARK ({reason}): {exc}')
        print(f'[park] could not save: {exc}')


def wait_for_save():
    if _save_thread is not None:
        _save_thread.join()


def save_park(reason):
    """Write the park to disk. Never raises: failing to save must not end a
    session, but it must not be silent either."""
    global _next_autosave_at, _save_thread
    _next_autosave_at = game.now() + PARK_AUTOSAVE_INTERVAL
    if reason == 'autosave' and _save_thread is not None and _save_thread.is_alive():
        return   # the last one is still writing; the next autosave catches up
    try:
        data = _park_to_dict()
        if reason == 'autosave':
            _save_thread = threading.Thread(
                target=_write_in_background, args=(data, reason), daemon=True)
            _save_thread.start()
            return
        wait_for_save()
        _write_park(data, PARK_SAVE_FILE)
        world.log_counts(f'park saved ({reason})')
    except Exception as exc:
        speech.log_event(f'COULD NOT SAVE PARK ({reason}): {exc}')
        print(f'[park] could not save: {exc}')


def load_park():
    """Replace the current world with the saved one. True if it worked.

    On a save that can't be read, the world is left alone and the file is
    moved aside as park-unreadable.json rather than deleted or overwritten,
    so the next autosave can't destroy something that might be recoverable.
    """
    try:
        with open(PARK_SAVE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if data.get('version') != PARK_SAVE_VERSION:
            raise ValueError(f"save version {data.get('version')!r}")
        t = time.monotonic()
        new_player = {k: float(data['player'][k]) for k in ('x', 'y', 'z', 'yaw')}
        new_held = [dict(h) for h in data['held']]
        new_eggs = [dict(e) for e in data['eggs']]
        new_baskets = [dict(b, eggs=[dict(e) for e in b['eggs']])
                       for b in data['baskets']]
        # Parks saved before chests existed have neither; that's fine.
        new_chests = [dict(c, eggs=[dict(e) for e in c['eggs']])
                      for c in data.get('chests', [])]
        # Parks saved before nets existed have none.
        new_progress = {k: int(data.get('progress', {}).get(k, 0))
                        for k in ('carry_bonus', 'storage_bonus', 'nets')}
        new_birds = [dict(bird,
                          next_call_at=t + max(0.0, bird['next_call_at']),
                          next_ambient_at=t + max(0.0, bird['next_ambient_at']))
                     for bird in data['birds']]
    except Exception as exc:
        speech.log_event(f'COULD NOT LOAD PARK: {exc}')
        print(f'[park] could not load: {exc}')
        try:
            os.replace(PARK_SAVE_FILE, PARK_BROKEN_FILE)
        except Exception:
            pass
        return False
    world.reset_world()
    state.player.update(new_player)
    state.held.extend(new_held)
    state.eggs.extend(new_eggs)
    state.baskets.clear()
    state.baskets.extend(new_baskets)
    state.birds.extend(new_birds)
    state.chests.extend(new_chests)
    state.progress.update(new_progress)
    world._last_seen_counts.update(found=world.discovered_count(), carry=world.player_carry_cap())
    world.log_counts('park loaded')
    return True


def continue_saved_park():
    if not load_park():
        speech.say('Your saved park could not be read. It has been kept, renamed '
            'park unreadable. Starting a new park.')
        menu.start_game()
        return
    menu._in_main_menu = False
    menu._game_started = True
    sounds.fire_menu_close()
    sounds.update_listener()
    parts = [f'{world.discovered_count()} baskets found',
             f'{len(state.held)} of {world.player_carry_cap()} eggs held']
    if state.birds:
        parts.append(f'{len(state.birds)} bird{"s" if len(state.birds) != 1 else ""}')
    speech.say('Welcome back. ' + '. '.join(parts) + '.')


def confirm_new_park():
    """Enter once to hear what would be lost, Enter again to do it."""
    global _new_park_armed
    has_save = menu._game_started or os.path.isfile(PARK_SAVE_FILE)
    if has_save and not _new_park_armed:
        _new_park_armed = True
        speech.say('This replaces your park. The old one is kept as a backup. '
            'Press Enter again to start a new park.')
        return
    _new_park_armed = False
    if os.path.isfile(PARK_SAVE_FILE):
        try:
            import shutil
            shutil.copyfile(PARK_SAVE_FILE, PARK_PREVIOUS_FILE)
            speech.log_event('old park kept as backup before starting a new one')
        except Exception as exc:
            speech.log_event(f'COULD NOT BACK UP OLD PARK: {exc}')
    if menu._game_started:
        menu.restart_game()
    else:
        menu.start_game()


def quit_game():
    if menu._game_started:
        save_park('quit')
    pyglet.app.exit()


def tick_autosave():
    if menu._game_started and game.now() >= _next_autosave_at:
        save_park('autosave')
