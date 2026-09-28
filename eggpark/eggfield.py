"""
EggField: the egg list, with a grid so "what is near me" stops depending on how
many eggs exist anywhere, and with removal that costs the same at forty thousand
eggs as at four.

Why. A park grows its own crowded corner — baskets cluster, birds lay near
baskets, eggs pile up in the same few metres. One real save had 40,464 eggs in it
with 23,100 inside a single 25-metre square. Everything that asked a question
about eggs walked the whole list, and the crowded corner is exactly where you have
to walk, because that is where the eggs are. Python holds the interpreter while it
counts, so a heavy frame also starved the sound.

Three things live here.

  * A grid of CELL-metre cells, so `near()` and `nearest()` look at a
    neighbourhood instead of a park.
  * An index from egg to position, so `remove()` is immediate. This matters more
    than it sounds: scooping with nets removes hundreds of eggs in ONE frame, and
    the first version of this file searched the list for each of them, which
    turned that into a visible freeze. Measured at 40,464 eggs, one search-based
    removal cost 0.78 ms — so 272 of them, which is one scoop, cost a fifth of a
    second.
  * `slice_for_ticking()`, for the one job that genuinely has to touch every egg:
    counting hatch timers down. Rationed over several frames, since a timer
    measured in minutes does not care whether it is looked at sixty times a
    second.

Eggs never move once laid — nothing in the game assigns to egg['x'] — so a cell is
decided once and stays true. If that ever changes, this has to change with it.

Order is not preserved by `remove()`: the last egg is moved into the gap, which is
what makes it immediate. Nothing in the game depends on the order eggs are in.
"""

from __future__ import annotations

import math

# Cell size, in metres. Chosen against what the game actually asks for: picking
# up reaches 2 m (more with nets), the egg call listens to 80 m, a scan reaches
# 200 m. Small cells make the close questions cheap and the far ones pay in
# dictionary lookups; 4 m keeps the every-frame question (pickup) to a few cells
# while a 200 m scan still only looks up about 2,600 of them.
#
# In the crowded corner of a real park there are roughly 37 eggs to the square
# metre, so a 2 m reach genuinely contains a few hundred eggs. No grid can do
# better than that — what it avoids is the other 22,000.
CELL = 4.0

# How many frames one pass over every hatch timer is spread across. Ten frames at
# 60 fps is a sixth of a second of slack on a timer measured in minutes.
TICK_SLICES = 10

# A step longer than this is not an ordinary frame -- it is a catch-up after a
# stall, or a test winding the clock forward -- and it has to reach every egg,
# because the slices only average out over ordinary frames.
CATCHUP_SECONDS = 0.25


