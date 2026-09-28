"""
Voices: a fixed pool of OpenAL sources, reused for every one-shot sound.

Why this exists. Every sound used to build a whole new pyglet Player, and every
Player was fed by one shared worker thread. Measured on 2026-09-27, playing one
short sound many times over at once, the playhead falls behind the wall clock as
voices pile up:

    8 voices    4 ms behind
    32 voices   8 ms
    64 voices  20 ms
    128 voices 68 ms and still slipping

That drift *is* the breaking-up: past a certain density every sound spoils every
other sound. The same test driving OpenAL directly, HRTF and all, played 128
voices with 20 ms of drift and almost no processor time. So the mixer and the
machine were never the problem; the player layer was.

So: hand OpenAL the sounds once as buffers, make a fixed set of sources at
startup, and play by pointing a spare source at a buffer. No object is built and
nothing is decoded while the game is running.

Two other things belong here rather than in the caller, because they are
decisions about what to give up when a park gets busy:

  * A sound too far away to hear never takes a voice at all.
  * When every voice is busy, the least important, most distant one is taken —
    and each kind of sound has its own allowance, so a flock of birds cannot
    drown out the eggs you are trying to find.

This module never opens a device of its own: it borrows pyglet's, so HRTF and the
bundled openal32.dll keep working exactly as before. If anything about that
fails, `available()` returns False and sounds.py falls back to the old path.
"""

from __future__ import annotations

import ctypes
import math

# How many sounds may play at once. OpenAL hands out 256 sources on this
# machine; pyglet's own players (the ambience bed, the wind) want a few, so this
# leaves room to spare. 128 was measured comfortable at about an eighth of one
# processor core; 192 is the same work per voice and leaves the flock room to be
# a flock.
POOL_SIZE = 192

# What each kind of sound is worth when voices run short. Higher wins. The
# numbers only matter relative to each other: eggs and baskets are what the game
# is about, scan cues are an answer to a question you just asked, and birds are
# scenery however lovely they are.
IMPORTANCE = {
    'scan-guide': 100,
    'scan-start': 100,
    'scan-egg-ping': 100,
    'scan-basket-ping': 100,
    'scan-chest-ping': 100,
    'collect': 90,
    'refuse': 90,
    'deposit': 90,
    'basket-full': 85,
    'basket-discover': 85,
    'chest-open': 85,
    'chest-chime': 70,
    'egg-warning': 80,
    'egg-call': 70,
    'basket-chime': 70,
    'hatch-in-basket': 60,
    'origin': 60,
    'egg-laid': 40,
    'footstep': 35,
    'wild-bird-flyoff': 30,
    'bird-call': 25,
    'bird-ambient': 20,
}
DEFAULT_IMPORTANCE = 50

# The most voices any one kind may hold at once.
#
# These are deliberately generous, and the bird ones especially. The keeper's
# correction, and it matters: the bird calls were good; the problem was their
# choking up everything. The birds were never the fault — a player per sound
# was. So the job here is not to thin the flock; it is to make sure that when
# every voice really is busy, what gets given up is a bird rather than the egg
# you are trying to find. That is what IMPORTANCE does, and it only comes into
# play at genuine saturation.
#
# The real limiter is distance: a bird you cannot hear never takes a voice at
# all, so a big park spread wide costs nothing for its far corners.
#
# Small allowances are kept only where more copies are mush rather than richness
# — your own footsteps, eggs landing right beside each other.
CATEGORY_LIMIT = {
    'bird-call': 64,
    'bird-ambient': 40,
    'egg-call': 32,
    'egg-laid': 6,
    'wild-bird-flyoff': 8,
    'footstep': 3,
}

_al = None
_context = None
_ready = False
_why_not = 'not started yet'

_buffers = {}        # id(pyglet source) -> AL buffer id
_buffer_keepalive = []   # hold the sources so their ids are never reused
_voices = []         # every Voice in the pool
_free = []           # Voices not in use
_live = []           # Voices playing, most recently started last

dropped = {}         # category -> how many were dropped, for the log
stolen = 0


