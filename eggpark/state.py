# SPDX-License-Identifier: CC0-1.0
"""What's in the park right now: you, the eggs, the baskets, the birds."""


# ============================================================================
# World state
# ============================================================================

# X-Y is the horizontal walking plane, Z is vertical (up). Yaw rotates
# around +Z; yaw=0 means facing +X.
player = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'yaw': 0.0}

# Eggs in the world. Each: {x, y, z, freq_idx, hatch_timer}.
# freq_idx selects a note from PENTATONIC_FREQS.
eggs = []

# Baskets at fixed cardinal-direction positions for easy navigation while
# testing. Each: {x, y, z, freq_idx, discovered, eggs}. `eggs` is a list
# of {hatch_timer} for eggs deposited in this basket.
# The three starting baskets sit at fixed cardinal positions with fixed
# pitches, so the opening of every park is learnable: east is always A3,
# north always D4, west always G4. Everything beyond these is generated as
# you wander (see maybe_spawn_basket).
INITIAL_BASKETS = (
    {'x':  40.0, 'y':   0.0, 'z': 0.0, 'freq_idx': 0, 'discovered': False},  # east  / A3
    {'x':   0.0, 'y':  40.0, 'z': 0.0, 'freq_idx': 2, 'discovered': False},  # north / D4
    {'x': -40.0, 'y':   0.0, 'z': 0.0, 'freq_idx': 4, 'discovered': False},  # west  / G4
)

baskets = [dict(b, eggs=[]) for b in INITIAL_BASKETS]

# Held eggs (player inventory). Each: {hatch_timer}. We don't track which
# spawned egg this came from once collected — they're fungible.
held = []

# Chests: see eggpark/chests.py. Each: {x, y, z, discovered, eggs, gifts,
# clutch_bonus}. None at the start; they appear as you explore.
chests = []

# What chest gifts have added so far, for the whole park.
progress = {'carry_bonus': 0, 'storage_bonus': 0}

# Hatched birds wandering the world. Each: {x, y, z, freq_idx, home_x,
# home_y, wander_angle, next_call_at}.
birds = []