class EggField(list):
    """The eggs. A list, with a grid and an index alongside it."""

    def __init__(self, items=()):
        super().__init__()
        self._cells = {}      # (cx, cy) -> {id(egg): egg}
        self._where = {}      # id(egg) -> index in self
        self._slice = 0
        self.extend(items)

    # ── keeping the grid and the index true ──────────────────────────────────

    @staticmethod
    def _key(egg):
        return (math.floor(egg['x'] / CELL), math.floor(egg['y'] / CELL))

    def append(self, egg):
        self._where[id(egg)] = len(self)
        super().append(egg)
        self._cells.setdefault(self._key(egg), {})[id(egg)] = egg

    def extend(self, items):
        for egg in items:
            self.append(egg)

    def remove(self, egg):
        """Remove this exact egg, immediately.

        By identity, deliberately. Two eggs in the same spot with the same note
        and the same timer are equal as dictionaries, and a crowded park has
        plenty of those, so searching by equality could take a different one than
        the caller meant.
        """
        index = self._where.pop(id(egg), None)
        if index is None:
            # Not one of ours by identity. Fall back to the old behaviour rather
            # than refuse, then repair.
            super().remove(egg)
            self._rebuild()
            return
        last = self[-1]
        if last is not egg:
            self[index] = last
            self._where[id(last)] = index
        super().pop()
        bucket = self._cells.get(self._key(egg))
        if bucket is not None:
            bucket.pop(id(egg), None)
            if not bucket:
                del self._cells[self._key(egg)]

    def clear(self):
        super().clear()
        self._cells.clear()
        self._where.clear()
        self._slice = 0

    def _rebuild(self):
        self._cells = {}
        self._where = {}
        for i, egg in enumerate(self):
            self._where[id(egg)] = i
            self._cells.setdefault(self._key(egg), {})[id(egg)] = egg

    def check(self):
        """True if the grid and the index account for every egg exactly once.

        For tests; the game calls `settle()`.
        """
        if len(self._where) != len(self):
            return False
        for i, egg in enumerate(self):
            if self._where.get(id(egg)) != i:
                return False
        counted = 0
        for key, bucket in self._cells.items():
            for egg in bucket.values():
                if self._key(egg) != key or self._where.get(id(egg)) is None:
                    return False
                counted += 1
        return counted == len(self)

    def settle(self):
        """Rebuild if anything has got past the methods above.

        A guard rather than a belief: this file cannot know every future way
        someone might change the list, so the one number that must always agree
        is checked, and disagreement is repaired rather than reported.
        """
        if len(self._where) != len(self):
            self._rebuild()
            return True
        return False

    # ── the questions worth asking ──────────────────────────────────────────

    def near(self, x, y, radius):
        """Every egg whose cell overlaps the circle.

        Some of what comes back is outside the radius — a cell is a square — so
        callers still measure. What this saves is looking at the rest of the park.
        """
        if radius <= 0 or not self._cells:
            return
        cells = self._cells
        for cx in range(math.floor((x - radius) / CELL),
                        math.floor((x + radius) / CELL) + 1):
            for cy in range(math.floor((y - radius) / CELL),
                            math.floor((y + radius) / CELL) + 1):
                bucket = cells.get((cx, cy))
                if bucket:
                    yield from bucket.values()

    def nearest(self, x, y, max_radius):
        """The closest egg within `max_radius`, or None.

        Searches outwards a ring of cells at a time, and rules a cell out by how
        close anything in it could possibly be. In a crowded park the first cell
        hands back an egg a few centimetres away and every neighbour is then
        dismissed without a single egg in it being looked at.
        """
        if not self._cells or max_radius <= 0:
            return None
        cx, cy = math.floor(x / CELL), math.floor(y / CELL)
        rings = int(max_radius / CELL) + 1
        cells = self._cells
        best = None
        best_d = float('inf')
        for ring in range(rings + 1):
            if ring > 1 and (ring - 1) * CELL > best_d:
                break
            for gx in range(cx - ring, cx + ring + 1):
                for gy in range(cy - ring, cy + ring + 1):
                    if ring and max(abs(gx - cx), abs(gy - cy)) != ring:
                        continue      # only the edge of this ring
                    bucket = cells.get((gx, gy))
                    if not bucket:
                        continue
                    gap_x = max(0.0, gx * CELL - x, x - (gx + 1) * CELL)
                    gap_y = max(0.0, gy * CELL - y, y - (gy + 1) * CELL)
                    if math.hypot(gap_x, gap_y) >= min(best_d, max_radius):
                        continue
                    for egg in bucket.values():
                        d = math.hypot(egg['x'] - x, egg['y'] - y)
                        if d < best_d and d <= max_radius:
                            best, best_d = egg, d
        return best

    # ── the one job that has to touch everything ───────────────────────────

    def ticking(self, dt):
        """Which eggs to count down this frame, and by how much.

        Counting every hatch timer down every frame is the only work here that
        genuinely scales with the whole park, and at 40,000 eggs it measured
        3.5 ms a frame — a fifth of what a frame has to spend. So an ordinary
        frame takes a share of the list and advances it by that much more time.
        Over TICK_SLICES frames every egg has been counted down by the elapsed
        time, and a timer measured in minutes cannot tell the difference.

        A step longer than CATCHUP_SECONDS is not an ordinary frame — it is a
        catch-up after a stall, or a test winding the clock forward — and it
        reaches every egg with the real step, because slices only average out
        over frames that keep coming.

        Returns (eggs, seconds_to_subtract).
        """
        if not self:
            return (), dt
        if dt > CATCHUP_SECONDS or len(self) <= TICK_SLICES:
            return list(self), dt
        slices = TICK_SLICES
        self._slice = (self._slice + 1) % slices
        start = (len(self) * self._slice) // slices
        stop = (len(self) * (self._slice + 1)) // slices
        return self[start:stop], dt * slices

    def cell_count(self):
        return len(self._cells)
