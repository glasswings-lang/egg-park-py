# SPDX-License-Identifier: CC0-1.0
"""Every sound: synth placeholders, recordings, sounds.txt, playback, the catalogue."""
import glob
import math
import os
import random

import pyglet
from pyglet.media import synthesis

from eggpark import config, prefs, speech, state, world

# ============================================================================
# Synth source factories (all placeholders — replace with sample banks)
# ============================================================================

def _triangle(frequency, duration, attack=0.06, decay=None, release=0.04, peak=1.0):
    """Build a Triangle source with a pluck-shaped ADSR envelope."""
    if decay is None:
        decay = max(0.01, duration - attack - release)
    return pyglet.media.StaticSource(synthesis.Triangle(
        duration=duration, frequency=frequency, sample_rate=44100,
        envelope=synthesis.ADSREnvelope(
            attack=attack, decay=decay, release=release, sustain_amplitude=0.0,
        ),
    ))


def _sine(frequency, duration, attack=0.10, decay=None, release=0.10):
    if decay is None:
        decay = max(0.01, duration - attack - release)
    return pyglet.media.StaticSource(synthesis.Sine(
        duration=duration, frequency=frequency, sample_rate=44100,
        envelope=synthesis.ADSREnvelope(
            attack=attack, decay=decay, release=release, sustain_amplitude=0.0,
        ),
    ))


def _square(frequency, duration, attack=0.02, decay=None, release=0.02):
    """Square wave. NOTHING USES THIS, on purpose — read before you do.

    A square wave with a fast attack in the low-mid register is not merely
    a harsh sound, it is *specifically* the synthesis medical and emergency
    alarms are built from: rich odd harmonics, no attack transient to soften
    the onset. Three of this game's gentlest messages — "hands full", "that
    did nothing", "this basket is full" — were built this way, and the first
    of them was reported as sounding for all the world like an EMS alarm.
    That was an accurate identification, not an exaggeration.

    Kept because it's a legitimate primitive and the harmonics are useful.
    But if you're reaching for it for anything that isn't an emergency,
    that's the mistake. Even the game's one real alarm (`egg-warning`) uses
    a falling triangle pair instead, so it can be urgent without sounding
    clinical.
    """
    if decay is None:
        decay = max(0.01, duration - attack - release)
    return pyglet.media.StaticSource(synthesis.Square(
        duration=duration, frequency=frequency, sample_rate=44100,
        envelope=synthesis.ADSREnvelope(
            attack=attack, decay=decay, release=release, sustain_amplitude=0.0,
        ),
    ))


def _noise_burst(duration, attack=0.05, decay=None, release=0.05):
    if decay is None:
        decay = max(0.01, duration - attack - release)
    return pyglet.media.StaticSource(synthesis.WhiteNoise(
        duration=duration, sample_rate=44100,
        envelope=synthesis.ADSREnvelope(
            attack=attack, decay=decay, release=release, sustain_amplitude=0.0,
        ),
    ))


# Per-note egg-call sources (one per pentatonic step). Triangle = "egg
# voice." Replace each with sample-bank lookup `samples['egg-call'][note]`.
_egg_call_sources = [_triangle(f, 0.5) for f in config.PENTATONIC_FREQS]

# Per-note basket chime sources — an octave below the eggs, and longer.
# Low tones need more cycles before the ear commits to a pitch, so a bass
# note at egg duration reads as a thud rather than a note.
_basket_chime_sources = [_sine(f * config.BASKET_OCTAVE, 1.3) for f in config.PENTATONIC_FREQS]

# Same note, different timbre, for a basket you've already found.
#
# Baskets used to be SILENT until discovered, so stepping on one switched its
# chime on and the world audibly changed. That gate had to go — you found a
# basket by walking within 3.5 m of it, so the beacon only ever switched on
# after you no longer needed it. But removing the gate took the reward with
# it: every basket now sounded identical before and after, and discovery
# became a single ding followed by nothing.
#
# So: pitch and position stay exactly the same, and only the WAVEFORM
# changes. A triangle carries odd harmonics a sine doesn't, so a found
# basket reads as brighter and closer without moving or changing note.
# You can still find the ones you haven't claimed, and you can still hear
# which ones you have.
# NOTE: found/unfound is a difference WITHIN the basket register, never a
# step out of it. An earlier attempt made a found basket a triangle at egg
# pitch, which made it sound like an egg — the two states were
# distinguishable but the whole category stopped being.
_basket_chime_found_sources = [_triangle(f * config.BASKET_OCTAVE, 1.3,
                                         attack=0.10, release=0.30)
                               for f in config.PENTATONIC_FREQS]

# Per-note scan pings. Briefer than ambient calls; the ping is a discrete
# "here is one item" signal.
_scan_egg_ping_sources = [_triangle(f, 0.3, attack=0.02, release=0.02) for f in config.PENTATONIC_FREQS]
# Basket pings follow baskets into the low register — a scan that answered in
# a different octave to the thing it was pointing at would undo the whole
# separation at the exact moment you're trying to tell them apart.
_scan_basket_ping_sources = [_sine(f * config.BASKET_OCTAVE, 0.6, attack=0.04, release=0.06)
                             for f in config.PENTATONIC_FREQS]

# Bird calls: CHIRPS, not notes.
#
# They used to be the egg call's own triangle, one octave up on the same five
# notes. An octave is the interval the ear fuses most readily, so a bird read
# as a brighter egg and eggs could only be found by scanning. Moving birds by
# whole octaves can't fix that; giving them a different SHAPE does. Eggs hold
# a steady note. Birds slide upward, fast, and never dip below their own note
# (the bird octave, 440-784 Hz), so they stay clear of the eggs' 220-392.
#
# Two calls, and each bird keeps one for life (see flock.hatch_into_your_bird):
#   chirp  - one quick upward slide, 120 ms, rising half an octave-ish (x1.5)
#   tweet  - two shorter slides, 60 ms and 70 ms, 40 ms apart
# Both are the exact recipes from preview clips that were listened to and
# approved; tests/test_birds_lay.py compares these sources to that recipe
# sample by sample. Don't let them drift toward a steady note.
BIRD_CHIRP_ATTACK = 0.004


def _bird_glide(f0, f1, duration, sample_rate=44100):
    """Samples of one upward glide: exponential sweep f0 -> f1, a sine with a
    little second harmonic, snapping on and dying away within the glide."""
    n = int(duration * sample_rate)
    ratio = f1 / f0
    phase = 0.0
    for i in range(n):
        t = i / sample_rate
        phase += 2.0 * math.pi * f0 * ratio ** (t / duration) / sample_rate
        env = min(t / BIRD_CHIRP_ATTACK, 1.0) * math.exp(-t / (duration * 0.35))
        yield env * (math.sin(phase) + 0.2 * math.sin(2.0 * phase)) / 1.2


