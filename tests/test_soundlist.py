"""Exercise sounds.txt parsing and template generation from main.py.

main.py opens a window on import, so the functions are lifted out by AST and
run in a controlled namespace. That means this tests the REAL source, not a
copy of it - a copy would drift and prove nothing.
"""
import ast
import os
import sys
import tempfile

MAIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'main.py')
WANT = ('_parse_sounds_list', 'write_sounds_template', 'sound_list_problem_for')

src = open(MAIN, encoding='utf-8').read()
tree = ast.parse(src)

sandbox = tempfile.mkdtemp(prefix='soundlist-test-')
ns = {
    'os': os,
    '_script_dir': sandbox,
    'SOUNDS_LIST_FILE': os.path.join(sandbox, 'sounds.txt'),
    '_sound_list_problems': [],
    '_SAMPLE_CATEGORIES': ('egg-call', 'footstep', 'refuse', 'ambience'),
    'SOUND_CATALOGUE': [
        ('egg-call', 'Egg call', 'An egg calling.', None),
        ('footstep', 'Footstep', 'Your own feet.', None),
        ('refuse', 'Hands full', 'You cannot carry that.', None),
    ],
}
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in WANT:
        exec(compile(ast.Module([node], []), MAIN, 'exec'), ns)
missing = [n for n in WANT if n not in ns]
if missing:
    print('FAIL: could not lift', missing)
    raise SystemExit(1)

parse = ns['_parse_sounds_list']
template = ns['write_sounds_template']
problem_for = ns['sound_list_problem_for']
problems = ns['_sound_list_problems']
PATH = ns['SOUNDS_LIST_FILE']

failures = []


def check(label, cond):
    # ascii() rather than repr(): a Windows console is cp1252, and printing a
    # non-ASCII label raises UnicodeEncodeError - so a test about handling
    # odd input would die on its own output rather than on the code.
    print(f"  {'ok  ' if cond else 'FAIL'} {ascii(label)[1:-1]}")
    if not cond:
        failures.append(label)


def write(text):
    with open(PATH, 'w', encoding='utf-8') as f:
        f.write(text)


real = os.path.join(sandbox, 'my take.wav')
open(real, 'wb').write(b'RIFF____WAVE')

print('template:')
check('creates the file', template() is True)
body = open(PATH, encoding='utf-8').read()
check('refuses to overwrite an existing one', template() is False)
check('every cue is named', all(c in body for c in ('egg-call', 'footstep', 'refuse')))
check('meanings are included', 'An egg calling.' in body)
check('every fill-in line is switched off',
      all(l.startswith('# ') for l in body.splitlines() if ' = ' in l and not l.startswith(' ')))
check('the explaining is NOT hash-prefixed',
      sum(1 for l in body.splitlines() if l.startswith('#')) < 8)
check('parses to nothing while untouched', parse() == {})
check('and reports no problems', problems == [])
check('force rewrites', template(force=True) is True)

print()
print('parsing:')
write(f'egg-call = {real}\n')
check('absolute path', parse() == {'egg-call': [real]})

write(f'egg-call = my take.wav\n')
check('relative to the game folder', parse() == {'egg-call': [real]})

write(f'egg-call = "{real}"\n')
check('quotes are optional', parse() == {'egg-call': [real]})

write(f'EGG_CALL  =  {real}  \n')
check('case, spacing and underscores forgiven', parse() == {'egg-call': [real]})

write(f'footstep = {real}\nfootstep = my take.wav\n')
check('same cue twice gives two variants', len(parse().get('footstep', [])) == 2)

write(f'# egg-call = {real}\nfootstep = {real}\n')
check('commented lines ignored', parse() == {'footstep': [real]})

write(f'footstep = {real}   # my best one\n')
check('trailing comment stripped', parse() == {'footstep': [real]})

write('\n\n   \n')
check('blank file is fine', parse() == {})

# The three ways a line is "just writing". These exist so the file can
# explain itself in plain prose instead of putting a # in front of every
# line - a hundred spoken hashes made the instructions the hardest part.
write('    footstep = C:\\Users\\you\\recordings\\step.wav\n')
check('an indented example is ignored', parse() == {} and problems == [])

write('\t footstep = C:\\Users\\you\\recordings\\step.wav\n')
check('tab-indented too', parse() == {} and problems == [])

# ...but an indented line pointing at a file that REALLY EXISTS is not an
# example, it is a real line with a stray space, and saying nothing about
# it is the silent failure this file exists to prevent.
write(f'    footstep = {real}\n')
parse()
check('an indented line that would have worked is reported, not swallowed',
      len(problems) == 1 and 'space' in problems[0][1])

write('This sentence explains something and is ignored.\n'
      f'footstep = {real}\n')
check('a plain sentence is ignored', parse() == {'footstep': [real]})

write('Up and Down move through the sounds\n')
check('prose with no equals sign raises no complaint',
      parse() == {} and problems == [])

print()
print('problems are reported, not swallowed:')
write('wibble = somewhere.wav\n')
parse()
check('an unknown cue name', len(problems) == 1 and 'wibble' in problems[0][1])

write('egg-call = nope-not-here.wav\n')
parse()
check('a file that is not there', len(problems) == 1)
check('and it names the cue, for the sound test',
      problem_for('egg-call') != '' and problem_for('footstep') == '')

write('egg-call =\n')
parse()
check('no file given', len(problems) == 1)

write(f'egg-call = {real}\n')
parse()
check('problems clear on a good reparse', problems == [])

print()
print('never raises:')
for text in ('=', '= = =', 'a' * 5000, '\x00\x01', '\u4e2d\u6587 = x.wav',
             f'egg-call = {real}\n' * 300):
    try:
        write(text)
        parse()
        check(f'{text[:14]!r}', True)
    except Exception as exc:
        check(f'{text[:14]!r} raised {exc!r}', False)

print()
if failures:
    print(f'FAILED: {len(failures)}')
    raise SystemExit(1)
print('test_soundlist: all checks passed')
