"""
EggField: the egg list, with a grid so "what is near me" stops depending on how
many eggs exist anywhere.

Why. A park grows its own crowded corner — baskets cluster, birds lay near
baskets, eggs pile up in the same few metres. One real save had 38,592 eggs in it
with 23,100 of them inside a single 25-metre square. Three places walked the
whole list: picking up what is in reach (every frame), choosing which egg calls
(every egg-call interval), and a scan (on the keypress). Every one of them cost
as much as the park was big, and the crowded corner is exactly where you have to
walk, because that is where the eggs are.

Python holds the interpreter while it counts, and the old audio system's refill
worker was Python too, so a heavy frame also starved the sound. That is why the
audio broke up in dense places and nowhere else.

This is a plain list that also keeps a dictionary of 25-metre cells. Append, go
in a cell. Remove, come out of it. Ask for what is near a point and only the
cells that overlap that circle are looked at. Nothing else in the game has to
know it exists: it *is* the list, so `state.eggs` keeps working everywhere,
including `len()`, iteration, and saving.

Eggs never move once laid — nothing in the game assigns to egg['x'] — so a cell
is decided once and stays true. If that ever changes, this has to change with it.
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


class EggField(list):
    """The eggs. A list, with a grid alongside it."""

    def __init__(self, items=()):
        super().__init__()
        self._cells = {}
        self.extend(items)

    # ── keeping the grid true ────────────────────────────────────────────────

    @staticmethod
    def _key(egg):
        return (math.floor(egg['x'] / CELL), math.floor(egg['y'] / CELL))

    def append(self, egg):
        super().append(egg)
        self._cells.setdefault(self._key(egg), []).append(egg)

    def extend(self, items):
        for egg in items:
            self.append(egg)

    def remove(self, egg):
        """Remove this exact egg.

        By identity, deliberately. Two eggs in the same spot with the same note
        and the same timer are equal as dictionaries, and a crowded park has
        plenty of those, so list.remove could take a different one than the
        caller meant — and then the list and the grid would disagree about which
        egg is where.
        """
        for i, existing in enumerate(self):
            if existing is egg:
                del self[i]
                break
        else:
            super().remove(egg)          # not ours by identity; old behaviour
            self._rebuild()
            return
        bucket = self._cells.get(self._key(egg))
        if bucket is not None:
            for i, existing in enumerate(bucket):
                if existing is egg:
                    del bucket[i]
                    break
            if not bucket:
                del self._cells[self._key(egg)]

    def clear(self):
        super().clear()
        self._cells.clear()

    def _rebuild(self):
        self._cells = {}
        for egg in self:
            self._cells.setdefault(self._key(egg), []).append(egg)

    def check(self):
        """True if the grid still accounts for every egg exactly once.

        Cheap enough to call from a test; the game calls `settle()` instead.
        """
        counted = sum(len(b) for b in self._cells.values())
        if counted != len(self):
            return False
        seen = set()
        for key, bucket in self._cells.items():
            for egg in bucket:
                if self._key(egg) != key or id(egg) in seen:
                    return False
                seen.add(id(egg))
        return len(seen) == len(self)

    def settle(self):
        """Rebuild the grid if anything has got past the methods above.

        A guard rather than a belief: this file cannot know about every future
        way someone might change the list, so the one number that must always
        agree is checked, and disagreement is repaired rather than reported. It
        costs one comparison per call.
        """
        if sum(len(b) for b in self._cells.values()) != len(self):
            self._rebuild()
            return True
        return False

    # ── the question worth asking ───────────────────────────────────────────

    def near(self, x, y, radius):
        """Every egg whose cell overlaps the circle, nearest cells first.

        Some of what comes back is outside the radius — a cell is a square — so
        callers still measure. What this saves is looking at the rest of the
        park.
        """
        if radius <= 0 or not self._cells:
            return
        first_x = math.floor((x - radius) / CELL)
        last_x = math.floor((x + radius) / CELL)
        first_y = math.floor((y - radius) / CELL)
        last_y = math.floor((y + radius) / CELL)
        cells = self._cells
        for cx in range(first_x, last_x + 1):
            for cy in range(first_y, last_y + 1):
                bucket = cells.get((cx, cy))
                if bucket:
                    yield from bucket

    def nearest(self, x, y, max_radius):
        """The closest egg within `max_radius`, or None.

        Searches outwards a ring of cells at a time and stops as soon as the best
        egg found is closer than the nearest possible egg in the next ring. In a
        crowded park the answer is usually in the first ring, so this costs
        almost nothing however many eggs are audible — and "which egg calls" is
        asked every 1.5 seconds, which is often enough for a 5 ms answer to be
        felt as a stumble.
        """
        if not self._cells or max_radius <= 0:
            return None
        cx, cy = math.floor(x / CELL), math.floor(y / CELL)
        rings = int(max_radius / CELL) + 1
        cells = self._cells
        best = None
        best_d = float('inf')
        for ring in range(rings + 1):
            # Nothing in this ring or any later one can beat what we have.
            if ring > 1 and (ring - 1) * CELL > best_d:
                break
            for gx in range(cx - ring, cx + ring + 1):
                for gy in range(cy - ring, cy + ring + 1):
                    if ring and max(abs(gx - cx), abs(gy - cy)) != ring:
                        continue      # only the edge of this ring
                    bucket = cells.get((gx, gy))
                    if not bucket:
                        continue
                    # How close anything in this cell could possibly be: the
                    # distance to the cell's own rectangle. In a crowded park
                    # the first cell hands back an egg a few centimetres away,
                    # and then every neighbouring cell is ruled out without a
                    # single egg in it being looked at. That is what makes this
                    # cost the same in a heap of twenty thousand as in an empty
                    # field.
                    gap_x = max(0.0, gx * CELL - x, x - (gx + 1) * CELL)
                    gap_y = max(0.0, gy * CELL - y, y - (gy + 1) * CELL)
                    if math.hypot(gap_x, gap_y) >= min(best_d, max_radius):
                        continue
                    for egg in bucket:
                        d = math.hypot(egg['x'] - x, egg['y'] - y)
                        if d < best_d and d <= max_radius:
                            best, best_d = egg, d
        return best

    def cell_count(self):
        return len(self._cells)