def _bird_call_generator(parts, sample_rate=44100):
    """`parts`: glides as (f0, f1, seconds), or silences as (None, None, seconds)."""
    for f0, f1, seconds in parts:
        if f0 is None:
            for _ in range(int(seconds * sample_rate)):
                yield 0.0
        else:
            yield from _bird_glide(f0, f1, seconds, sample_rate)
    while True:
        yield 0.0


def _bird_call_source(parts):
    duration = sum(p[2] for p in parts)
    return pyglet.media.StaticSource(synthesis.SynthesisSource(
        _bird_call_generator(parts), duration, 44100))


def bird_chirp_parts(note):
    return [(note, note * 1.5, 0.12)]


def bird_tweet_parts(note):
    return [(note, note * 1.25, 0.06), (None, None, 0.04), (note * 1.1, note * 1.45, 0.07)]


BIRD_CALL_STYLES = ('chirp', 'tweet')
_bird_call_sources = {
    'chirp': [_bird_call_source(bird_chirp_parts(f * config.BIRD_OCTAVE))
              for f in config.PENTATONIC_FREQS],
    'tweet': [_bird_call_source(bird_tweet_parts(f * config.BIRD_OCTAVE))
              for f in config.PENTATONIC_FREQS],
}

# Non-pitched one-shots.
_collect_source = _triangle(440.0, 0.35, attack=0.02, release=0.03)         # A4
# "Hands full" — you walked near an egg you can't carry.
#
# This was a square wave at 110 Hz with a 5 ms attack, which is a buzzsaw
# with a click on the front, played at the listener at half volume. It was
# frightening, and it fires CONSTANTLY: carry capacity starts at one, so
# every egg you pass while holding one sets it off.
#
# It is also the only sound in the game triggered by NOT acting. You didn't
# press anything and nothing went wrong — you walked past something you'll
# come back for. `fumble`, which fires when you press a key that genuinely
# doesn't work, was gentler than this. That was backwards.
#
# Now: sine, soft attack, quieter, and short. B3 is off the pentatonic and
# sits in the gap between egg A3 and egg C4, so it reads as "not a thing"
# rather than a note — and can't be mistaken for an egg you could take.
_refuse_source = _sine(246.94, 0.22, attack=0.05, release=0.12)  # B3, off-scale           # A2 buzz
_basket_discover_source = _sine(174.61, 1.4, attack=0.20, release=0.20)     # F3 — warm "found"
_deposit_source = _triangle(110.0, 0.4, attack=0.02, release=0.02)          # A2 thump
# "This basket is full." GOOD NEWS — you filled it. It was a square wave
# with a 5 ms attack, i.e. the medical-alarm palette, for the sound of a job
# finishing.
#
# Warm, short, and off the scale (Db3 sits between basket C3 and basket D3),
# so it belongs to the basket register without ever being mistaken for a
# chime. Short on purpose: a long sustained tone down here IS a chime.
#
# Deliberately a single tone, not a falling pair — direction is reserved for
# the menu cues and the egg alarm, and this is neither.
_basket_full_source = _triangle(138.59, 0.30, attack=0.03, release=0.14)  # Db3     # D3 — denied
_hatch_in_basket_source = _sine(523.25, 1.6, attack=0.30, release=0.30)     # C5 — bright bloom
# A bird laid an egg. Short and soft, in the egg register (G4) because it
# marks where a new egg now lies; a sine so it isn't mistaken for the
# triangle egg call that egg will start making.
_egg_laid_source = _sine(392.0, 0.35, attack=0.01, release=0.25)             # G4 — soft plop

# Chests: a struck METAL BELL, unlike anything else in the park.
#
# Every other placeholder is a clean musical tone whose overtones sit on
# whole-number multiples of its note (sine, triangle, the plucks and chirps).
# A bell made by frequency modulation at a non-whole ratio puts its overtones
# BETWEEN those multiples, which is what the ear hears as struck metal rather
# than a note. That, not pitch, is what keeps it apart. tests/test_chests.py
# measures it.
#
# Pitch Ab3 (207.65 Hz): above the highest basket note (G3, 196) and below the
# lowest egg (A3, 220), so it doesn't sit on top of either. Placeholder only;
# a proper chest soundscape comes later.
CHEST_BELL_HZ = 207.65
CHEST_BELL_RATIO = 1.41      # modulator / carrier: deliberately not a whole number


def _bell_generator(strikes, duration, sample_rate=44100):
    """`strikes`: (start seconds, carrier Hz, brightness, ring seconds). Each is
    a frequency-modulated bell whose brightness fades faster than its ring."""
    n = int(duration * sample_rate)
    peak = sum(1.0 for _ in strikes)
    for i in range(n):
        t = i / sample_rate
        v = 0.0
        for start, hz, brightness, ring in strikes:
            s = t - start
            if s < 0.0:
                continue
            env = min(s / 0.003, 1.0) * math.exp(-s / ring)
            index = brightness * math.exp(-s / (ring * 0.4))
            v += env * math.sin(2.0 * math.pi * hz * s
                                + index * math.sin(2.0 * math.pi * hz * CHEST_BELL_RATIO * s))
        yield v / peak
    while True:
        yield 0.0


def _bell_source(strikes, duration):
    return pyglet.media.StaticSource(synthesis.SynthesisSource(
        _bell_generator(strikes, duration), duration, 44100))


_chest_chime_source = _bell_source([(0.0, CHEST_BELL_HZ, 2.5, 0.45)], 1.4)
# Found: the same bell struck harder, so brighter. Same idea as found baskets.
_chest_chime_found_source = _bell_source([(0.0, CHEST_BELL_HZ, 4.5, 0.45)], 1.4)
# Found, with gifts: the bell, then a fifth above it, rising.
_chest_discover_source = _bell_source(
    [(0.0, CHEST_BELL_HZ, 3.5, 0.5), (0.22, CHEST_BELL_HZ * 1.5, 3.5, 0.6)], 2.2)
_scan_chest_ping_source = _bell_source([(0.0, CHEST_BELL_HZ, 2.5, 0.15)], 0.5)
_wild_bird_flyoff_source = _noise_burst(config.WILD_BIRD_DISPERSAL,
                                         attack=0.05, decay=config.WILD_BIRD_DISPERSAL - 0.2, release=0.15)

# Footstep — short noise burst as the synth placeholder. Quiet by design;
# it fires every meter and shouldn't fatigue. Real samples will replace it.
#
# LOW-PASSED AT 5 kHz. Raw white noise put most of its energy up top, and a
# step every half second of that came across as being hissed at, constantly.
# Everything above the cutoff is what made it a hiss rather than a step.
FOOTSTEP_LOWPASS_HZ = 5000.0


