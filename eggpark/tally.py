# SPDX-License-Identifier: CC0-1.0
"""Counting repeated events, and reporting them once.

THE RULE: a thing that can happen to many eggs at once does not get a sound
per egg, or a sentence per egg. It gets counted, and the count is reported.

Why this exists. Every hatch, flyoff and warning used to fire its own
one-shot and say its own line. That is correct for one egg and ruinous for a
park: a play log caught a park where twelve eggs hatched away per frame, all
64 sound slots went to identical flyoffs, and the basket chimes and bird
calls were dropped for want of a slot. A flock of twelve birds leaving at
once does not sound like twelve birds; it sounds like mud. And twelve spoken
lines are twelve interruptions, which with NVDA asleep cannot even be
skipped.

How it works. Something happens, so it is added to a tally. Once a frame,
game.update calls flush_all, and each tally that has anything in it and is
past its own minimum gap fires ONE sound and speaks ONE line with the number
in it. Everything else that arrived in between is in that number.

The gaps are per tally, because the events differ: a wave of eggs hatching
away is scenery and can report slowly, while an egg about to hatch in your
hands is urgent and reports every second, as it always did.

Positions: a tally keeps the position nearest the player, because that is
the one you had a chance of reaching and the only one you could have
localised anyway.
"""
import math

from eggpark import sounds, speech, state


class Tally:
    """One kind of event, counted and reported at most every `gap` seconds.

    `sound` is the NAME of a function in eggpark.sounds, looked up when it
    fires rather than held onto here. Two reasons, both real: sounds is still
    being imported when this module is read, so holding the function is a
    circular-import crash; and tests replace those functions on the module,
    which a held reference would quietly ignore.
    `phrase(count)` returns what to say, or None to say nothing at all —
    scenery (eggs hatching away across a whole park) is heard, not narrated.
    """

    def __init__(self, name, gap, sound=None, phrase=None, positional=True):
        self.name = name
        self.gap = gap
        self.sound = sound
        self.phrase = phrase
        self.positional = positional
        self.count = 0
        self.position = None
        self.next_at = 0.0

    def add(self, position=None):
        self.count += 1
        if position is None or not self.positional:
            return
        if self.position is None or self._near(position) < self._near(self.position):
            self.position = position

    @staticmethod
    def _near(position):
        return math.hypot(position[0] - state.player['x'], position[1] - state.player['y'])

    def flush(self, now):
        """Report, if there is anything to report and enough time has passed.
        Returns what was said, or '' — handy for tests."""
        if not self.count or now < self.next_at:
            return ''
        count, position = self.count, self.position
        self.count, self.position = 0, None
        self.next_at = now + self.gap
        if self.sound is not None:
            fire = getattr(sounds, self.sound)
            if self.positional and position is not None:
                fire(position=position)
            else:
                fire()
        line = self.phrase(count) if self.phrase else None
        if line:
            speech.say(line)
            return line
        return ''

    def forget(self):
        """Drop what's waiting and clear the gap. For a new park: events from
        the park you just left must not be reported into this one."""
        self.count, self.position, self.next_at = 0, None, 0.0


def _birds_hatched(count):
    flock = len(state.birds)
    in_park = f'{flock} bird{"s" if flock != 1 else ""} in the park.'
    if count == 1:
        return f'A bird hatched. {in_park}'
    return f'{count} birds hatched. {in_park}'


def _eggs_lost(count):
    if count == 1:
        return 'An egg in your hand hatched. The bird flew off.'
    return f'{count} eggs in your hands hatched. Those birds flew off.'


# Eggs hatching away on the ground: scenery. Heard, never spoken — in a park
# with laying birds this happens forever and would never stop talking.
GROUND_FLYOFF = Tally('ground flyoff', 1.5, 'fire_wild_bird_flyoff')

# Eggs hatching into YOUR birds, in a basket or chest. A whole basket can come
# due in one frame, so this is the difference between one line and twenty-eight.
BIRD_HATCHED = Tally('bird hatched', 0.8, 'fire_hatch_in_basket_at', _birds_hatched)

# Held eggs hatching before you got them anywhere. Plays at you, so no
# position, and it is worth speaking: this is the one you lost.
EGG_LOST = Tally('egg lost', 0.8, 'fire_wild_bird_flyoff', _eggs_lost,
                 positional=False)

# The alarm, for held and basketed eggs in their last seconds. Fires every
# second as it always did, however many eggs are counting down, from the one
# nearest you.
EGG_WARNING = Tally('egg warning', 1.0, 'fire_egg_warning')

ALL = (GROUND_FLYOFF, BIRD_HATCHED, EGG_LOST, EGG_WARNING)


def flush_all(now):
    for tally in ALL:
        tally.flush(now)


def forget_all():
    for tally in ALL:
        tally.forget()
