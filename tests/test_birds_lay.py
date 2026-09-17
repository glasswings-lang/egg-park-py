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
    flyoff = G['fire_wild_bird_flyoff']
    G['fire_egg_laid'] = lambda egg: laid_sounds.append(egg)
    settings, eggs, birds, player = G['settings'], G['eggs'], G['birds'], G['player']
    # Most checks here count eggs over minutes; eggs hatching away on the
    # ground mid-count would muddle them. Ground hatching gets its own section.
    settings['enable_ground_hatching'] = False

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

    def clutches():
        return len(laid_sounds)

    # Fixed clutch size for the timing checks, so counts are exact.
    G['CLUTCH_MIN'] = G['CLUTCH_MAX'] = 3

    print('a plain bird lays clutches, again and again:')
    settings['lay_time'] = 30.0
    home = fresh_park()
    laid_sounds.clear()
    G['hatch_into_your_bird'](home)
    bird = birds[0]
    check('is born with no clutch bonus', bird['clutch_bonus'] == 0)
    frames(29)
    check('has not laid before the lay time', not laid())
    frames(2)
    check(f'lays a whole clutch at once ({len(laid())} eggs)', len(laid()) == 3)
    for egg in laid():
        d = math.hypot(egg['x'] - home['x'], egg['y'] - home['y'])
        if not G['LAID_EGG_MIN'] - 0.01 <= d <= G['LAID_EGG_MAX'] + 0.01:
            break
    check('every egg near its home basket', G['LAID_EGG_MIN'] - 0.01 <= d <= G['LAID_EGG_MAX'] + 0.01)
    check(f'one laid sound for the clutch, from one of its eggs ({clutches()})',
          clutches() == 1 and laid_sounds[0] in laid())
    frames(30)
    check(f'and lays again next time round ({len(laid())} eggs, {clutches()} clutches)',
          len(laid()) == 6 and clutches() == 2)
    frames(90)
    check(f'and keeps going ({clutches()} clutches after 2.5 minutes)', clutches() == 5)

    print('clutch sizes:')
    G['CLUTCH_MIN'], G['CLUTCH_MAX'] = 1, 10
    sizes = [G['clutch_size']({'clutch_bonus': 0}) for _ in range(3000)]
    check(f'plain clutches range {min(sizes)}-{max(sizes)}', min(sizes) == 1 and max(sizes) == 10)
    boosted = [G['clutch_size']({'clutch_bonus': 4}) for _ in range(3000)]
    check(f'a +4 bird lays {min(boosted)}-{max(boosted)}, past the ballpark', min(boosted) == 5 and max(boosted) == 14)
    check('a bird from an older save, with no bonus field, lays plain clutches',
          1 <= G['clutch_size']({}) <= 10)
    G['CLUTCH_MIN'] = G['CLUTCH_MAX'] = 3

    print('the setting is honoured:')
    settings['lay_time'] = 90.0
    home = fresh_park()
    G['hatch_into_your_bird'](home)
    frames(60)
    check('nothing at 60 s with a 90 s lay time', not laid())
    frames(31)
    check('laid by 91 s', len(laid()) == 3)

    print('timing settings move in 5 second jumps:')
    for name in ('hatch_time', 'lay_time'):
        settings[name] = 60.0
        G['nudge_setting'](name, +1)
        up = settings[name]
        G['nudge_setting'](name, -1)
        G['nudge_setting'](name, -1)
        check(f'{name}: 60 -> {up:g} up, {settings[name]:g} down', up == 65.0 and settings[name] == 55.0)
        for _ in range(200):
            G['nudge_setting'](name, -1)
        check(f'{name}: bottoms out at {settings[name]:g} s', settings[name] == 5.0)
    settings['lay_time'] = 30.0
    settings['hatch_time'] = 30.0

    print('wild eggs keep coming back, laid ones do not:')
    home = fresh_park()
    wild_before = [e for e in eggs if not e.get('laid')]
    G['hatch_into_your_bird'](home)
    frames(31)
    laid_egg = laid()[0]
    count_before = len(eggs)
    player.update(x=laid_egg['x'], y=laid_egg['y'])
    G['held'].clear()
    G['try_collect_eggs']()
    check('picking up a laid egg adds no new egg',
          laid_egg not in eggs and len(eggs) == count_before - 1)
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
    check('turned back on, it lays after the rest of its wait', len(laid()) == 3)

    print('older saves:')
    home = fresh_park()
    G['hatch_into_your_bird'](home)
    del birds[0]['clutch_bonus'], birds[0]['lay_timer']    # a bird from before clutches
    frames(31)
    check('a bird from an older save lays a plain clutch after a full wait', len(laid()) == 3)
    home = fresh_park()
    G['hatch_into_your_bird'](home)
    birds[0]['eggs_to_lay'] = 0                             # left over from lifetime laying
    frames(31)
    check('an old "no eggs left" count no longer stops it', len(laid()) == 3)

    print('saving:')
    home = fresh_park()
    G['hatch_into_your_bird'](home)
    birds[0]['clutch_bonus'] = 2
    frames(10)
    G['save_park']('test')
    left = birds[0]['lay_timer']
    G['reset_world']()
    check('the park loads', G['load_park']())
    check(f'the bird keeps its bonus and its wait ({birds[0]["lay_timer"]:.1f} s left)',
          birds[0]['clutch_bonus'] == 2 and abs(birds[0]['lay_timer'] - left) < 1e-6)
    player.update(x=500.0, y=500.0)
    frames(21)
    check(f'and lays on time after loading, bonus included ({len(laid())} eggs)', len(laid()) == 5)
    G['save_park']('test')
    G['reset_world']()
    G['load_park']()
    check('laid eggs stay laid eggs after loading', len(laid()) == 5)
    G['CLUTCH_MIN'], G['CLUTCH_MAX'] = 1, 10

    speech_log_event = G['log_event']

    print('ground hatching:')
    settings['enable_ground_hatching'] = True
    settings['hatch_time'] = 20.0
    settings['lay_time'] = 900.0
    G['CLUTCH_MIN'] = G['CLUTCH_MAX'] = 3
    flew = []
    G['fire_wild_bird_flyoff'] = lambda position=None: flew.append(position)
    home = fresh_park()
    for e in eggs:
        e['hatch_timer'] = 20.0
    G['hatch_into_your_bird'](home)
    G['lay_clutch'](birds[0])
    wild_before = [e for e in eggs if not e.get('laid')]
    check('a fresh clutch and four wild eggs lying out', len(laid()) == 3 and len(wild_before) == 4)
    frames(19)
    check('nothing hatches before the hatch time', len(laid()) == 3 and not flew)
    frames(2)
    check(f'the uncollected clutch hatches away ({len(laid())} laid left, {len(flew)} flew off)',
          not laid() and len(flew) == 7)
    wild_now = [e for e in eggs if not e.get('laid')]
    check('wild eggs that hatched away are replaced by new ones',
          len(wild_now) == 4 and not any(e in wild_before for e in wild_now))
    check('each flies off from where it lay', all(p is not None for p in flew))

    print('a park where every egg runs out at the same instant:')
    # Not hypothetical: a real save held 4,161 eggs each with exactly 180.0
    # seconds left, because the timer only ticks while ground hatching is on
    # and they had all been stored untouched. Turning the setting on would
    # have hatched the lot in one frame.
    settings['enable_ground_hatching'] = True
    settings['hatch_time'] = 180.0
    settings['lay_time'] = 900.0
    fresh_park()
    birds.clear()
    eggs.clear()
    flew.clear()
    for i in range(4161):
        eggs.append({'x': 300.0 + i * 0.1, 'y': 300.0, 'z': 0.0, 'freq_idx': 0,
                     'hatch_timer': 180.0, 'laid': True})
    player.update(x=0.0, y=0.0)
    logged = []
    G['log_event'] = logged.append
    per_frame = []
    before = len(eggs)
    G['tick_hatching'](181.0)                  # everything is now overdue
    per_frame.append(before - len(eggs))
    frames_taken = 0
    while eggs and frames_taken < 3000:
        before = len(eggs)
        G['tick_hatching'](1 / 60)
        per_frame.append(before - len(eggs))
        frames_taken += 1
    cap = G['GROUND_HATCH_PER_FRAME']
    check(f'no frame hatches more than {cap} (the most any frame did: {max(per_frame)})',
          max(per_frame) <= cap)
    check(f'all 4161 still leave, over {frames_taken} frames '
          f'({frames_taken / 60:.1f} seconds)', not eggs and len(flew) == 4161)
    hatch_lines = [line for line in logged if 'hatched on the ground' in line]
    check(f'and the log gets {len(hatch_lines)} lines, not 4161', len(hatch_lines) < 500)
    check('each line counts its own frame',
          all('egg(s) hatched' in line for line in hatch_lines))
    G['log_event'] = speech_log_event

    print('picking up keeps the countdown:')
    home = fresh_park()
    egg = eggs[0]
    egg['hatch_timer'] = 20.0
    frames(15)
    player.update(x=egg['x'], y=egg['y'])
    G['held'].clear()
    G['try_collect_eggs']()
    left = G['held'][0]['hatch_timer'] if G['held'] else None
    check(f'an egg lifted with 5 s left still has about 5 s ({left:.1f})', left is not None and 4.5 < left < 5.5)
    settings['enable_ground_hatching'] = False
    G['held'].clear()
    egg = eggs[0]
    egg['hatch_timer'] = 3.0
    player.update(x=egg['x'], y=egg['y'])
    G['try_collect_eggs']()
    check('with ground hatching off, a lifted egg starts a full hatch time',
          G['held'] and G['held'][0]['hatch_timer'] == settings['hatch_time'])
    G['held'].clear()
    player.update(x=500.0, y=500.0)
    before = [dict(e) for e in eggs]
    frames(40)
    check('and with it off, eggs on the ground never hatch away',
          [(e['x'], e['y']) for e in eggs] == [(e['x'], e['y']) for e in before])

    print('hearing a ground egg hatch:')
    played = []
    G['fire_wild_bird_flyoff'] = flyoff
    G['_play'] = lambda src, **kw: played.append(kw)
    player.update(x=0.0, y=0.0)
    G['fire_wild_bird_flyoff'](position=(10.0, 0.0, 0.0))
    check('nearby: heard, from where it lay', played and played[-1]['position'] == (10.0, 0.0, 0.0)
          and played[-1]['volume'] == 0.5)
    played.clear()
    G['fire_wild_bird_flyoff'](position=(300.0, 0.0, 0.0))
    check('far away: silent', not played)
    G['fire_wild_bird_flyoff']()
    check('from your hands: at you, full volume', played and played[-1]['position'] is None
          and played[-1]['volume'] == 0.5)
    settings['hatch_time'] = 30.0
    settings['enable_ground_hatching'] = False

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
