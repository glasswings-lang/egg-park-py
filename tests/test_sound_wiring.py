"""A sound has to be registered in several places. This catches a missed one.

Adding a sound means touching `_SAMPLE_CATEGORIES`, `_VOLUME_CATEGORIES`,
`SOUND_CATALOGUE` and `docs/SOUNDS.md`. Four places, and forgetting any of
them fails quietly:

  * no volume slider  -> the sound ignores its own setting and plays at full
  * not in SOUND_CATALOGUE -> nobody can find out what it means
  * not in SOUNDS.md  -> nobody knows what to record

None of those raise. The game just behaves slightly wrongly forever.

Run: python tests/test_sound_wiring.py

Read by regex rather than by importing, because loading the game opens a
window. The registrations live in different files under eggpark/, so all of
them are read as one text.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, 'eggpark')
SOUNDS_MD = os.path.join(ROOT, 'docs', 'SOUNDS.md')

# --- Deliberate exceptions -------------------------------------------------
#
# Named here with the reason, so the test stays green and keeps guarding.
# A check that fails on purpose forever is one that gets ignored, and then
# it isn't guarding anything.

# Cues that deliberately share another cue's volume slider. Two states of
# one thing want ONE control: "Volume: basket chimes" has to mean every
# basket chime, or turning it down silently applies to half the world.
SHARES_VOLUME_WITH = {
    'basket-chime-found': 'basket-chime',
    'footstep-basket': 'footstep',
    'footstep-chest': 'footstep',
    'chest-chime-found': 'chest-chime',
    'basket-pour': 'basket-deposit',
}

# Cues deliberately absent from the sound test.
NOT_IN_SOUND_TEST = {
    'ambience': 'a continuous bed rather than a cue, and half a minute long '
                '- previewing it would mean sitting through it',
}

src = '\n'.join(open(os.path.join(PACKAGE, f), encoding='utf-8').read()
                for f in sorted(os.listdir(PACKAGE)) if f.endswith('.py'))
md = open(SOUNDS_MD, encoding='utf-8').read()


def block(pattern, text):
    match = re.search(pattern, text, re.S | re.M)
    if not match:
        print(f'FAIL: could not find {pattern!r} - has it been renamed?')
        sys.exit(1)
    return match.group(1)


categories = re.findall(r"'([a-z0-9-]+)'",
                        block(r'_SAMPLE_CATEGORIES = \((.*?)\)', src))
volumes = {v.replace('_', '-') for v in
           re.findall(r"\('vol_([a-z0-9_]+)'",
                      block(r'_VOLUME_CATEGORIES = \[(.*?)^\]', src))}
in_test = re.findall(r"^\s*\('([a-z0-9-]+)'",
                     block(r'SOUND_CATALOGUE = \[(.*?)^\]', src), re.M)
documented = set(re.findall(r'^### `([a-z0-9-]+)`', md, re.M))

failures = []


def check(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        failures.append(label)


print(f'{len(categories)} sound categories')
print()

print('every category has a volume slider, or shares one on purpose:')
for c in categories:
    if c in SHARES_VOLUME_WITH:
        parent = SHARES_VOLUME_WITH[c]
        check(f'{c} shares the {parent} slider',
              c not in volumes and parent in volumes)
    else:
        check(f'{c}', c in volumes)

print()
print('every category is in the sound test, or excluded on purpose:')
for c in categories:
    if c in NOT_IN_SOUND_TEST:
        check(f'{c} excluded: {NOT_IN_SOUND_TEST[c]}', c not in in_test)
    else:
        check(f'{c}', c in in_test)

print()
print('every category is described in SOUNDS.md:')
for c in categories:
    check(f'{c}', c in documented)

print()
print('nothing dangling:')
check('no volume slider without a category',
      not (volumes - set(categories)))
check('no sound-test entry that is not a real category',
      not (set(in_test) - set(categories)))
check('no SOUNDS.md section for a category that does not exist',
      not (documented - set(categories)))
check('no category listed twice in the sound test',
      len(in_test) == len(set(in_test)))
check('no category listed twice in _SAMPLE_CATEGORIES',
      len(categories) == len(set(categories)))

print()
if failures:
    print(f'FAILED: {len(failures)} check(s)')
    print()
    print('Adding a sound means all four of these:')
    print('  1. name it in _SAMPLE_CATEGORIES')
    print('  2. give it a slider in _VOLUME_CATEGORIES, or add it to')
    print('     SHARES_VOLUME_WITH at the top of this file and say why')
    print('  3. add it to SOUND_CATALOGUE with a label and what it MEANS')
    print('  4. write a ### section for it in docs/SOUNDS.md')
    sys.exit(1)
print('test_sound_wiring: all checks passed')
