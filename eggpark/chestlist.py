# SPDX-License-Identifier: CC0-1.0
"""The chest list and the basket list: everything of one kind you've found.

WHY. Chests roll four kinds of gift in fifteen mixes, and two of them belong
to the chest itself: birds hatched there lay bigger clutches, or more of
them. "Lead me to the nearest found chest" (C, D-pad right) can't tell those
apart, so this lists them all, nearest first, and says what each one gives.
Pick one and the scan guide leads you there.

BASKETS TOO, 28 Oct 2026. Chests could be listed and found, baskets only led
to one at a time, so chests were where eggs went and the park bunched up
around them. The same list, of baskets, says how much room each has.

IT IS A SCAN, NOT A MENU. The park keeps running while it's open: eggs keep
counting down, birds keep laying, and you can keep walking. That was
Rozaya's call, 25 Sep 2026. So only the keys it needs are taken while it's
open, and everything else still reaches the park:
  keyboard    G opens the chests and Shift+G the baskets; pressing the one
              that's open closes it, the other switches. Up and Down arrows
              choose, Enter picks, Escape closes. W A S D and turning still
              work.
  controller  Left trigger opens and closes it. D-pad left and right switch
              between chests and baskets, up and down choose, A picks, B
              closes. The sticks still walk and turn.

FULL ONES ARE LISTED TOO, marked full. You can only fill one by having a
lot of eggs to put in it, but when it happens you still want to find it.
"""
import math

from eggpark import scan, sounds, speech, state, world

_open = False
_kind = 'chest'  # 'chest' or 'basket'
_items = []      # the found ones, nearest first, as of opening
_focus = 0

_WORD = {'chest': 'chest', 'basket': 'basket'}


def is_open():
    return _open


def kind():
    return _kind


def forget():
    """Close without a word. For a new park, a menu opening, anything that
    takes the park away from under the list."""
    global _open, _items, _focus
    _open, _items, _focus = False, [], 0


def _pool(which):
    return state.chests if which == 'chest' else state.baskets


def _cap(which):
    return world.chest_cap() if which == 'chest' else world.basket_cap()


def _plural(n, word):
    return f'{n} {word}{"s" if n != 1 else ""}'


def _distance(thing):
    return math.hypot(thing['x'] - state.player['x'], thing['y'] - state.player['y'])


def _live_items():
    """The list, less anything that has left the park since it opened."""
    pool = _pool(_kind)
    return [c for c in _items if c in pool]


def describe(thing, position, total, which=None):
    """One chest or basket, the way it's spoken in the list."""
    which = which or _kind
    held, cap = len(thing['eggs']), _cap(which)
    parts = [f'{_WORD[which].capitalize()}, {int(round(_distance(thing)))} metres.']
    if held >= cap:
        parts.append(f'Full, {held} of {cap}.')
    else:
        parts.append(f'Room for {cap - held}.')
    if which == 'chest':
        eggs, more = thing.get('clutch_bonus', 0), thing.get('extra_clutches', 0)
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
        speech.say(f'No found {_WORD[_kind]}s left.')
        return
    i = _focus % len(items)
    speech.say(describe(items[i], i + 1, len(items)))


def open_list(which='chest'):
    global _open, _kind, _items, _focus
    found = [c for c in _pool(which) if c['discovered']]
    if not found:
        sounds.fire_fumble()
        speech.say(f'No {_WORD[which]}s found yet.')
        return
    _kind = which
    _items = sorted(found, key=_distance)
    _focus = 0
    _open = True
    sounds.fire_scan_start()
    speech.say(f'{_plural(len(_items), _WORD[which])} found, nearest first. '
               f'Up and down to choose, pick one to be led there.')
    _speak_focused()


def close_list():
    word = _WORD[_kind].capitalize()
    forget()
    speech.say(f'{word} list closed.')


def toggle(which='chest'):
    """G (chests) or Shift+G (baskets): open it, close it if it's the one
    already open, or switch to it from the other."""
    if _open and _kind == which:
        close_list()
    else:
        open_list(which)


def switch():
    """D-pad left or right while the list is open: the other kind."""
    toggle('basket' if _kind == 'chest' else 'chest')


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
    word = _WORD[_kind]
    if not items:
        forget()
        speech.say(f'No found {word}s left.')
        return
    thing = items[_focus % len(items)]
    which = _kind
    forget()
    if which == 'chest':
        sounds.fire_scan_chest_ping(thing)
    else:
        sounds.fire_scan_basket_ping(thing)
    scan.start_scan_guide(f'picked {which}', thing)
    speech.say(f'Leading you to the {word}, {int(round(_distance(thing)))} metres.')
