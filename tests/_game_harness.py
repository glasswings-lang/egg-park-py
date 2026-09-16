# SPDX-License-Identifier: CC0-1.0
"""Run main.py for a test: on a hidden desktop, silent, and with speech off.

    from _game_harness import run_game, check, finish
    def checks(G):          # G reaches the whole game by name, fully booted
        check('something', G['...'] == ...)
    run_game(checks)
    finish('test_name')

main.py opens a window and speaks the moment it runs. So before anything
else this moves onto a hidden Windows desktop (see _isolated_desktop.py),
blocks the screen reader library and forces pyglet's silent audio driver.
Nothing a test does can reach a screen, speakers or a screen reader. If the
hidden desktop is unavailable it refuses to run rather than running
unprotected.

The game's main loop is swapped for the test's checks, so boot happens for
real and then `checks` runs where the game would otherwise start waiting for
keys.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAIN = os.path.join(ROOT, 'main.py')
sys.path.insert(0, HERE)

from _isolated_desktop import enter_isolated_desktop, isolation_detail  # noqa: E402

if not enter_isolated_desktop('eggpark-tests'):
    print('REFUSED: could not move onto a hidden desktop, and running the '
          'game here would take focus from a screen reader.')
    print('  reason:', isolation_detail())
    sys.exit(3)

sys.modules['accessible_output2'] = None       # no speech

# Never let a test rotate away the log from someone's real play session, nor
# touch their saved park: both go to a scratch folder. A test that runs
# several game sessions against ONE save (see test_park_save.py) sets
# EGG_PARK_TEST_DIR so every session shares it.
import tempfile                                # noqa: E402
TEST_DIR = (os.environ.get('EGG_PARK_TEST_DIR')
            or tempfile.mkdtemp(prefix='eggpark-test-'))
PLAY_LOG = os.path.join(TEST_DIR, 'play-log.txt')
PARK_SAVE = os.path.join(TEST_DIR, 'park.json')
os.environ['EGG_PARK_PLAY_LOG'] = PLAY_LOG
os.environ['EGG_PARK_SAVE'] = PARK_SAVE
import pyglet                                  # noqa: E402

pyglet.options['audio'] = ('silent',)

failures = []


def check(label, ok):
    print(('  ok   ' if ok else '  FAIL ') + label)
    if not ok:
        failures.append(label)


class Game:
    """The whole game, reachable by name: `G['eggs']`, `G['try_scan']()`.

    The game is split across the files in eggpark/, and a test shouldn't have
    to know which file a thing lives in. Reading finds it wherever it is.
    Writing replaces it IN the file that owns it, which is what makes
    `G['say'] = spoken.append` work: every caller, in every file, goes through
    that file's copy.
    """

    def __init__(self, main_globals):
        self._main = main_globals
        self._modules = [m for name, m in sorted(sys.modules.items())
                         if name.startswith('eggpark.') and m is not None]

    def _owner(self, name):
        import types
        for m in self._modules:
            value = m.__dict__.get(name, _MISSING)
            if value is not _MISSING and not isinstance(value, types.ModuleType):
                return m
        return None

    def __getitem__(self, name):
        owner = self._owner(name)
        if owner is not None:
            return getattr(owner, name)
        for m in self._modules:           # imported modules: pyglet, time, ...
            if name in m.__dict__:
                return m.__dict__[name]
        return self._main[name]

    def __setitem__(self, name, value):
        owner = self._owner(name)
        if owner is None:
            raise KeyError(f'{name}: no file in eggpark/ defines it')
        setattr(owner, name, value)


_MISSING = object()


def run_game(checks):
    os.chdir(ROOT)
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    source = open(MAIN, encoding='utf-8').read()
    # main.py picks its own audio drivers; keep it on the silent one.
    source = source.replace("pyglet.options['audio']", '_test_ignored_audio')
    main_globals = {'__name__': '__main__', '__file__': MAIN, '_test_ignored_audio': {}}

    def fake_run(*a, **k):
        G = Game(main_globals)
        # Changing a setting saves it. Settings were already loaded from the
        # real file at boot; from here on, saves go to the scratch folder so a
        # test that nudges a slider can't rewrite someone's settings.json.
        G['SETTINGS_FILE'] = os.path.join(TEST_DIR, 'settings.json')
        try:
            checks(G)
        finally:
            G['window'].close()

    pyglet.app.run = fake_run
    exec(compile(source, MAIN, 'exec'), main_globals)


def finish(name):
    if failures:
        print(f'\n{name}: {len(failures)} FAILED')
        sys.exit(1)
    print(f'\n{name}: all checks passed')
