# SPDX-License-Identifier: CC0-1.0
"""Fixed numbers the whole game shares: speeds, distances, ranges, timings."""
import math
import os

# The game folder: where main.py, settings.json and the saves live.
_script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ============================================================================
# Constants
# ============================================================================

WALK_SPEED = 2.0
TURN_SPEED = math.pi / 2

# A-minor pentatonic, the world's tonal anchor. All pitched sounds draw
# from this so eggs / baskets / scan pings / bird calls harmonize.
PENTATONIC_FREQS = [220.00, 261.63, 293.66, 329.63, 392.00]  # A3 C4 D4 E4 G4
PENTATONIC_NAMES = ['A3', 'C4', 'D4', 'E4', 'G4']

# Register separation. Everything drew from the same five notes, so eggs and
# baskets sat on top of each other and eggs won — they call more often and a
# triangle is far more assertive than a sine. Timbre alone was never going to
# carry it.
#
# Birds already solved this by living an octave up. Baskets now live an
# octave DOWN, which gives three layers you can hear apart even when all
# three are sounding: baskets low, eggs middle, birds high.
#
# TUNE BY EAR — this is one number. 0.5 is an octave down; 1.0 puts baskets
# back with the eggs; 0.25 is two octaves down and probably too low to
# localise, since HRTF direction cues thin out badly in the bass.
BASKET_OCTAVE = 0.5
BIRD_OCTAVE = 2.0

# Eggs
NUM_EGGS = 4
EGG_CALL_INTERVAL = 1.5
EGG_AUDIBLE = 80.0
COLLECT_RADIUS = 2.0
# Where a new egg appears when you pick one up: around one of the baskets
# you've FOUND, not around you.
#
# It used to be 20-60 m from wherever you picked the last one up, with
# nothing keeping eggs apart. You pick eggs up near home, so early on they
# piled up around your baskets, all calling at once. And every new egg
# started from the last pickup spot rather than from home, so over a long
# session they crept outward: a simulated player was 200+ m from the nearest
# egg after a hundred pickups.
#
# Anchoring to your found baskets keeps eggs within reach of home forever,
# and the area they can appear in grows as your park does. Before any basket
# is found, the anchor is where the park began.
EGG_SPAWN_MIN = 35.0        # from the basket it's placed around
EGG_SPAWN_MAX = 90.0
EGG_MIN_SEPARATION = 30.0   # from every other egg lying in the world
EGG_MIN_FROM_PLAYER = 20.0  # never appears underfoot
EGG_PLACE_ATTEMPTS = 40     # then settle for the most isolated spot tried

# Baskets
BASKET_AUDIBLE = 80.0
BASKET_DEPOSIT_RADIUS = 2.0
BASKET_DISCOVER_RADIUS = 3.5
BASKET_CHIME_INTERVAL_FAR = 4.0
BASKET_CHIME_INTERVAL_NEAR = 1.0

# Basket generation. The park used to hold exactly three baskets, forever,
# which capped carry capacity at two eggs and made walking outward pointless
# — there was nothing further out to find.
#
# Now the world keeps BASKET_TARGET_UNFOUND unclaimed baskets within reach of
# wherever you actually are. Claim one and another appears somewhere you
# haven't been, so exploring in any direction eventually pays.
BASKET_TARGET_UNFOUND = 2     # unclaimed baskets kept available at any time
BASKET_SPAWN_MIN = 45.0       # never closer than this to the player...
BASKET_SPAWN_MAX = 75.0       # ...and INSIDE earshot (80). It was 85, "earshot plus a
                              # little", but a basket placed past 80 doesn't count as
                              # waiting nearby, so another was made at once: 50 extra
                              # in 200 test walks. Baskets outnumbered eggs partly because of it.
