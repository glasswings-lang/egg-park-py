# SPDX-License-Identifier: CC0-1.0
"""Birds hatched in baskets lay eggs near home.

Run: python tests/test_birds_lay.py

Runs the real game, safely: see _game_harness.py.
"""
import math

import _game_harness  # noqa: F401  (hidden desktop, silence; must come first)
from _game_harness import check, finish, run_game

from pyglet.window import key


def run_checks(G):
    G['write_sounds_template'] = lambda *a, **k: False
    G['say'] = lambda text: None
    laid_sounds = []
    G['fire_egg_laid'] = lambda egg: laid_sounds.append(egg)
    settings, eggs, birds, player = G['settings'], G['eggs'], G['birds'], G['player']

    def fresh_park():
        G['start_game']()
        home = G['baskets'][0]
        home['discovered'] = True
        player.update(x=500.0, y=500.0)            # far away: nothing picked up by accident
        return home

    def frames(seconds):
        for _ in range(int(seconds * 60)):
            G['update'](1 / 60)

    def laid():
        return [e for e in eggs if e.get('laid')]

    print('a plain bird:')
    settings['lay_time'] = 30.0
    home = fresh_park()
    G['hatch_into_your_bird'](home)
    bird = birds[0]
    check('is born with one egg to lay', bird['eggs_to_lay'] == 1)
    frames(29)
    check('has not laid before the lay time', not laid())
    frames(2)
    check(f'lays after the lay time ({len(laid())} egg)', len(laid()) == 1)
    egg = laid()[0]
    d = math.hypot(egg['x'] - home['x'], egg['y'] - home['y'])
    check(f'near its home basket ({d:.1f} m)', G['LAID_EGG_MIN'] - 0.01 <= d <= G['LAID_EGG_MAX'] + 0.01)
    check('the laid sound plays from the egg', laid_sounds and laid_sounds[-1] is egg)
    frames(200)
    check('and never lays again', len(laid()) == 1 and bird['eggs_to_lay'] == 0)

    print('the setting is honoured:')
    settings['lay_time'] = 90.0
    home = fresh_park()
    G['hatch_into_your_bird'](home)
    frames(60)
    check('nothing at 60 s with a 90 s lay time', not laid())
    frames(31)
    check('laid by 91 s', len(laid()) == 1)

    print('timing settings move in 5 second jumps:')
    for name in ('hatch_time', 'lay_time'):
        settings[name] = 60.0
        G['nudge_setting'](name, +1)
        up = settings[name]
        G['nudge_setting'](name, -1)
        G['nudge_setting'](name, -1)
        check(f'{name}: 60 -> {up:g} up, {settings[name]:g} down', up == 65.0 and settings[name] == 55.0)
        for _ in range(100):
            G['nudge_setting'](name, -1)
        check(f'{name}: bottoms out at {settings[name]:g} s', settings[name] == 5.0)
    settings['lay_time'] = 30.0
    settings['hatch_time'] = 30.0

    print('wild eggs keep coming back, laid ones do not:')
    settings['lay_time'] = 30.0
    home = fresh_park()
    wild_before = [e for e in eggs if not e.get('laid')]
    G['hatch_into_your_bird'](home)
    frames(31)
    laid_egg = laid()[0]
    player.update(x=laid_egg['x'], y=laid_egg['y'])
    G['held'].clear()
    G['try_collect_eggs']()
    check('picking up a laid egg adds no new egg',
          laid_egg not in eggs and len(eggs) == len(wild_before))
    wild = wild_before[0]
    player.update(x=wild['x'], y=wild['y'])
    G['held'].clear()
    G['try_collect_eggs']()
    check('picking up a wild egg still brings a new wild one',
          wild not in eggs and len([e for e in eggs if not e.get('laid')]) == len(wild_before))

    print('pauses and switches:')
    home = fresh_park()
    G['hatch_into_your_bird'](home)
    G['open_main_menu']()
    frames(60)
    check('no laying while the menu is open', not laid())
    G['resume_game']()
    player.update(x=500.0, y=500.0)
    settings['enable_bird_laying'] = False
    frames(60)
    check('none with "Birds lay eggs" turned off', not laid())
    settings['enable_bird_laying'] = True
    frames(29)
    check('its wait was frozen while off, not used up', not laid())
    frames(2)
    check('turned back on, it lays after the rest of its wait', len(laid()) == 1)

    print('boosted birds and old saves:')
    home = fresh_park()
    G['hatch_into_your_bird'](home)
    birds[0]['eggs_to_lay'] = G['BIRD_EGGS_TO_LAY_MAX']
    frames(30.5 * G['BIRD_EGGS_TO_LAY_MAX'] + 60)
    check(f'a bird with {G["BIRD_EGGS_TO_LAY_MAX"]} to lay lays exactly that many ({len(laid())})',
          len(laid()) == G['BIRD_EGGS_TO_LAY_MAX'])
    home = fresh_park()
    G['hatch_into_your_bird'](home)
    del birds[0]['eggs_to_lay'], birds[0]['lay_timer']     # a bird from before laying existed
    frames(31)
    check('a bird from an older save lays its one egg', len(laid()) == 1)

    print('saving:')
    home = fresh_park()
    G['hatch_into_your_bird'](home)
    frames(10)
    G['save_park']('test')
    left = birds[0]['lay_timer']
    G['reset_world']()
    check('the park loads', G['load_park']())
    check(f'the bird still has its egg to lay, with {birds[0]["lay_timer"]:.1f} s left',
          birds[0]['eggs_to_lay'] == 1 and abs(birds[0]['lay_timer'] - left) < 1e-6)
    player.update(x=500.0, y=500.0)
    frames(21)
    check('and lays it on time after loading', len(laid()) == 1)
    G['save_park']('test')
    G['reset_world']()
    G['load_park']()
    check('a laid egg stays a laid egg after loading', len(laid()) == 1)

    print('you only hear birds near you:')
    played = []
    G['_play'] = lambda src, **kw: played.append(kw)
    player.update(x=0.0, y=0.0)
    for dist, expect in ((10.0, 0.5), (70.0, 0.25), (79.0, 0.025), (81.0, None), (500.0, None)):
        played.clear()
        G['fire_bird_call']({'x': dist, 'y': 0.0, 'z': 0.0, 'freq_idx': 0})
        if expect is None:
            check(f'a bird {dist:.0f} m away is silent', not played)
        else:
            vol = played[0]['volume'] if played else None
            check(f'a bird {dist:.0f} m away calls at volume {vol}', vol is not None and abs(vol - expect) < 1e-6)
    played.clear()
    G['fire_bird_ambient']({'x': 300.0, 'y': 0.0, 'z': 0.0, 'freq_idx': 0})
    check('far wing rustles are silent too', not played)

    print('birds chirp, eggs hold a note:')
    import numpy as np
    SR = 44100

    def audio(src):
        d = src.get_queue_source().get_audio_data(10 ** 7)
        return np.frombuffer(d.data, dtype=np.int16).astype(float) / 32767

    # The approved preview clips' recipe, written out independently of the
    # game's code, so a mistake in one can't hide in the other.
    def recipe_glide(f0, f1, dur):
        t = np.arange(int(dur * SR)) / SR
        f = f0 * (f1 / f0) ** (t / dur)
        phase = 2 * np.pi * np.cumsum(f) / SR
        env = np.minimum(t / 0.004, 1) * np.exp(-t / (dur * 0.35))
        return env * (np.sin(phase) + 0.2 * np.sin(2 * phase)) / 1.2

    def recipe(style, note):
        if style == 'chirp':
            return recipe_glide(note, note * 1.5, 0.12)
        return np.concatenate([recipe_glide(note, note * 1.25, 0.06), np.zeros(int(0.04 * SR)),
                               recipe_glide(note * 1.1, note * 1.45, 0.07)])

    def pitch(seg):
        w = seg * np.hanning(len(seg))
        sp = np.abs(np.fft.rfft(w, 1 << 16))
        f = np.fft.rfftfreq(1 << 16, 1 / SR)
        band = (f > 150) & (f < 3000)
        return f[band][sp[band].argmax()]

    worst = 0.0
    for style in G['BIRD_CALL_STYLES']:
        for i, f in enumerate(G['PENTATONIC_FREQS']):
            game = audio(G['_bird_call_sources'][style][i])
            want = recipe(style, f * G['BIRD_OCTAVE'])
            n = min(len(game), len(want))
            worst = max(worst, np.abs(game[:n] - want[:n]).max(), np.abs(game[n:]).max(initial=0))
    check(f'every bird call matches the approved clip recipe (worst sample off by {worst * 32767:.1f} of 32767)',
          worst * 32767 <= 2.0)
    chirp = audio(G['_bird_call_sources']['chirp'][0])
    w = int(0.025 * SR)
    start, end = pitch(chirp[:w]), pitch(chirp[int(0.12 * SR) - w:int(0.12 * SR)])
    check(f'a chirp slides up: {start:.0f} Hz to {end:.0f} Hz', end > start * 1.25)
    lowest = min(pitch(audio(G['_bird_call_sources'][s][0])[:w]) for s in G['BIRD_CALL_STYLES'])
    check(f'no bird starts inside the eggs\' range (lowest start {lowest:.0f} Hz, eggs top out at '
          f'{max(G["PENTATONIC_FREQS"]):.0f})', lowest > max(G['PENTATONIC_FREQS']) * 1.05)
    egg = audio(G['_egg_call_sources'][0])
    e0, e1 = pitch(egg[:int(0.05 * SR)]), pitch(egg[int(0.35 * SR):int(0.4 * SR)])
    check(f'an egg call holds its note ({e0:.0f} Hz to {e1:.0f} Hz)', abs(e1 - e0) < 10)
    styles = set()
    for _ in range(40):
        G['hatch_into_your_bird'](G['baskets'][0])
        styles.add(birds[-1]['call_style'])
    check(f'new birds get both calls ({sorted(styles)})', styles == set(G['BIRD_CALL_STYLES']))
    played.clear()
    real_pick = G['pick_source']
    picked = []
    G['pick_source'] = lambda cat, fallback: (picked.append(fallback), fallback)[1]
    G['fire_bird_call']({'x': 5.0, 'y': 0.0, 'z': 0.0, 'freq_idx': 3})
    check('a bird from an older save still gets a chirp or tweet',
          picked and any(picked[-1] is src for s in G['BIRD_CALL_STYLES'] for src in G['_bird_call_sources'][s]))
    G['pick_source'] = real_pick

    print('baskets hold at least what you carry:')
    G['CARRY_START'] = 40
    check(f'carrying boosted to {G["player_carry_cap"]()}: a basket holds {G["basket_cap"]()}',
          G['basket_cap']() >= G['player_carry_cap']())
    G['CARRY_START'] = 1

    print('the key still works:')
    check('Escape handled', G['on_key_press'](key.ESCAPE, 0) is not None)


run_game(run_checks)
finish('test_birds_lay')