def _lowpassed_noise_generator(cutoff, sample_rate):
    """White noise through a 2-pole (12 dB per octave) low-pass filter."""
    w = 2.0 * math.pi * cutoff / sample_rate
    alpha = math.sin(w) / (2.0 * 0.7071)
    cos_w = math.cos(w)
    a0 = 1.0 + alpha
    b0 = b2 = (1.0 - cos_w) / 2.0 / a0
    b1 = (1.0 - cos_w) / a0
    a1 = -2.0 * cos_w / a0
    a2 = (1.0 - alpha) / a0
    x1 = x2 = y1 = y2 = 0.0
    while True:
        x = random.uniform(-1.0, 1.0)
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, x, y1, y
        yield max(-1.0, min(1.0, y))


def _lowpassed_noise_burst(duration, cutoff, attack, decay, release):
    return pyglet.media.StaticSource(synthesis.SynthesisSource(
        _lowpassed_noise_generator(cutoff, 44100), duration, 44100,
        envelope=synthesis.ADSREnvelope(
            attack=attack, decay=decay, release=release, sustain_amplitude=0.0,
        ),
    ))


_footstep_source = _lowpassed_noise_burst(
    0.12, FOOTSTEP_LOWPASS_HZ, attack=0.005, decay=0.05, release=0.06)

# Standing on a basket. Longer and softer than open ground — a shorter,
# duller burst reads as a step onto something that gives, rather than onto
# packed earth. It tells you you're ON the basket, which the chime can't:
# the chime is loudest nearby but never says "here", and standing exactly
# on the deposit spot is the one thing you actually need to know before
# pressing F.
_footstep_basket_source = _lowpassed_noise_burst(
    0.18, FOOTSTEP_LOWPASS_HZ, attack=0.01, decay=0.09, release=0.08)

# Egg warning — short distressed-coo placeholder (sine in mid-octave).
# Egg warning — the only alarm in the game. It means you are about to lose
# a bird, and it is the one sound that must never be mistaken for anything.
#
# It used to be a single sine at 659.25 Hz, which is also exactly the pitch
# and near enough the length of `scan start` — the blip you fire deliberately
# several times a minute. An alarm that sounds like the most common
# acknowledgement in the game is an alarm you learn to ignore.
#
# Now: two tones, FALLING, both deliberately off the pentatonic (Eb5 -> Bb4),
# so it is the only thing in the world that isn't in key. Falling because
# this reports something slipping away rather than asking for input, matching
# the shape used everywhere else. Two events also read as urgency in a way no
# single tone does, which is why smoke alarms and reversing lorries chirp
# rather than hold a note.
#
# Kept short — it fires once a second for the last five seconds, so it has to
# stay clear of its own next repeat and must not become punishing to hear
# five times.
_egg_warning_source = _triangle(622.25, 0.10, attack=0.005, release=0.03)   # Eb5
_egg_warning_second_source = _triangle(466.16, 0.15, attack=0.005, release=0.05)  # Bb4
EGG_WARNING_GAP = 0.11  # seconds between the two tones

# Scan start — quick chime marking the moment of pressing Space.
_scan_start_source = _triangle(659.25, 0.18, attack=0.01, release=0.04)         # E5

# Scan guide — the blip that leads you to what a scan found. Repeats from the
# target's direction; see tick_scan_guide for what changes it.
#
# E5 is shared with scan-start and sits in the bird octave. What keeps it
# apart is its VOICE: a bright pluck, a sine with a little second and third
# harmonic on top, that snaps on and dies away fast. Triangles this high sound
# almost like pure sines, so a plain sine here read as one more bird. That
# was tried, and it did. This recipe is the one heard and approved in the
# preview clips; keep the harmonics and the fast decay if you retune it.
def _scan_guide_generator(frequency, sample_rate, duration):
    step = 2.0 * math.pi * frequency / sample_rate
    attack, decay = 0.006, 0.035
    for i in range(int(duration * sample_rate)):
        t = i / sample_rate
        env = min(t / attack, 1.0) * math.exp(-t / decay)
        a = i * step
        tone = math.sin(a) + 0.25 * math.sin(2 * a) + 0.08 * math.sin(3 * a)
        yield env * tone / 1.33   # 1.33 = the three amplitudes summed: no clipping
    while True:
        yield 0.0


_scan_guide_source = pyglet.media.StaticSource(synthesis.SynthesisSource(
    _scan_guide_generator(659.25, 44100, 0.11), 0.11, 44100))                 # E5

# Bird ambient — short noise burst, brighter than a footstep.
_bird_ambient_source = _noise_burst(0.18, attack=0.02, decay=0.08, release=0.06)

# "That press did nothing." F with no basket under you, F with empty hands,
# a scan that found nothing in range.
#
# Same square-with-a-click problem as the other two. It pairs with `refuse`
# as the game's two soft negatives, so it's built to match: same family,
# lower and drier. Ab3 is off the pentatonic and sits below refuse's B3,
# which makes them a low/high pair rather than two unrelated noises.
#
# Kept out of the basket register (110-196) despite being a low sound — a
# short tone down there among the chimes is one more thing to disentangle.
_fumble_source = _triangle(207.65, 0.14, attack=0.025, release=0.06)  # Ab3

# Boot — a warm bloom that announces the game has loaded.
_boot_source = _sine(329.63, 1.2, attack=0.25, release=0.30)                    # E4

# Menu cues — rising for open, falling for close (the conventional shape).
_menu_open_source = _triangle(523.25, 0.20, attack=0.02, release=0.05)          # C5
_menu_close_source = _triangle(329.63, 0.20, attack=0.02, release=0.05)         # E4

# Origin chime — the fixed beacon at world (0, 0, 0).
#
# It used to be E3 (164.81 Hz), chosen as "outside the pentatonic's
# mid-octave but harmonically related". Moving baskets an octave down put
# a basket on exactly that pitch — and a found basket is a triangle, so the
# permanent landmark and a movable one became the same sound. Two beacons
# that can't be told apart are worse than one.
#
# Eb3 keeps the low-register bell character and is the one pitch in it that
# is NOT in A minor pentatonic, so it can never collide with a basket
# however the octave constant is tuned. Slightly outside the key on
# purpose: home should sound like home, not like another landmark.
ORIGIN_FREQ = 155.56  # Eb3 — deliberately not a pentatonic degree
_origin_source = _triangle(ORIGIN_FREQ, 1.5, attack=0.2, release=0.4)