BASKET_MIN_SEPARATION = 25.0  # keep them apart or two chimes fight for the ear
BASKET_PLACE_ATTEMPTS = 24    # tries to find a spot before giving up this tick
# Unclaimed baskets left far behind are forgotten. Without this the park
# silts up with baskets you walked past once and will never return to: a
# twenty-minute wander spawned seventeen and found two.
#
# This is ALSO why there is no ceiling on the total. There used to be one
# (24), and discovered baskets counted toward it — so after 24 finds no basket
# ever appeared again, and since basket capacity and carry capacity both grow
# from finds, the ceiling froze them too. The three-baskets-forever problem
# wearing a later hat. Forgetting keeps the unclaimed ones bounded; the
# discovered ones only grow as fast as a person can walk to them, and only
# the nearest basket ever chimes, so a big park costs nothing.
#
# Comfortably beyond earshot, so nothing is ever removed while it can still
# be heard.
BASKET_FORGET_DISTANCE = BASKET_AUDIBLE * 1.75

# Chests: see eggpark/chests.py for what they are and why.
CHEST_TARGET_UNFOUND = 1       # unfound chests kept within earshot (baskets: 2)
CHEST_SPAWN_MIN = 55.0         # further out than baskets' 45...
CHEST_SPAWN_MAX = 75.0         # ...but INSIDE earshot (80): one placed past it doesn't count
                               # as waiting, so a second would spawn straight away
CHEST_MIN_SEPARATION = 30.0    # from every basket and chest
CHEST_PLACE_ATTEMPTS = 24
CHEST_AUDIBLE = 80.0
CHEST_FORGET_DISTANCE = CHEST_AUDIBLE * 1.75
CHEST_DEPOSIT_RADIUS = 5.0     # wider than a basket's 2: more of a place to walk onto
CHEST_DISCOVER_RADIUS = 7.0    # basket: 3.5
CHEST_CHIME_INTERVAL_FAR = 4.5
CHEST_CHIME_INTERVAL_NEAR = 1.2
CHEST_START_CAPACITY = 5       # a chest holds this plus...
CHEST_CAPACITY_PER_BASKET = 2  # ...this per basket found (a basket: 1 per basket found)
CHEST_GIFT_SLOTS = 3
CHEST_GIFT_MIN = 1
CHEST_GIFT_MAX = 5

# Nets. Separate from the three gift slots: each chest, when found, may also
# hold a net. Every net you own widens how far away you can pick eggs up, and
# everything in reach comes up at once, so with a few nets you can walk past a
# clutch and scoop the lot instead of stepping onto each egg.
#
# Capped below EGG_MIN_FROM_PLAYER (20): a replacement egg is never placed
# closer than that, so a net can never snatch the egg that just appeared.
NET_CHANCE = 0.5           # chance a chest holds a net
NET_REACH_EACH = 2.0       # metres of reach each net adds to COLLECT_RADIUS
NET_REACH_MAX = 16.0       # reach never goes past this, however many nets

# "Hands full": how long before walking into another egg you cannot take says
# so again. Depositing clears it too, so this only matters if you keep walking
# with full hands.
REFUSE_REPEAT_SECONDS = 20.0

# Capacity
CARRY_BUMP_EVERY = 3   # player carry cap grows by 1 every N basket discoveries
CARRY_START = 1        # starting carry capacity (also grows from there)

# Scan
SCAN_RANGE = 200.0
SCAN_DURATION = 2.5    # close items ping first, far items last
# The nearest N of each kind actually ping. Space used to ping every egg in
# range, which was fine with four eggs and not once birds lay clutches: a few
# hundred eggs meant a few hundred pings at once, which is both an unlistenable
# wall of sound and more sounds than the audio card will give out (see
# sounds.MAX_VOICES). The count spoken is still the true one.
SCAN_MAX_PINGS_PER_KIND = 12

# Hatching
HATCH_TIMER_INITIAL = 30.0
# Ground hatching: the most eggs that may hatch and fly off in one frame.
# At 60 frames a second that is up to 720 a second, so any believable backlog
# clears in a few seconds while no single frame stalls. See flock.tick_hatching
# for the park that made this necessary.
GROUND_HATCH_PER_FRAME = 12