class Voice:
    """One OpenAL source, borrowed and returned over and over."""

    __slots__ = ('source_id', 'category', 'base_volume', 'at_listener',
                 'importance', 'distance', 'serial')

    def __init__(self, source_id):
        self.source_id = source_id
        self.category = None
        self.base_volume = 1.0
        self.at_listener = False
        self.importance = 0
        self.distance = 0.0
        self.serial = 0


def available():
    return _ready


def why_not():
    return _why_not


def start():
    """Borrow pyglet's OpenAL device and make the pool. Safe to call twice."""
    global _al, _context, _ready, _why_not
    if _ready:
        return True
    try:
        import pyglet.media
        driver = pyglet.media.get_audio_driver()
        if type(driver).__name__ != 'OpenALDriver':
            _why_not = f'the audio driver is {type(driver).__name__}, not OpenAL'
            return False
        from pyglet.media.drivers.openal import lib_openal as al
        context = driver.context
        context.make_current()
        al.alGetError()

        ids = (al.ALuint * POOL_SIZE)()
        al.alGenSources(POOL_SIZE, ids)
        err = al.alGetError()
        if err:
            _why_not = f'OpenAL would not give {POOL_SIZE} sources (error {err})'
            return False

        _al = al
        _context = context
        for i in range(POOL_SIZE):
            v = Voice(ids[i])
            _voices.append(v)
            _free.append(v)
        _ready = True
        _why_not = ''
        return True
    except Exception as exc:
        _why_not = f'{type(exc).__name__}: {exc}'
        return False


# ── sounds become buffers once ───────────────────────────────────────────────

def _al_format(audio_format):
    channels = audio_format.channels
    size = audio_format.sample_size
    if channels == 1 and size == 8:
        return _al.AL_FORMAT_MONO8
    if channels == 1 and size == 16:
        return _al.AL_FORMAT_MONO16
    if channels == 2 and size == 8:
        return _al.AL_FORMAT_STEREO8
    if channels == 2 and size == 16:
        return _al.AL_FORMAT_STEREO16
    return None


def buffer_for(source):
    """The AL buffer for a pyglet source, made the first time it is asked for.

    Everything the game plays is a StaticSource — already decoded in memory — so
    this is a copy into the sound card, once per sound, for the life of the run.
    """
    key = id(source)
    existing = _buffers.get(key)
    if existing is not None:
        return existing
    fmt = _al_format(source.audio_format)
    if fmt is None:
        return None
    data = getattr(source, '_data', None)
    if data is None:
        audio_data = source.get_queue_source().get_audio_data(1 << 30)
        if audio_data is None:
            return None
        data = audio_data.data
    if not data:
        return None
    buf = _al.ALuint()
    _al.alGenBuffers(1, ctypes.byref(buf))
    if _al.alGetError():
        return None
    _al.alBufferData(buf.value, fmt, data, len(data),
                     source.audio_format.sample_rate)
    if _al.alGetError():
        return None
    _buffers[key] = buf.value
    _buffer_keepalive.append(source)
    return buf.value


# ── playing ──────────────────────────────────────────────────────────────────

def _count_category(category):
    return sum(1 for v in _live if v.category == category)


def _note_drop(category):
    dropped[category] = dropped.get(category, 0) + 1


def _reclaim_finished():
    if not _live:
        return
    state = _al.ALint()
    still = []
    for v in _live:
        _al.alGetSourcei(v.source_id, _al.AL_SOURCE_STATE, ctypes.byref(state))
        if state.value == _al.AL_PLAYING or state.value == _al.AL_PAUSED:
            still.append(v)
        else:
            v.category = None
            _free.append(v)
    _live[:] = still


def _steal_for(importance, distance):
    """Take the worst voice, if this new sound is worth more than it.

    Worse means less important, and among equals, further away.
    """
    global stolen
    if not _live:
        return None
    worst = min(_live, key=lambda v: (v.importance, -v.distance))
    if (worst.importance, -worst.distance) >= (importance, -distance):
        return None
    _al.alSourceStop(worst.source_id)
    _live.remove(worst)
    worst.category = None
    stolen += 1
    return worst


_serial = 0