# Ambience — looped under everything. The synth fallback is filtered noise
# (200 Hz lowpass) so the placeholder reads as distant air rather than
# full-spectrum hiss. A recorded `ambience.wav` plays as-recorded; only
# this synth fallback gets the lowpass.
def _make_lowpass_noise_source(duration_sec, cutoff_hz, sample_rate=44100):
    """Generate a Source of lowpass-filtered white noise via numpy + scipy.
    Falls back to plain white noise if either is missing — the game still
    boots, the bed is just harsher until samples replace it."""
    try:
        import numpy as np
        from scipy import signal as sp_signal
        import io
        import wave
    except ImportError:
        return pyglet.media.StaticSource(synthesis.WhiteNoise(
            duration=duration_sec, sample_rate=sample_rate,
        ))
    n = int(duration_sec * sample_rate)
    x = np.random.uniform(-1.0, 1.0, n).astype(np.float32)
    # 4th-order Butterworth lowpass at the cutoff.
    sos = sp_signal.butter(4, cutoff_hz, btype='low', fs=sample_rate, output='sos')
    y = sp_signal.sosfilt(sos, x).astype(np.float32)
    # The lowpass strips most of the energy from white noise (we kept only
    # the bottom ~200 Hz of ~22 kHz bandwidth), so normalize back up with
    # a touch of headroom so it doesn't clip on loud peaks.
    peak = float(np.abs(y).max())
    if peak > 0:
        y = y / peak * 0.8
    samples_int = (y * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples_int.tobytes())
    buf.seek(0)
    return pyglet.media.load('synth-ambience.wav', file=buf, streaming=False)


_ambience_source = _make_lowpass_noise_source(30.0, 200.0)


# ============================================================================
# Sample bank — looks for recorded .wav files in public/audio/samples and
# uses them in place of the synth placeholders above. Flat-pool per
# category: drop `{category}-N.wav` variants in (or a single
# `{category}.wav` for one-variant categories) and the engine picks one
# at random per fire. Empty categories fall back to the synth placeholder
# transparently. No pitch matching — the pentatonic still drives synth
# variation per egg / basket / bird while you're recording, but the
# recorded pool is flat and direction/HRTF carries the spatial cue.
# ============================================================================

SAMPLES_DIR = os.path.join(config._script_dir, 'public', 'audio', 'samples')
os.makedirs(SAMPLES_DIR, exist_ok=True)

_SAMPLE_CATEGORIES = (
    'egg-call', 'basket-chime', 'basket-chime-found',
    'scan-egg-ping', 'scan-basket-ping', 'scan-guide', 'bird-call',
    'egg-collect', 'refuse', 'basket-discover', 'basket-deposit',
    'basket-full', 'hatch-in-basket', 'egg-laid', 'wild-bird-flyoff',
    'chest-chime', 'chest-chime-found', 'chest-discover', 'scan-chest-ping',
    'footstep', 'footstep-basket',
    'egg-warning', 'scan-start', 'bird-ambient', 'fumble',
    'boot', 'menu-open', 'menu-close', 'ambience', 'origin',
)

# Each category stores as [StaticSource, ...] — flat list of variants.
_sample_bank = {}


def _load_one_sample(path):
    try:
        return pyglet.media.load(path, streaming=False)
    except Exception as exc:
        print(f'[samples] could not load {os.path.basename(path)}: {exc}')
        return None


def _load_sample_bank():
    for category in _SAMPLE_CATEGORIES:
        paths = sorted(glob.glob(os.path.join(SAMPLES_DIR, f'{category}-*.wav')))
        single = os.path.join(SAMPLES_DIR, f'{category}.wav')
        if os.path.isfile(single):
            paths.insert(0, single)
        sources = [s for s in (_load_one_sample(p) for p in paths) if s]
        if sources:
            _sample_bank[category] = sources
    if _sample_bank:
        summary = [f'{cat}({len(v)})' for cat, v in _sample_bank.items()]
        print(f'[samples] loaded: {", ".join(summary)}')


def pick_source(category, *, fallback):
    """A random recorded source for this category, or the synth fallback.

    Honours the "Use recordings when available" setting, so the whole game
    can be flipped back to placeholders in one keypress. Every cue routes
    through here, which is what makes that a single switch rather than
    twenty-four of them.
    """
    if not prefs.settings.get('prefer_samples', True):
        return fallback
    bank = _sample_bank.get(category)
    return random.choice(bank) if bank else fallback


def has_recording(category):
    """True if this category has at least one recorded take on disk.

    Deliberately ignores the prefer_samples setting: this answers "does a
    file exist", not "would it be used right now". The sound test needs both
    facts and they are not the same question.
    """
    return bool(_sample_bank.get(category))


# The bank is built further down, once sounds.txt can be read too — see
# rebuild_sample_bank. Loading here would catch only the folder scan.


# ---------------------------------------------------------------------------
# sounds.txt — pointing at your own files, by hand, without renaming anything
# ---------------------------------------------------------------------------
#
# The folder scan above requires a file to be named EXACTLY right and to sit
# in EXACTLY one folder. That is a coding task wearing a filename: it means
# "use this recording" is spelled by renaming `take 4 good one.wav` to
# `basket-chime-2.wav` and moving it.
#
# sounds.txt is the other way in. One line per sound:
#
#     egg-call = C:\Users\you\recordings\take 4 good one.wav
#
# Paths can be absolute or relative to the game folder, spaces are fine, and
# quotes are optional. Several lines for the same cue give it several
# variants, picked between at random exactly like numbered files.
#
# A line here REPLACES the folder-scanned files for that cue rather than
# adding to them, so "which files does this sound use" has one answer and
# it's the one written down.
#
# Nothing here is required. The file is generated with every cue listed and
# commented out, so the names never have to be memorised or typed from
# scratch — uncomment a line and put a path after the equals sign.

SOUNDS_LIST_FILE = os.path.join(config._script_dir, 'sounds.txt')

# (line number, what went wrong) for anything sounds.txt asked for and didn't
# get. Kept rather than printed: this runs under pythonw with no console, and
# a silent failure to load someone's recording is the worst possible outcome.
_sound_list_problems = []