# Birds laying eggs. A bird hatched in a basket lays a CLUTCH, several eggs at
# once the way real birds do, every "Time before a bird lays" (a setting), for
# life, near its home basket. You keep eggs safe; the birds they become give
# you more young to keep safe.
#
# Clutch size is rolled fresh each time from CLUTCH_MIN..CLUTCH_MAX, plus the
# bird's own clutch_bonus. Plain birds have no bonus; birds hatched in a chest
# with an egg gift will. CLUTCH_MAX is a ballpark, not a wall: with a bonus a
# clutch can go past it.
#
# (An earlier version gave each bird ONE egg for its whole life. That was a
# misreading of "birds lay 1-10": it meant a clutch, not a lifetime.)
CLUTCH_MIN = 1
CLUTCH_MAX = 10
LAY_TIME_DEFAULT = 180.0
LAID_EGG_MIN = 6.0            # from the home basket: close enough to be "theirs"
LAID_EGG_MAX = 20.0
LAID_EGG_MIN_SEPARATION = 8.0  # several birds share a basket; don't stack eggs
WILD_BIRD_DISPERSAL = 1.5
BIRD_CALL_MIN_INTERVAL = 8.0
BIRD_CALL_MAX_INTERVAL = 16.0
BIRD_WANDER_RADIUS = 10.0
BIRD_WANDER_SPEED = 0.4

# How far away a bird can be heard. OpenAL's default distance rule, which
# pyglet never changes, only fades a sound until max_distance (80 m) and
# then holds it at a quarter volume however far away it is. So every bird in
# the park could be heard from everywhere, and a flock of thirty was a wall.
# Eggs and baskets were always limited to earshot; birds never were.
# Past BIRD_AUDIBLE a bird is silent; over the last BIRD_FADE metres its
# calls fade out rather than cutting off.
BIRD_AUDIBLE = 80.0
BIRD_FADE = 20.0

# Footsteps — distance the player has to walk before the next step fires.
# Cadence is implicitly tied to walk speed: 1.0 m stride at default 2.0 m/s
# = ~2 steps/sec = ~120 BPM (natural walking cadence). Slower walk_speed
# spaces them out; faster compresses them toward a jog/run rate.
STEP_DISTANCE = 1.0

# Running: hold Shift. A longer stride, not just the same step faster —
# 5 m/s at a one-metre stride is five steps a second, which is a drumroll,
# not a run. At 1.8 m it's under three a second, and still clearly quicker.
RUN_SPEED = 5.0
RUN_STEP_DISTANCE = 1.8

# Egg warning — when a held or basketed egg's hatch_timer drops below
# WARNING_WINDOW, the warning sound fires once per WARNING_INTERVAL until
# the egg hatches (or the held egg is deposited, resetting the cadence).
WARNING_WINDOW = 5.0
WARNING_INTERVAL = 1.0

# Bird ambient — wing-flap / rustle per bird, between calls. Picked
# independently of bird_call's timing so the two overlap unpredictably.
BIRD_AMBIENT_MIN_INTERVAL = 15.0
BIRD_AMBIENT_MAX_INTERVAL = 40.0

# Origin chime — a beacon at world (0, 0, 0). Lets the player hear which
# way "home" is from anywhere reasonable. Fires on a fixed interval rather
# than proximity-scaled so it's a constant landmark, not a reactive thing.
ORIGIN_CHIME_INTERVAL = 8.0
ORIGIN_MAX_DISTANCE = 500.0  # carries well beyond SOURCE_MAX_DISTANCE

# Spatial audio attenuation (shared by all positioned sounds).
#
# SOURCE_MIN_DISTANCE is OpenAL's REFERENCE distance, not a minimum: it is
# the distance at which a sound plays at full gain, and under the default
# inverse-distance model gain falls as ref / (ref + (dist - ref)).
#
# It was 1.0 in a world where eggs spawn 20-60 m out and baskets sit at 40 m.
# At 40 m that is 1/40th gain -- about -32 dB. So the basket scan ping fired
# perfectly and correctly, at every basket in range, entirely inaudibly. The
# feature was never missing; it was whispering from four blocks away.
#
# At 20 m: 40 m -> 0.33 gain, 60 m -> 0.33... no: ref/(ref+(d-ref)) = 20/40
# = 0.5 at 40 m, 0.25 at 80 m. A usable gradient that still tells you how far
# away something is, which is the whole point of the cue.
SOURCE_MIN_DISTANCE = 20.0
SOURCE_MAX_DISTANCE = 80.0
