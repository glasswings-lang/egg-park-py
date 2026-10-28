# SPDX-License-Identifier: CC0-1.0
"""The reused voice pool: does it play, share buffers, and give up the right
sounds when a park gets busy?

Run: python tests/test_voices.py

Safe to run any time. Two protections, both of which this test refuses to run
without:

  * The listener's own gain is set to zero and read back before a single sound
    is allowed to play, so nothing can reach the speakers whatever backend
    OpenAL chose. The mixer still does all of its work. OpenAL is also pointed
    at its null backend, but that is the second belt, not the first: asking the
    device which backend it opened only ever answers "OpenAL Soft", so it cannot
    be verified, and an unverified promise of silence is worth nothing. Two
    earlier versions of this test made a noise in someone's room. Never again.
  * It moves onto a hidden desktop first, like the game tests do, because
    importing pyglet can take the foreground for a moment and drag a screen
    reader with it.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from _isolated_desktop import enter_isolated_desktop, isolation_detail  # noqa: E402

if not enter_isolated_desktop('eggpark-voices'):
    print('REFUSED: could not move onto a hidden desktop, and importing pyglet '
          'here could take focus from a screen reader.')
    print('  reason:', isolation_detail())
    sys.exit(3)

# Before pyglet: no output device, and HRTF on so the cost is the real cost.
os.environ['ALSOFT_DRIVERS'] = 'null'
os.environ['ALSOFT_HRTF'] = '1'
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(ROOT)

import ctypes                      # noqa: E402
import pyglet                      # noqa: E402

pyglet.options['shadow_window'] = False
pyglet.options['audio'] = ('openal',)
import pyglet.media                # noqa: E402
from pyglet.media import synthesis  # noqa: E402

from eggpark import voices         # noqa: E402

failures = []


def check(label, ok):
    print(('  ok   ' if ok else '  FAIL ') + label)
    if not ok:
        failures.append(label)


def finish(name):
    print()
    if failures:
        print(f'{name}: {len(failures)} FAILED')
        for f in failures:
            print('  - ' + f)
        sys.exit(1)
    print(f'{name}: all good')
    sys.exit(0)


def tone(seconds=0.4, hz=440):
    return pyglet.media.StaticSource(
        synthesis.Sine(seconds, frequency=hz, sample_rate=44100))


def fire(source, category, *, distance=2.0, volume=0.5, at_listener=False):
    return voices.play(source, position=(distance, 0.0, 0.0), volume=volume,
                       duck=1.0, pitch=1.0, min_distance=1.0,
                       max_distance=80.0, category=category,
                       at_listener=at_listener, listener_position=(0.0, 0.0, 0.0))


def gain_of(voice):
    value = ctypes.c_float()
    voices._al.alGetSourcef(voice.source_id, voices._al.AL_GAIN,
                            ctypes.byref(value))
    return value.value


def position_of(voice):
    x, y, z = ctypes.c_float(), ctypes.c_float(), ctypes.c_float()
    voices._al.alGetSource3f(voice.source_id, voices._al.AL_POSITION,
                             ctypes.byref(x), ctypes.byref(y), ctypes.byref(z))
    return (x.value, y.value, z.value)


def silence_everything():
    """Zero the listener's gain, and prove it, before anything plays.

    This is the one guarantee that does not depend on which audio backend
    OpenAL picked, and it is checked rather than assumed: if the gain does not
    read back as zero, the test refuses to go on instead of risking the room.
    """
    al = voices._al
    al.alListenerf(al.AL_GAIN, 0.0)
    value = ctypes.c_float()
    al.alGetListenerf(al.AL_GAIN, ctypes.byref(value))
    return value.value


def clear():
    voices.stop_all()
    voices.dropped.clear()


def main():
    print('the voice pool')
    driver = pyglet.media.get_audio_driver()
    check(f'OpenAL is in charge, not something silent ({type(driver).__name__})',
          type(driver).__name__ == 'OpenALDriver')
    check('the pool starts', voices.start())
    if not voices.available():
        print('  cannot go on: ' + voices.why_not())
        finish('test_voices')
    check(f'{voices.POOL_SIZE} voices exist',
          len(voices._voices) == voices.POOL_SIZE)

    listener_gain = silence_everything()
    check(f'nothing can be heard: the listener is at gain {listener_gain:g}',
          listener_gain == 0.0)
    if listener_gain != 0.0:
        print('  REFUSING to play anything: silence could not be guaranteed.')
        finish('test_voices')

    # ── a sound is loaded once, however often it plays ───────────────────────
    clear()
    voices._buffers.clear()
    egg = tone(0.4, 440)
    for _ in range(20):
        fire(egg, 'egg-call')
    check('twenty plays of one sound made one buffer',
          len(voices._buffers) == 1)
    check('all twenty are playing', voices.live_count() == 20)

    # ── distance decides what is given up, never what is refused ─────────────
    # Silencing distant sounds hid the things the keeper was walking towards.
    clear()
    played_near = fire(egg, 'egg-call', distance=10.0)
    played_far = fire(egg, 'egg-call', distance=500.0)
    check('a sound within earshot plays', played_near)
    check('a distant sound still plays -- it is quiet, not silenced',
          played_far and voices.live_count() == 2)
    check('but it is the further one that would be given up first',
          max(voices._live, key=lambda v: v.distance).distance > 400)

    # nothing at all has a cap except the two mush categories
    clear()
    for _ in range(80):
        fire(bird_or_egg := egg, 'egg-call', distance=5.0)
    check('eighty egg calls at once are eighty egg calls',
          voices.live_count() == 80 and not voices.dropped)

    # ── each kind has its own allowance ──────────────────────────────────────
    # The flock is the good part. Forty birds calling at once should be forty
    # birds calling at once.
    clear()
    bird = tone(0.4, 660)   # noqa: F841 -- used below and by later checks
    for _ in range(40):
        fire(bird, 'bird-call')
    birds = sum(1 for v in voices._live if v.category == 'bird-call')
    check(f'forty bird calls at once are forty bird calls ({birds})', birds == 40)
    check('nothing was let go', not voices.dropped)

    # eggs still get in with the flock in full voice
    check('an egg call still plays over forty birds', fire(egg, 'egg-call'))

    # An allowance still exists where more copies would be mush rather than
    # richness: your own footsteps on top of each other.
    clear()
    step = tone(0.15, 200)
    played = [fire(step, 'footstep', at_listener=True) for _ in range(10)]
    steps = [v for v in voices._live if v.category == 'footstep']
    check(f'ten footsteps at once become {len(steps)}, the allowance being '
          f'{voices.CATEGORY_LIMIT["footstep"]}',
          len(steps) == voices.CATEGORY_LIMIT['footstep'])
    # ...but a step is never dropped for it: a recording longer than a stride
    # used to lose every other step at a run, so the rhythm went irregular.
    # Each new step cuts off the oldest one still sounding instead.
    check('every one of the ten steps started, on time', all(played))
    check('no step was let go', 'footstep' not in voices.dropped)
    newest = sorted(v.serial for v in voices._live)[-len(steps):]
    check('the steps still sounding are the newest three',
          sorted(v.serial for v in steps) == newest)

    # One sound stopped by its handle: how the sound test and the file
    # dialog's Preview stop the last preview before the next.
    clear()
    long_one = tone(2.0, 300)
    fire(long_one, 'wind', at_listener=True)
    wind = voices.last_serial()
    fire(long_one, 'bird-call')
    voices.stop(wind)
    kinds = sorted(v.category for v in voices._live)
    check(f'stop() ends that one sound and nothing else ({kinds})', kinds == ['bird-call'])
    voices.stop(wind)
    fire(long_one, 'wind', at_listener=True)       # may well reuse the same voice
    voices.stop(wind)
    check('a stale handle never stops whatever took its voice since',
          sorted(v.category for v in voices._live) == ['bird-call', 'wind'])

    # Eggs landing in the same instant are not a rhythm: past their allowance
    # the new ones are still let go, not swapped in.
    clear()
    laid = tone(0.4, 880)
    for _ in range(10):
        fire(laid, 'egg-laid')
    eggs_live = sum(1 for v in voices._live if v.category == 'egg-laid')
    check(f'ten eggs laid at once: {eggs_live} play, the rest let go',
          eggs_live == voices.CATEGORY_LIMIT['egg-laid']
          and voices.dropped.get('egg-laid') == 10 - eggs_live)

    # ── when the pool is full, what wins ─────────────────────────────────────
    clear()
    ambient = tone(0.4, 330)
    # bird-ambient has an allowance too, so fill up with something unlimited
    filler = tone(0.4, 550)
    for _ in range(voices.POOL_SIZE):
        fire(filler, 'hatch-in-basket')      # importance 60, no allowance
    check('the pool fills up', voices.live_count() == voices.POOL_SIZE)
    before = voices.stolen
    check('a scan cue gets in anyway', fire(tone(0.2, 880), 'scan-guide'))
    check('it took a voice from something less important',
          voices.stolen == before + 1)
    check('and the pool is still full, not overfull',
          voices.live_count() == voices.POOL_SIZE)

    clear()
    # One source, made before the loop: building 128 of them takes long enough
    # that the first sounds end before the last ones start, which would leave
    # free voices and make this check pass for the wrong reason.
    guide = tone(0.6, 770)
    for _ in range(voices.POOL_SIZE):
        fire(guide, 'scan-guide')
    check('the pool is full of scan cues',
          voices.live_count() == voices.POOL_SIZE)
    before = voices.stolen
    check('a bird call cannot push a scan cue out',
          not fire(bird, 'bird-call') and voices.stolen == before)

    # ── finished voices come back by themselves ──────────────────────────────
    clear()
    short = tone(0.08, 500)
    for _ in range(10):
        fire(short, 'egg-laid')
    time.sleep(0.4)
    voices.update((0.0, 0.0, 0.0), lambda c: 1.0)
    check('voices come back when their sound ends',
          voices.live_count() == 0 and len(voices._free) == voices.POOL_SIZE)

    # ── the duck ─────────────────────────────────────────────────────────────
    clear()
    fire(egg, 'egg-call', volume=0.8)
    v = voices._live[0]
    check(f'a voice starts at its own level ({gain_of(v):.2f})',
          abs(gain_of(v) - 0.8) < 1e-4)
    voices.relevel(lambda c: 0.35 if c != 'scan-guide' else 1.0)
    check(f'the duck pulls it down ({gain_of(v):.3f})',
          abs(gain_of(v) - 0.8 * 0.35) < 1e-4)
    voices.relevel(lambda c: 1.0)
    check(f'and lifting it puts it back exactly ({gain_of(v):.2f})',
          abs(gain_of(v) - 0.8) < 1e-4)

    # ── the listener's own sounds follow the listener ────────────────────────
    clear()
    fire(short, 'footstep', at_listener=True)
    own = voices._live[0]
    voices.update((12.0, -3.0, 0.5), lambda c: 1.0)
    check(f'a footstep moves with you (now at {position_of(own)})',
          position_of(own) == (12.0, -3.0, 0.5))
    clear()
    fire(egg, 'egg-call', distance=5.0)
    world_sound = voices._live[0]
    voices.update((12.0, -3.0, 0.5), lambda c: 1.0)
    check(f'an egg stays where it is ({position_of(world_sound)})',
          position_of(world_sound) == (5.0, 0.0, 0.0))

    # ── a flood, which is what broke the old way ─────────────────────────────
    clear()
    sources = [tone(0.5, 300 + 40 * i) for i in range(8)]
    started = time.perf_counter()
    for i in range(600):
        fire(sources[i % len(sources)],
             ('bird-call', 'egg-call', 'egg-laid', 'basket-chime')[i % 4],
             distance=2.0 + (i % 30))
    cost = time.perf_counter() - started
    check(f'600 sounds in one go never exceeds the pool '
          f'({voices.live_count()} playing)',
          voices.live_count() <= voices.POOL_SIZE)
    check(f'and costs {cost*1000:.0f}ms in total, {cost/600*1000:.3f}ms each',
          cost < 0.5)
    print('  ' + voices.report())

    clear()
    finish('test_voices')


if __name__ == '__main__':
    main()