def play(source, *, position, volume, pitch, min_distance, max_distance,
         category, at_listener, listener_position, duck=1.0):
    """Start a sound. True if it plays, False if it was let go.

    Everything about levels and positions is settled by the caller; the choices
    made here are only about scarcity: too far to hear, too many of its kind, or
    nothing free that it outranks.

    `volume` is the sound's own level with the duck left out, so the duck can be
    applied and lifted later without the level drifting; `duck` is the multiplier
    to start with.
    """
    global _serial
    if not _ready:
        return False

    # Too far away to hear: never worth a voice. The listener's own sounds
    # (footsteps, menus) are always at zero distance.
    distance = 0.0
    if not at_listener and position is not None and listener_position is not None:
        dx = position[0] - listener_position[0]
        dy = position[1] - listener_position[1]
        dz = position[2] - listener_position[2]
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        if max_distance and distance > max_distance:
            _note_drop(category or 'sound')
            return False

    importance = IMPORTANCE.get(category, DEFAULT_IMPORTANCE)

    _reclaim_finished()

    limit = CATEGORY_LIMIT.get(category)
    if limit is not None and _count_category(category) >= limit:
        _note_drop(category or 'sound')
        return False

    buf = buffer_for(source)
    if buf is None:
        _note_drop(category or 'sound')
        return False

    voice = _free.pop() if _free else _steal_for(importance, distance)
    if voice is None:
        _note_drop(category or 'sound')
        return False

    al = _al
    sid = voice.source_id
    al.alSourceStop(sid)
    al.alSourcei(sid, al.AL_BUFFER, buf)
    al.alSourcef(sid, al.AL_GAIN, float(volume) * float(duck))
    al.alSourcef(sid, al.AL_PITCH, float(pitch) if pitch else 1.0)
    al.alSourcef(sid, al.AL_REFERENCE_DISTANCE, float(min_distance))
    al.alSourcef(sid, al.AL_MAX_DISTANCE, float(max_distance))
    al.alSourcei(sid, al.AL_LOOPING, al.AL_FALSE)
    here = position if position is not None else listener_position
    if here is None:
        here = (0.0, 0.0, 0.0)
    al.alSource3f(sid, al.AL_POSITION, float(here[0]), float(here[1]),
                  float(here[2]))
    al.alSourcePlay(sid)
    if al.alGetError():
        _free.append(voice)
        _note_drop(category or 'sound')
        return False

    _serial += 1
    voice.serial = _serial
    voice.category = category
    voice.base_volume = float(volume)
    voice.at_listener = at_listener
    voice.importance = importance
    voice.distance = distance
    _live.append(voice)
    return True


def update(listener_position, duck_factor):
    """Once a frame: return finished voices, move the listener's own sounds,
    and re-level everything for the duck.

    `duck_factor` is called with a category and returns the multiplier to apply.
    """
    if not _ready:
        return
    _reclaim_finished()
    al = _al
    for v in _live:
        if v.at_listener and listener_position is not None:
            al.alSource3f(v.source_id, al.AL_POSITION,
                          float(listener_position[0]),
                          float(listener_position[1]),
                          float(listener_position[2]))
        al.alSourcef(v.source_id, al.AL_GAIN,
                     v.base_volume * duck_factor(v.category))


def relevel(duck_factor):
    """Re-level playing sounds without touching positions."""
    if not _ready:
        return
    for v in _live:
        _al.alSourcef(v.source_id, _al.AL_GAIN,
                      v.base_volume * duck_factor(v.category))


def stop_all():
    """Silence every one-shot at once. For leaving a park."""
    if not _ready:
        return
    for v in tuple(_live):
        _al.alSourceStop(v.source_id)
        v.category = None
        _free.append(v)
    _live.clear()


def live_count():
    return len(_live)


def report():
    """One line for the play log."""
    total_dropped = sum(dropped.values())
    worst = sorted(dropped.items(), key=lambda kv: -kv[1])[:3]
    detail = ', '.join(f'{k} {v}' for k, v in worst) if worst else 'none'
    return (f'voices: {len(_live)} playing of {POOL_SIZE}, '
            f'{len(_buffers)} sounds loaded, {total_dropped} let go '
            f'({detail}), {stolen} taken over')
