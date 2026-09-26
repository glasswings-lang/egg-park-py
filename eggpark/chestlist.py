# SPDX-License-Identifier: CC0-1.0
"""The chest list: every chest you've found, and what its birds get.

WHY. Chests roll four kinds of gift in fifteen mixes, and two of them belong
to the chest itself: birds hatched there lay bigger clutches, or more of
them. "Lead me to the nearest found chest" (C, D-pad right) can't tell those
apart, so this lists them all, nearest first, and says what each one gives.
Pick one and the scan guide leads you there.

IT IS A SCAN, NOT A MENU. The park keeps running while it's open: eggs keep
counting down, birds keep laying, and you can keep walking. That was
Rozaya's call, 25 Sep 2026. So only the keys it needs are taken while it's
open, and everything else still reaches the park:
  keyboard    G opens and closes it. Up and Down arrows choose, Enter picks,
              Escape closes. W A S D and turning still work.
  controller  Left trigger opens and closes it. D-pad up and down choose,
              A picks, B closes. The sticks still walk and turn.

FULL CHESTS ARE LISTED TOO, marked full. You can only fill one by having a
lot of eggs to put in it, but when it happens you still want to find it.
"""
import math

from eggpark import scan, sounds, speech, state, world

_open = False
_items = []     # the found chests, nearest first, as of opening
_focus = 0


def is_open():
    return _open


def forget():
    """Close without a word. For a new park, a menu opening, anything that
    takes the park away from under the list."""
    global _open, _items, _focus
    _open, _items, _focus = False, [], 0


def _distance(chest):
    return math.hypot(chest['x'] - state.player['x'], chest['y'] - state.player['y'])


def _live_items():
    """The list, less any chest that has left the park since it opened."""
    return [c for c in _items if c in state.chests]


def describe(chest, position, total):
    """One chest, the way it's spoken in the list."""
    held, cap = len(chest['eggs']), world.chest_cap()
    parts = [f'Chest, {int(round(_distance(chest)))} metres.']
    if held >= cap:
        parts.append(f'Full, {held} of {cap}.')
    else:
        parts.append(f'Room for {cap - held}.')
    eggs, more = chest.get('clutch_bonus', 0), chest.get('extra_clutches', 0)
    gifts = []
    if eggs:
        gifts.append(f'{eggs} more egg{"s" if eggs != 1 else ""} a clutch')
    if more:
        gifts.append(f'{more} more clutch{"es" if more != 1 else ""}')
    if gifts:
        parts.append('Birds here lay ' + ' and '.join(gifts) + '.')
    else:
        parts.append('Plain birds.')
    parts.append(f'{position} of {total}.')
    return ' '.join(parts)


def _speak_focused():
    items = _live_items()
    if not items:
        speech.say('No found chests left.')
        return
    i = _focus % len(items)
    speech.say(describe(items[i], i + 1, len(items)))


def open_list():
    global _open, _items, _focus
    found = [c for c in state.chests if c['discovered']]
    if not found:
        sounds.fire_fumble()
        speech.say('No chests found yet.')
        return
    _items = sorted(found, key=_distance)
    _focus = 0
    _open = True
    sounds.fire_scan_start()
    n = len(_items)
    speech.say(f'{n} chest{"s" if n != 1 else ""} found, nearest first. '
               f'Up and down to choose, pick one to be led there.')
    _speak_focused()


def close_list():
    forget()
    speech.say('Chest list closed.')


def toggle():
    if _open:
        close_list()
    else:
        open_list()


def move(step):
    global _focus
    items = _live_items()
    if not items:
        _speak_focused()
        return
    _focus = (_focus + step) % len(items)
    _speak_focused()


def pick():
    items = _live_items()
    if not items:
        forget()
        speech.say('No found chests left.')
        return
    chest = items[_focus % len(items)]
    forget()
    sounds.fire_scan_chest_ping(chest)
    scan.start_scan_guide('picked chest', chest)
    speech.say(f'Leading you to the chest, {int(round(_distance(chest)))} metres.')