def _parse_sounds_list():
    """Read sounds.txt into {category: [paths]}. Never raises.

    Unknown cue names and missing files are recorded as problems rather than
    ignored. A typo that silently does nothing is indistinguishable from a
    file that didn't load, and you can't see either one.
    """
    _sound_list_problems.clear()
    wanted = {}
    if not os.path.isfile(SOUNDS_LIST_FILE):
        return wanted
    try:
        with open(SOUNDS_LIST_FILE, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception as exc:
        _sound_list_problems.append((0, f'could not open sounds.txt: {exc}'))
        return wanted

    for n, raw in enumerate(lines, start=1):
        # Three ways a line is "just writing", not an instruction. All three
        # exist so the explaining can be done in PLAIN PROSE instead of every
        # line needing a # in front of it — a hundred lines each starting
        # with a hash is a hundred spoken "hash"es to a screen reader, which
        # made the file that explains everything the hardest thing to read.
        if raw[:1] in (' ', '\t'):
            # Indented: a worked example, so ignored. But if it names a real
            # sound AND points at a file that actually exists, it isn't an
            # example — it's someone's real line that picked up a stray
            # space, and swallowing it silently is the failure this whole
            # file is built to avoid. The template's own examples point at
            # C:\Users\you\... which exists nowhere, so they stay quiet.
            maybe = raw.split('#', 1)[0].strip()
            if '=' in maybe:
                cue, path = (p.strip().strip('"').strip("'")
                             for p in maybe.split('=', 1))
                cue = cue.lower().replace(' ', '-').replace('_', '-')
                full = (path if os.path.isabs(path)
                        else os.path.join(config._script_dir, path)) if path else ''
                if cue in _SAMPLE_CATEGORIES and full and os.path.isfile(full):
                    _sound_list_problems.append(
                        (n, f'line {n} for {cue} starts with a space, so it '
                            'is being treated as an example and ignored. '
                            'Move it to the very start of the line.'))
            continue
        if raw.lstrip().startswith('#'):
            continue                      # switched off on purpose
        if '=' not in raw:
            continue                      # ordinary sentence; not for us
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        cue, path = (part.strip() for part in line.split('=', 1))
        cue = cue.lower().replace(' ', '-').replace('_', '-')
        path = path.strip().strip('"').strip("'")
        if cue not in _SAMPLE_CATEGORIES:
            _sound_list_problems.append(
                (n, f'line {n}: there is no sound called {cue}'))
            continue
        if not path:
            _sound_list_problems.append((n, f'line {n}: no file given for {cue}'))
            continue
        full = path if os.path.isabs(path) else os.path.join(config._script_dir, path)
        if not os.path.isfile(full):
            _sound_list_problems.append(
                (n, f'line {n}: the file for {cue} is not there'))
            continue
        wanted.setdefault(cue, []).append(full)
    return wanted


def write_sounds_template(force=False):
    """Create sounds.txt, listing every cue with what it means.

    Generated rather than shipped so it can never drift from the actual cue
    list, and so the names never have to be typed from memory. Won't
    overwrite an existing file unless asked — this is someone's config.
    """
    if os.path.isfile(SOUNDS_LIST_FILE) and not force:
        return False
    lines = [
        'EGG PARK - USING YOUR OWN SOUNDS',
        '',
        'You can record your own sounds and have the game use them instead of',
        'the beeps it comes with. You do not have to rename anything, and you',
        'do not have to move any files.',
        '',
        'Further down, every sound in the game is listed. Each one gets two',
        'lines: what it is, and a line to fill in. They look like this.',
        '',
        '    Footstep - Your own feet on open ground.',
        '    # footstep = ',
        '',
        'To use your own recording, delete the # from the start of the second',
        'line, and type where your file is after the equals sign.',
        '',
        '    Footstep - Your own feet on open ground.',
        '    footstep = C:\\Users\\you\\recordings\\my footstep.wav',
        '',
        'Then save this file, and press R in the Sound test.',
        '',
        'That is the whole thing. The rest of this is only if you want it.',
        '',
        '',
        'A FEW THINGS THAT MIGHT COME UP',
        '',
        'The recording can live anywhere on your computer. Spaces in the name',
        'are fine. You do not need quote marks.',
        '',
        'Leave a line alone and the game keeps using its own built-in sound',
        'for that one. You never have to fill all of these in. One is fine.',
        '',
        'You can give one sound several recordings by writing it more than',
        'once, and the game will pick between them at random.',
        '',
        '    footstep = C:\\Users\\you\\recordings\\step one.wav',
        '    footstep = C:\\Users\\you\\recordings\\step two.wav',
        '',
        'Nothing you type here can break the game. If it cannot find a file,',
        'or does not recognise a name, it says so and carries on with its own',
        'sound. Press P in the Sound test to hear what it did not like.',
        '',
        '',
        'HOW THIS FILE IS READ, IF YOU ARE CURIOUS',
        '',
        'A line counts as an instruction only if it has an equals sign in it,',
        'starts at the very beginning of the line, and does not start with a',
        '# symbol.',
        '',
        'So: sentences like this one are ignored. Indented lines are ignored,',
        'which is why the examples above do nothing. And a # at the start',
        'switches a line off.',
        '',
        'You can write yourself notes anywhere in here.',
        '',
        '',
        'IN THE GAME',
        '',
        'Main menu, then Sound test.',
        '',
        '    Up and Down   move through the sounds',
        '    Enter         play the one you are on',
        '    Right         say what it is for',
        '    S             switch between your recordings and the built-in ones',
        '    R             load this file again, after you save it',
        '    P             read out anything wrong with this file',
        '    F             open this file',
        '',
        '',
        'THE SOUNDS',
        '',
    ]
    body = []
    for category, label, meaning, _getter in SOUND_CATALOGUE:
        body.append(f'{label} - {meaning}')
        body.append(f'# {category} = ')
        body.append('')
    body.append('Background sound - Plays quietly under everything, all the '
                'time. Not a cue, so it is not in the Sound test.')
    body.append('# ambience = ')
    body.append('')
    text = '\n'.join(lines) + '\n' + '\n'.join(body) + '\n'
    try:
        tmp = SOUNDS_LIST_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(text)
        os.replace(tmp, SOUNDS_LIST_FILE)
        return True
    except Exception as exc:
        _sound_list_problems.append((0, f'could not write sounds.txt: {exc}'))
        return False


def sound_list_problem_for(category):
    """The first complaint mentioning this cue, or ''. Used by the sound test
    so a broken path is heard where you'd look for it."""
    for _n, message in _sound_list_problems:
        if category in message:
            return message
    return ''


def rebuild_sample_bank():
    """Re-read sounds.txt and re-scan the samples folder. Says nothing.

    Order matters: the folder scan fills the bank, then sounds.txt overrides
    whatever it names. An explicit instruction should beat a filename
    convention, or writing one down would do nothing whenever a same-named
    file happened to exist.

    Silent so it can run at import, before there is anywhere to speak to.
    """
    _sample_bank.clear()
    _load_sample_bank()
    for cue, paths in _parse_sounds_list().items():
        sources = [s for s in (_load_one_sample(p) for p in paths) if s]
        if sources:
            _sample_bank[cue] = sources
        else:
            _sound_list_problems.append(
                (0, f'the file for {cue} could not be read as sound'))


def reload_sample_bank():
    """rebuild_sample_bank, then report out loud. Bound to R."""
    rebuild_sample_bank()
    total = sum(len(v) for v in _sample_bank.values())
    cues = len(_sample_bank)
    parts = []
    parts.append(f'{total} sound files across {cues} sounds.' if total
                 else 'No recordings loaded. Using the built-in sounds.')
    if _sound_list_problems:
        n = len(_sound_list_problems)
        parts.append(f'{n} problem{"s" if n != 1 else ""} in sounds dot text. '
                     'Press P here to hear them.')
    speech.say(' '.join(parts))


def speak_sound_list_problems():
    if not _sound_list_problems:
        speech.say('No problems in sounds dot text.')
        return
    speech.say('. '.join(message for _n, message in _sound_list_problems) + '.')


# ============================================================================
# Audio playback
# ============================================================================

# Active Player references — Python GCs locals before audio finishes, so
# keep them alive until pyglet's on_player_eos fires.
_active_players = set()

# One-shots that are meant to be AT the listener — your own footsteps, UI
# cues, collect/refuse. They have to be re-positioned every frame, exactly
# like the ambience bed, or they don't stay at you.
#
# Setting the position once at fire time is not enough, and this is why the
# steps sounded like they came from behind. In the update loop the order is:
#
#     player['x'] += ...        # you move
#     fire_footstep()           # source pinned to where you now are
#     update_listener()         # the LISTENER finally moves
#
# so the sound starts one frame ahead of the listener, the listener catches
# up, and then keeps walking forward for the rest of the burst while the
# source stays nailed to that patch of ground. Net effect: every step
# recedes behind you.
#
# The ambience bed was always co-located with the listener too, and never
# sounded wrong — because it alone got its position pushed every frame.
# That was the control that proves it's the update, not the co-location.
_listener_locked = set()


def _play(source, *, position=None, volume=1.0, category=None,
          min_distance=None, max_distance=None, pitch=1.0):
    p = pyglet.media.Player()
    p.queue(source)
    p.pitch = pitch
    # Per-category volume multiplies on top of master volume. Category names
    # ('egg-call', etc.) map to setting keys by replacing '-' with '_' and
    # prefixing 'vol_'. Missing keys default to 1.0, so passing an unknown
    # category is a no-op (you just don't get a slider for it).
    cat_vol = 1.0
    if category:
        cat_vol = prefs.settings.get('vol_' + category.replace('-', '_'), 1.0)
    p.volume = volume * prefs.settings['master_volume'] * cat_vol
    # Spatialize. If the caller passed a world position, use it. Otherwise
    # snap the source to the listener's current position — without this,
    # the source defaults to OpenAL's world-origin (0,0,0) and the listener
    # walks away from it, so "non-positional" sounds end up sounding like
    # they're coming from wherever the player spawned. Co-locating source
    # with listener gives OpenAL a centered, max-gain render — i.e., the
    # "at the listener" behavior we actually want for footsteps, UI cues,
    # collect/refuse/etc.
    at_listener = position is None
    if at_listener:
        position = (state.player['x'], state.player['y'], state.player['z'])
    p.position = position
    # Distance attenuation. The defaults work for in-world objects (eggs,
    # baskets, birds — 80 m max). Origin chime overrides with a much
    # larger max so it stays audible as a navigational beacon.
    # Read from settings so the Hearing distance slider takes effect on the
    # very next sound, with no restart -- tuning this by ear is impossible if
    # you have to relaunch between each try.
    if min_distance is None:
        min_distance = prefs.settings.get('audio_distance', config.SOURCE_MIN_DISTANCE)
    p.min_distance = min_distance
    p.max_distance = max_distance if max_distance is not None else config.SOURCE_MAX_DISTANCE

    def _on_eos():
        _active_players.discard(p)
        _listener_locked.discard(p)

    p.push_handlers(on_player_eos=_on_eos)
    _active_players.add(p)
    if at_listener:
        _listener_locked.add(p)
    p.play()


# --- One sound-effect function per "category." Swap each to use samples
# without changing any caller code. -----------------------------------------

def fire_egg_call(egg):
    src = pick_source('egg-call', fallback=_egg_call_sources[egg['freq_idx']])
    _play(src, position=(egg['x'], egg['y'], egg['z']), volume=0.6,
          category='egg-call')


def fire_basket_chime(basket):
    """Chime the given basket, in whichever voice matches its state.

    Two categories so a recorded sample bank can distinguish them too:
    drop `basket-chime-found-1.wav` and the found voice uses your recording
    while unfound baskets keep theirs. If you only record `basket-chime`,
    the found voice falls back to the synth triangle rather than silently
    collapsing both states into one sound.
    """
    if basket['discovered']:
        src = pick_source(
            'basket-chime-found',
            fallback=_basket_chime_found_sources[basket['freq_idx']])
    else:
        src = pick_source(
            'basket-chime',
            fallback=_basket_chime_sources[basket['freq_idx']])
    # Sample category varies; VOLUME category deliberately does not. _play
    # looks a category up as `vol_<name>` and silently defaults a miss to
    # 1.0, so a separate volume category here would mean "Volume: basket
    # chimes" quietly stopped applying to half the baskets in the world.
    _play(src, position=(basket['x'], basket['y'], basket['z']), volume=0.5,
          category='basket-chime')


def fire_collect_sound():
    _play(pick_source('egg-collect', fallback=_collect_source), volume=0.5,
          category='egg-collect')


def fire_refuse_sound():
    # Quieter than the other cues on purpose. This one fires more often than
    # anything except footsteps, and it's reporting an ordinary situation,
    # not a mistake.
    _play(pick_source('refuse', fallback=_refuse_source), volume=0.3,
          category='refuse')


def fire_basket_discover(basket):
    src = pick_source('basket-discover', fallback=_basket_discover_source)
    _play(src, position=(basket['x'], basket['y'], basket['z']), volume=0.7,
          category='basket-discover')


def fire_deposit_sound(basket):
    src = pick_source('basket-deposit', fallback=_deposit_source)
    _play(src, position=(basket['x'], basket['y'], basket['z']), volume=0.7,
          category='basket-deposit')


def fire_basket_full_sound():
    _play(pick_source('basket-full', fallback=_basket_full_source), volume=0.5,
          category='basket-full')


def fire_scan_egg_ping(egg):
    src = pick_source('scan-egg-ping', fallback=_scan_egg_ping_sources[egg['freq_idx']])
    _play(src, position=(egg['x'], egg['y'], egg['z']), volume=0.7,
          category='scan-egg-ping')


def fire_scan_basket_ping(basket):
    src = pick_source('scan-basket-ping', fallback=_scan_basket_ping_sources[basket['freq_idx']])
    _play(src, position=(basket['x'], basket['y'], basket['z']), volume=0.7,
          category='scan-basket-ping')


def fire_scan_guide(position, *, volume, pitch):
    """One blip of the scan guide. `position` is already placed a short way
    off in the target's direction, NOT at the target — see tick_scan_guide."""
    _play(pick_source('scan-guide', fallback=_scan_guide_source),
          position=position, volume=volume, pitch=pitch, category='scan-guide')


def fire_hatch_in_basket(basket):
    src = pick_source('hatch-in-basket', fallback=_hatch_in_basket_source)
    _play(src, position=(basket['x'], basket['y'], basket['z']), volume=0.7,
          category='hatch-in-basket')


def fire_chest_chime(chest):
    """Found and unfound chests have separate recordings but ONE volume
    slider, the same as baskets."""
    if chest['discovered']:
        src = pick_source('chest-chime-found', fallback=_chest_chime_found_source)
    else:
        src = pick_source('chest-chime', fallback=_chest_chime_source)
    _play(src, position=(chest['x'], chest['y'], chest['z']), volume=0.5,
          category='chest-chime')


def fire_chest_discover(chest):
    _play(pick_source('chest-discover', fallback=_chest_discover_source),
          position=(chest['x'], chest['y'], chest['z']), volume=0.7,
          category='chest-discover')


def fire_scan_chest_ping(chest):
    _play(pick_source('scan-chest-ping', fallback=_scan_chest_ping_source),
          position=(chest['x'], chest['y'], chest['z']), volume=0.7,
          category='scan-chest-ping')


def fire_egg_laid(egg):
    src = pick_source('egg-laid', fallback=_egg_laid_source)
    _play(src, position=(egg['x'], egg['y'], egg['z']), volume=0.6,
          category='egg-laid')


def fire_wild_bird_flyoff(position=None):
    """No position: an egg in your hand, so it plays at you, since you're the
    one losing it. With a position: an egg on the ground, heard from there,
    and only if it's in earshot, like a bird."""
    volume = 0.5
    if position is not None:
        d = math.hypot(position[0] - state.player['x'], position[1] - state.player['y'])
        volume *= max(0.0, min(1.0, (config.BIRD_AUDIBLE - d) / config.BIRD_FADE))
        if volume <= 0.0:
            return
    _play(pick_source('wild-bird-flyoff', fallback=_wild_bird_flyoff_source),
          position=position, volume=volume, category='wild-bird-flyoff')


def bird_hearing(bird):
    """0 when a bird is out of earshot, 1 well inside it, fading between."""
    d = math.hypot(bird['x'] - state.player['x'], bird['y'] - state.player['y'])
    return max(0.0, min(1.0, (config.BIRD_AUDIBLE - d) / config.BIRD_FADE))


def fire_bird_call(bird):
    hearing = bird_hearing(bird)
    if hearing <= 0.0:
        return
    style = bird.get('call_style') or BIRD_CALL_STYLES[bird['freq_idx'] % 2]
    src = pick_source('bird-call', fallback=_bird_call_sources[style][bird['freq_idx']])
    _play(src, position=(bird['x'], bird['y'], bird['z']), volume=0.5 * hearing,
          category='bird-call')


def fire_footstep():
    # Non-positional — these are *your* footsteps, they play at the listener.
    #
    # The surface changes on BASKET_DEPOSIT_RADIUS (via current_basket, the
    # same test F uses), not the wider discovery radius — so the ground
    # changes at exactly the point depositing starts working. Hearing it
    # change and then being told 'not standing on a basket' would be worse
    # than no cue at all.
    #
    # One volume category for both surfaces: "Volume: footsteps" has to mean
    # all of them. Only the sample category and the synth fallback change.
    if world.current_basket() is not None:
        src = pick_source('footstep-basket', fallback=_footstep_basket_source)
    else:
        src = pick_source('footstep', fallback=_footstep_source)
    _play(src, volume=0.3, category='footstep')


def fire_egg_warning(*, position=None):
    """The alarm. Fires from the egg's location for basketed eggs, at the
    listener for held ones — same category either way, so one recorded take
    covers both contexts (anticipation and anxiety).

    A RECORDED sample plays once, whole. Only the synth placeholder is built
    from two scheduled tones: a recording already contains whatever shape its
    author wanted, and firing the second tone over it would talk across
    someone's take.
    """
    recorded = _sample_bank.get('egg-warning') if prefs.settings.get('prefer_samples', True) else None
    if recorded:
        _play(random.choice(recorded), position=position, volume=0.5,
              category='egg-warning')
        return

    _play(_egg_warning_source, position=position, volume=0.5,
          category='egg-warning')
    # Second tone scheduled rather than concatenated: pyglet sources can't be
    # joined without rebuilding the wave by hand, and a scheduled follow-up
    # costs nothing. Position is captured so a basketed warning stays put.
    pyglet.clock.schedule_once(
        lambda _dt: _play(_egg_warning_second_source, position=position,
                          volume=0.5, category='egg-warning'),
        EGG_WARNING_GAP)


# ============================================================================
# Sound test
# ============================================================================
#
# Every cue in the game, in one list, each with what it MEANS. This exists
# because a world made entirely of sound is unusable until you know which
# sound is which — and there was no way to learn that except by triggering
# each one in play and inferring backwards.
#
# It doubles as the recording workstation: arrow to a cue, hear it, toggle
# recordings off with S to hear the placeholder it replaces, press R after
# saving a take to load it without restarting.
#
# ADDING A SOUND MEANS ADDING A LINE HERE. A cue missing from this list is a
# cue nobody can identify, which is the same as not having documented it.
# `getter` is a callable so per-note categories can pick one representative
# note, and so nothing is evaluated before the sources exist.

SOUND_CATALOGUE = [
    ('egg-call', 'Egg call',
     'An egg calling from where it lies. Follow it to find the egg.',
     lambda: _egg_call_sources[0]),
    ('basket-chime', 'Basket chime, not yet found',
     'A basket you have not walked to yet. Low. Speeds up as you approach.',
     lambda: _basket_chime_sources[0]),
    ('basket-chime-found', 'Basket chime, already found',
     'The same basket once you have claimed it. Same note, brighter voice.',
     lambda: _basket_chime_found_sources[0]),
    ('basket-discover', 'Basket found',
     'Fires once, the moment you first reach a basket.',
     lambda: _basket_discover_source),
    ('footstep', 'Footstep',
     'Your own feet on open ground. One per metre walked.',
     lambda: _footstep_source),
    ('footstep-basket', 'Footstep on a basket',
     'Your feet while stood ON a basket. This is how you know F will work.',
     lambda: _footstep_basket_source),
    ('egg-collect', 'Egg collected',
     'You picked up an egg. Its hatch timer is now running.',
     lambda: _collect_source),
    ('refuse', 'Hands full',
     'You walked past an egg you cannot carry. Nothing went wrong.',
     lambda: _refuse_source),
    ('fumble', 'That did nothing',
     'You pressed a key that had nothing to act on.',
     lambda: _fumble_source),
    ('basket-deposit', 'Egg deposited',
     'An egg went from your hands into a basket. It is safe now.',
     lambda: _deposit_source),
    ('basket-full', 'Basket full',
     'That basket has all it can hold. Good news: you filled it.',
     lambda: _basket_full_source),
    ('egg-warning', 'Egg about to hatch',
     'THE ALARM. A held egg is seconds from hatching and flying off. '
     'The only cue in the game that is not in key.',
     None),  # fired through fire_egg_warning so you hear both tones
    ('hatch-in-basket', 'Bird hatched',
     'An egg in a basket became one of your birds.',
     lambda: _hatch_in_basket_source),
    ('egg-laid', 'Egg laid',
     'One of your birds laid an egg, near its home basket. It plays from '
     'where the egg now lies.',
     lambda: _egg_laid_source),
    ('chest-chime', 'Chest, not yet found',
     'A chest you have not walked onto yet. A metal bell. Speeds up as you approach.',
     lambda: _chest_chime_source),
    ('chest-chime-found', 'Chest, already found',
     'A chest you have found. The same bell, struck brighter.',
     lambda: _chest_chime_found_source),
    ('chest-discover', 'Chest found',
     'You walked onto a chest and its three gifts were rolled. The bell, then '
     'a note above it.',
     lambda: _chest_discover_source),
    ('scan-chest-ping', 'Scan ping, chest',
     'One chest answering a scan, or C finding one.',
     lambda: _scan_chest_ping_source),
    ('wild-bird-flyoff', 'Bird lost',
     'A held egg hatched before you could deposit it. That bird is gone.',
     lambda: _wild_bird_flyoff_source),
    ('bird-call', 'Bird call',
     'One of your birds, wandering the park. A quick upward chirp or a double '
     'tweet, high. Eggs hold a steady note; birds slide.',
     lambda: _bird_call_sources['chirp'][0]),
    ('bird-ambient', 'Bird rustle',
     'A bird moving about, between its calls.',
     lambda: _bird_ambient_source),
    ('origin', 'Home beacon',
     'The centre of the world, at zero zero. Always there, never moves.',
     lambda: _origin_source),
    ('scan-start', 'Scan started',
     'You pressed Space. The pings that follow are the scan itself.',
     lambda: _scan_start_source),
    ('scan-egg-ping', 'Scan ping, egg',
     'One egg answering a scan. Near things answer first.',
     lambda: _scan_egg_ping_sources[0]),
    ('scan-basket-ping', 'Scan ping, basket',
     'One basket answering a scan.',
     lambda: _scan_basket_ping_sources[0]),
    ('scan-guide', 'Scan guide',
     'Leads you to what a scan found. Faster and louder as you get closer. '
     'Steady pitch when you face it, low and wobbling when you do not.',
     lambda: _scan_guide_source),
    ('boot', 'Startup',
     'Plays once when the game opens.',
     lambda: _boot_source),
    ('menu-open', 'Menu opened',
     'A menu came up. Rising.',
     lambda: _menu_open_source),
    ('menu-close', 'Menu closed',
     'A menu went away. Falling.',
     lambda: _menu_close_source),
]


def fire_scan_start():
    _play(pick_source('scan-start', fallback=_scan_start_source),
          volume=0.4, category='scan-start')


def fire_bird_ambient(bird):
    hearing = bird_hearing(bird)
    if hearing <= 0.0:
        return
    _play(pick_source('bird-ambient', fallback=_bird_ambient_source),
          position=(bird['x'], bird['y'], bird['z']),
          volume=0.4 * hearing, category='bird-ambient')


def fire_fumble():
    _play(pick_source('fumble', fallback=_fumble_source),
          volume=0.4, category='fumble')


def fire_boot():
    _play(pick_source('boot', fallback=_boot_source),
          volume=0.6, category='boot')


def fire_menu_open():
    _play(pick_source('menu-open', fallback=_menu_open_source),
          volume=0.4, category='menu-open')


def fire_menu_close():
    _play(pick_source('menu-close', fallback=_menu_close_source),
          volume=0.4, category='menu-close')


def fire_origin_chime():
    # Beacon at world origin. Extended max-distance so it remains audible
    # as a navigational landmark from anywhere on the walking plane.
    _play(pick_source('origin', fallback=_origin_source),
          position=(0.0, 0.0, 0.0), volume=0.5, category='origin',
          max_distance=config.ORIGIN_MAX_DISTANCE)


# --- Ambience: continuous looped bed, not one-shot ---------------------------
# Pyglet's Player.loop replays the same source forever. We pick the source
# once at boot (random pick if the user dropped variants like ambience-1.wav)
# and keep that one player alive across settings changes — only its .volume
# property and play/pause state update when settings change.

_ambience_player = None


def _resolve_ambience_source():
    bank = _sample_bank.get('ambience')
    if bank:
        return random.choice(bank)
    return _ambience_source


def _sync_ambience():
    """Reconcile the ambience player with current settings. Safe to call
    after any setting change — if nothing relevant changed it's a no-op."""
    global _ambience_player
    enabled = prefs.settings['enable_ambience']
    target_vol = prefs.settings['master_volume'] * prefs.settings.get('vol_ambience', 1.0)

    if enabled:
        if _ambience_player is None:
            _ambience_player = pyglet.media.Player()
            _ambience_player.queue(_resolve_ambience_source())
            _ambience_player.loop = True
            # Seed at current player position. update_listener pushes
            # further updates each frame, so the bed follows the player.
            _ambience_player.position = (state.player['x'], state.player['y'], state.player['z'])
            _ambience_player.min_distance = config.SOURCE_MIN_DISTANCE
            _ambience_player.max_distance = config.SOURCE_MAX_DISTANCE
        _ambience_player.volume = target_vol
        if not _ambience_player.playing:
            _ambience_player.play()
    else:
        if _ambience_player is not None and _ambience_player.playing:
            _ambience_player.pause()


# ============================================================================
# Listener
# ============================================================================

_listener = pyglet.media.get_audio_driver().get_listener()


def update_listener():
    pos = (state.player['x'], state.player['y'], state.player['z'])
    _listener.position = pos
    _listener.forward_orientation = (
        math.cos(state.player['yaw']), math.sin(state.player['yaw']), 0.0,
    )
    _listener.up_orientation = (0.0, 0.0, 1.0)
    # Ambience is a continuous loop player created once at boot; one-shot
    # _play calls snap to the listener at fire time, but the ambience
    # source needs its position updated every frame so the bed follows
    # the player around the world instead of staying at the spawn point.
    if _ambience_player is not None:
        _ambience_player.position = pos
    # Same treatment for the at-the-listener one-shots. Iterate a copy: a
    # player can reach end-of-stream and drop out of the set mid-loop.
    for p in tuple(_listener_locked):
        try:
            p.position = pos
        except Exception:
            _listener_locked.discard(p)
