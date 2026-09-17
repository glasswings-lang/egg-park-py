# Sound Design Specs — Egg Park

Living spec for the sampled audio that will replace Egg Park's synth
placeholders. Every mechanic in the game is now wired with a placeholder
sound; this document is the recording plan to take us from those
placeholders to the final game audio.

**The sample-bank wiring is already done for every category.** Drop a
`.wav` into `public/audio/samples/` with the naming below and the game
uses it on the next reload (R in-game, or restart). No code change needed
per category. Fallback is per-file, not per-category — recording only
some notes in a pitched category or some variants in a non-pitched one
is fine; missing files keep the synth placeholder for those specific
picks.

Each category below has: what triggers it, character notes, file naming,
duration, whether it's spatialized (positioned in 3D space) or not, and
how many files to record.

## File conventions

- **Format**: 44.1 kHz `.wav`, mono unless explicitly noted. Mono routes
  through binaural panning correctly; stereo gets summed into mono first
  and loses spatial cues. (For non-spatial sounds — collect, refuse,
  status cues — stereo is fine but mono is still smaller and cleaner.)
- **Headroom**: peak normalize to **−3 dBFS** or lower.
- **Naming**: lowercase, hyphens. Filename minus extension is the in-code
  name. Variants are numbered.
- **Where files go**: `public/audio/samples/` in the project root.

## The recording loop

Use the **Sound test**, from the main menu. It lists every cue below with
what it means, tells you whether you're hearing a recording or the
placeholder, and lets you swap between them without moving files or
restarting.

1. Record a take, save it into the samples folder with the right name.
2. **R** in the sound test — reloads from disk.
3. **Enter** — hear your take.
4. **S** — hear the placeholder it replaces. **S** again to come back.

The placeholders are scaffolding, not a target. Several of them were
actively wrong about their own entries in this file (see *A note on square
waves* at the end). **Where a placeholder and the description here
disagree, the description wins.**

**Every category below appears in the sound test.** If you add one to the
engine, add it there too — a cue nobody can identify is a cue that isn't
really documented, whatever this file says about it.

## Adding a NEW sound to the game

Not "using a recording" — that's `sounds.txt` above. This is adding a cue
that didn't exist, in code.

A sound has to be registered in **four** places, and forgetting any of them
fails quietly. Nothing raises; the game just behaves slightly wrongly
forever.

1. **Build the source** in `eggpark/sounds.py` — `_sine`, `_triangle` or
   `_noise_burst`, near the other `_*_source` definitions. Read *A note on
   square waves* at the bottom of this file first.
2. **Name it in `_SAMPLE_CATEGORIES`** (`eggpark/sounds.py`). Lowercase, hyphenated. This is what
   the filename and the `sounds.txt` line will use.
3. **Give it a volume slider in `_VOLUME_CATEGORIES`** (`eggpark/prefs.py`) — `vol_<name>` with
   hyphens turned into underscores. *Or* deliberately route it through
   another cue's slider, and say so in `SHARES_VOLUME_WITH` in
   `tests/test_sound_wiring.py`. Two states of one thing should share one
   control; a missing slider means the cue silently ignores its own setting.
4. **Write the `fire_*` helper**, going through
   `pick_source(category, fallback=…)` and `_play(…, category=…)`. Never
   reach for a `_source` directly — that's what makes the recordings switch
   a single switch instead of twenty-four.
5. **Add it to `SOUND_CATALOGUE`** (`eggpark/sounds.py`) with a label and *what it means*. A cue
   nobody can identify is a cue that isn't really documented, whatever this
   file says about it.
6. **Write a `### ` section for it here**, so there's something to record
   against.

Then:

```
python tests/test_sound_wiring.py
```

That checks all four registrations against each other and prints the list
above if anything is missing. It exists because this is exactly the kind of
step that gets forgotten.

### Filename pattern

Same for every category: `{category}-{variant}.wav`, numbered from 1.

Examples: `egg-call-1.wav`, `basket-chime-2.wav`, `footstep-3.wav`,
`scan-basket-ping-1.wav`.

If a category needs only one variant, drop the `-1`: `refuse.wav`,
`basket-discover.wav`. (Both shapes are accepted — `refuse.wav` and
`refuse-1.wav` work equally well for a single-variant category.)

The engine picks one at random per fire from whatever variants you've
recorded. Empty categories use the synth placeholder.

## Tonal anchor (synth placeholders only)

While you're recording, the synth placeholders use **A minor pentatonic**
(`a3 c4 d4 e4 g4`) so two eggs sound musically distinct from each other
instead of all hitting the same pitch.

**Category is carried by REGISTER, not by timbre.** Every pitched thing
used to draw from the same five mid-octave notes, with only waveform
telling them apart — and it didn't work. Eggs call more often than baskets
chime, and a triangle buries a sine, so baskets were inaudible under the
eggs they sat on top of. Three octaves now:

| | pitches | voice |
| --- | --- | --- |
| **Baskets** | 110–196 Hz (one octave **down**) | sine unfound, triangle found |
| **Eggs** | 220–392 Hz (the anchor) | triangle |
| **Birds** | 440–784 Hz (one octave **up**) | triangle |
| **Origin** | 155.6 Hz, Eb3 | triangle, long bell |

Origin is the one pitch deliberately outside the scale, so it can never
land on a basket however the octave constants are tuned. Home should sound
like home, not like another landmark.

**If you record samples, keep them in their register.** A basket sample
pitched up into egg territory undoes this entirely, and it will sound fine
in isolation — the failure only appears when several things sound at once,
which is most of the time. Once you record a category, the synth fades out for that category
and your samples take over — they don't have to match any pitch, and
spatial direction (HRTF) carries which-egg-is-where instead of pitch.

You don't need to think about notes when recording. Just record sounds
you like; the engine plays them at the right positions.

---

## Categories

### `egg-call` — 5 variants
- **Trigger**: The nearest audible egg calls every 1.5 seconds.
- **Spatial**: yes, at egg position. Player hears distance + direction.
- **Duration**: 0.3–0.8 s.
- **Character**: A short, gentle, hopeful vocal-like call. Think small
  bird-chirp or coo, not whistle. "Live thing in there," not a tone.
- **Why 5 variants**: this fires constantly while you're walking near
  eggs — the ear locks onto repeats fast at this rate, so more variants
  buys more before the pattern reads as looped.
- **Files** (5):
  - `egg-call-1.wav`
  - `egg-call-2.wav`
  - `egg-call-3.wav`
  - `egg-call-4.wav`
  - `egg-call-5.wav`

### `basket-chime` — 3 variants
- **Trigger**: Baskets you have NOT yet found chime periodically. Interval
  scales with proximity: ~4 s when far, ~1 s when standing nearby. Only the
  nearest audible basket chimes at any moment, so cross-talk between baskets
  isn't a concern.
- **Spatial**: yes, at basket position.
- **Duration**: 0.8–1.5 s.
- **Character**: Soft hollow knock, wooden bell, or chime with long-ish
  tail. Not metallic. Imagine a wind chime made of driftwood.
- **Files** (3):
  - `basket-chime-1.wav`
  - `basket-chime-2.wav`
  - `basket-chime-3.wav`

### `basket-chime-found` — 3 variants
- **Trigger**: Exactly as above, but for a basket you have already
  discovered. Same note, same position, same interval — only the voice
  changes.
- **Spatial**: yes, at basket position.
- **Duration**: 0.8–1.5 s.
- **Character**: The **same instrument** as `basket-chime`, played closer
  or brighter — struck rather than brushed, a touch more body. It must read
  as *the same object in a different state*, not as a different object. If
  the two sound like unrelated things, the world stops being one place.
- **Why it exists**: baskets used to be silent until discovered, so
  stepping on one switched its chime on and you could hear the world
  change. That gate was removed because it made baskets impossible to find
  by ear — the beacon only came on once you no longer needed it. This
  category puts the reward back without bringing the bug with it.
- **If you don't record it**: the synth triangle placeholder is used, so
  the two states stay distinguishable either way.
- **Files** (3):
  - `basket-chime-found-1.wav`
  - `basket-chime-found-2.wav`
  - `basket-chime-found-3.wav`

### `scan-egg-ping` — 5 variants
- **Trigger**: Pressing Space scans. Each egg within 200 m emits a single
  ping, timed so close items ping first, distant items ping later. Sweep
  takes ~2.5 s total.
- **Spatial**: yes.
- **Duration**: 0.2–0.4 s. Should be shorter than `egg-call` so the scan
  feels brisk.
- **Character**: A clean, locating "ping" with a hint of life in it.
  Pulse-y or slightly modulated, not a flat beep.
- **Why 5 variants**: a single scan can fire several pings within a
  couple of seconds, so a small pool would read as a sequence of the same
  sound. More variants gives the sweep texture.
- **Files** (5):
  - `scan-egg-ping-1.wav`
  - `scan-egg-ping-2.wav`
  - `scan-egg-ping-3.wav`
  - `scan-egg-ping-4.wav`
  - `scan-egg-ping-5.wav`

### `scan-basket-ping` — 3 variants
- **Trigger**: Pressing Space scans. Each basket within 200 m (discovered
  or not) emits a single ping. This is how you find undiscovered baskets
  in the first place — scan, hear the direction, walk that way.
- **Spatial**: yes.
- **Duration**: 0.3–0.6 s. Slightly longer than egg ping so the two are
  distinguishable in a busy scan.
- **Character**: Hollower than the egg ping — woody, basket-shaped. Slower
  pulse than the egg pings. Should be tonally distinct enough from
  `scan-egg-ping` that you can tell at a glance whether the scan found
  eggs or baskets.
- **Files** (3):
  - `scan-basket-ping-1.wav`
  - `scan-basket-ping-2.wav`
  - `scan-basket-ping-3.wav`

### `scan-guide` — 1 variant
- **Trigger**: After Space finds an egg, or B finds a basket with room, this
  repeats until you arrive, the target is gone or full, or you scan again.
- **Spatial**: direction only. It plays a short way off toward the target,
  never at it, so distance doesn't fade it. The game sets its loudness.
- **Duration**: 0.08–0.15 s. It can repeat six times a second up close, so
  anything longer smears into a buzz.
- **Character**: A short, clean pluck with a clear pitch. The game changes
  the pitch of this recording to say which way the target is (steady when
  you face it, sinking and wobbling when you don't), so it needs a pitch
  you can follow. A noisy or unpitched sound loses the whole direction cue.
  Keep it a different waveform from the triangle chimes and bird calls it
  shares a register with; the placeholder is a pure sine.
- **Don't** build in a volume swell or tail: speed and loudness are how it
  says distance, and a recording with its own shape fights that.
- **Files** (1):
  - `scan-guide.wav`

### `bird-call` — 5 variants
- **Trigger**: Hatched birds wander the park and call every 8–16 seconds.
  Only birds within 80 m can be heard, fading out over the last 20 m.
- **Spatial**: yes.
- **Duration**: 0.1–0.3 s.
- **Character**: CHIRPS: pitch that moves, fast and upward. This is what
  tells a bird from an egg, and it matters more than pitch height: the
  placeholder used to be the egg call an octave up in the same voice, and
  the ear fused the two, so eggs could only be found by scanning. Eggs hold
  a steady note; a bird recording must not. Keep it above the eggs
  (440 Hz and up). The placeholders are a single upward chirp and a double
  tweet; each bird keeps one for life.
- **Why 5 variants**: as you accumulate birds, several are calling at
  staggered intervals — the ear locks onto repeats fast with overlapping
  sources.
- **Files** (5):
  - `bird-call-1.wav`
  - `bird-call-2.wav`
  - `bird-call-3.wav`
  - `bird-call-4.wav`
  - `bird-call-5.wav`

---

### `egg-collect` — 3 variants
- **Trigger**: Walking into an egg.
- **Spatial**: no (plays at listener — it's "yours now").
- **Duration**: 0.3–0.6 s.
- **Character**: Brief, warm, "settled in." Soft, not chimey.
- **Files** (3):
  - `egg-collect-1.wav`
  - `egg-collect-2.wav`
  - `egg-collect-3.wav`

### `refuse` — 1 variant
- **Trigger**: Walking onto an egg while at carry capacity. Egg stays in
  the world; player has to deposit first.
- **Spatial**: no.
- **Duration**: 0.15–0.30 s.
- **Character**: A small "nope" — soft, deflated, not harsh. Could be a
  brief downward sigh.
- **THIS FIRES A LOT.** Carry capacity starts at one, so every egg you walk
  past while holding one sets it off. Treat it like a footstep for fatigue
  purposes, not like an event.
- **It is not an error sound.** Nothing went wrong and you didn't press
  anything — you walked past something you'll come back for.
- **`refuse` and `fumble` are a pair.** Both are soft negatives and neither
  is harsher than the other; they differ in *weight and pitch*, not in
  aggression. Record them back to back. Since this one fires far more often,
  it's the one to judge for fatigue.
- **The placeholder used to contradict this entry**: a square wave at 110 Hz
  with a 5 ms attack, i.e. a buzz with a click on the front, at half volume,
  played right at the listener. It was genuinely frightening. The spec here
  was right; the synth was wrong. If you record this one, trust the
  paragraph above and not whatever the placeholder happens to sound like.
- **Files** (1):
  - `refuse.wav`

### `basket-discover` — 1 variant
- **Trigger**: First time walking within 2 m of a basket. Fires once per
  basket, ever. Bumps capacity and announces the discovery.
- **Spatial**: yes, at basket position.
- **Duration**: 1.0–2.0 s.
- **Character**: Warm, settling, a touch celebratory but understated. The
  basket "woke up" and said hello.
- **Files** (1):
  - `basket-discover.wav`

### `basket-deposit` — 3 variants
- **Trigger**: F pressed while on a discovered basket with eggs in hand.
- **Spatial**: yes, at basket position.
- **Duration**: 0.4–0.8 s.
- **Character**: Soft thunk + slight settle. Eggs nestling into the basket.
- **Files** (3):
  - `basket-deposit-1.wav`
  - `basket-deposit-2.wav`
  - `basket-deposit-3.wav`

### `basket-full` — 1 variant
- **Trigger**: F pressed when basket is at capacity.
- **Spatial**: no.
- **Duration**: 0.15–0.30 s.
- **Character**: Same family as `refuse` but heftier — "this basket has
  enough." Could share its character; consider recording back-to-back so
  they pair.
- **This is good news.** You filled it. It reports a job finishing, not a
  failure — warm and closed, never a warning. The placeholder was a square
  wave with a 5 ms attack, which is the medical-alarm palette, for the sound
  of something going right.
- Keep it **short**. A long sustained tone in the basket register is a
  chime, and this must never be mistaken for one.
- **Files** (1):
  - `basket-full.wav`

### `hatch-in-basket` — 3 variants
- **Trigger**: An egg's hatch timer reaches 0 while in a basket. A new
  bird is born and joins your roster.
- **Spatial**: yes, at the basket where the bird hatched.
- **Duration**: 1.0–2.0 s.
- **Character**: Crack + small triumphant chirp. Warm, satisfying. The
  beginning of a new bird's life.
- **Files** (3):
  - `hatch-in-basket-1.wav`
  - `hatch-in-basket-2.wav`
  - `hatch-in-basket-3.wav`

### `chest-chime` — 1 variant
- **Trigger**: The nearest chest within 80 m, one you haven't found yet.
  Faster as you get closer, on its own timer apart from baskets.
- **Spatial**: yes.
- **Duration**: 1.0–1.5 s.
- **Character**: Must not sound like a basket, egg, bird or the guide. The
  placeholder is a struck metal bell (overtones that don't line up with the
  note) at A flat 3. A real chest soundscape is still to be designed.
- **Files** (1):
  - `chest-chime.wav`

### `chest-chime-found` — 1 variant
- **Trigger**: The same, for a chest you have found. Shares the chest chime
  volume slider.
- **Spatial**: yes.
- **Character**: The same voice as `chest-chime`, brighter.
- **Files** (1):
  - `chest-chime-found.wav`

### `chest-discover` — 1 variant
- **Trigger**: Walking onto a chest for the first time. Its three gifts are
  rolled and spoken right after.
- **Spatial**: yes, at the chest.
- **Duration**: 1.5–2.5 s.
- **Character**: A reveal. The placeholder strikes the bell, then a fifth above.
- **Files** (1):
  - `chest-discover.wav`

### `scan-chest-ping` — 1 variant
- **Trigger**: A chest answering Space, or C / Shift+C picking one.
- **Spatial**: yes.
- **Duration**: 0.2–0.5 s.
- **Character**: A short strike of the chest voice.
- **Files** (1):
  - `scan-chest-ping.wav`

### `egg-laid` — 1 variant
- **Trigger**: One of your birds lays an egg, a short way from its home
  basket.
- **Spatial**: yes, at the new egg.
- **Duration**: 0.2–0.5 s.
- **Character**: A soft, rounded plop or settle. It says "an egg is here
  now", so it belongs in the egg register (220–392 Hz), and it should
  sound different from the egg call itself, which that egg starts making.
- **Files** (1):
  - `egg-laid.wav`

### `wild-bird-flyoff` — 3 variants
- **Trigger**: A held egg's hatch timer reaches 0 before you reach a
  basket. The bird flies off into the world — not yours. Also, with ground
  hatching on, an egg nobody rescued hatching where it lay.
- **Spatial**: from a held egg, no (plays at listener — you're losing the
  bird, it's a personal loss, not a position cue). From an egg on the
  ground, yes, from where it lay, and only within 80 m.
- **Duration**: 1.0–2.0 s.
- **Character**: Crack + chirp like `hatch-in-basket`, but with a
  "flutter away" tail. The bird is leaving you. Bittersweet — not a
  punishment sound, just a consequence.
- **Not hiss.** The built-in one was 1.5 s of raw white noise and was
  reported as sounding like a can of compressed air. It is now a handful of
  wingbeats: short low-passed pulses with a fast attack, starting quick and
  spreading out, each quieter than the last as the bird gets away. Cut at
  1100 Hz — below the footsteps (5 kHz) and above the ambience bed (200 Hz),
  so it moves air without becoming either a footfall or weather. A recording
  should follow the same rule: wings, low, separate beats, nothing in the
  treble.
- **Files** (3):
  - `wild-bird-flyoff-1.wav`
  - `wild-bird-flyoff-2.wav`
  - `wild-bird-flyoff-3.wav`

### `footstep` — 5 variants
- **Trigger**: Fires once per meter walked. Cadence implicitly follows
  the player's walk speed — default 2.0 m/s = ~2 steps/sec.
- **Spatial**: no (plays at listener — these are *your* footsteps).
- **Duration**: 0.10–0.25 s.
- **Character**: Soft footfall on grass / dirt / forest floor. Quick,
  natural, not booted on concrete. Should be subtle enough that constant
  walking doesn't fatigue — these fire a *lot*, more than any other
  sound. Record 5 variants so the rotation has enough variety that the
  ear doesn't lock onto a repeat pattern.
- **Files** (5):
  - `footstep-1.wav`
  - `footstep-2.wav`
  - `footstep-3.wav`
  - `footstep-4.wav`
  - `footstep-5.wav`

### `footstep-basket` — 3 variants
- **Trigger**: Same as `footstep`, but fires instead of it while you are
  stood within depositing range of a basket (2 m). The surface underfoot
  changes at exactly the point **F** starts working.
- **Spatial**: no (plays at listener — still your own feet).
- **Duration**: 0.15–0.30 s. May run slightly longer than open-ground
  steps.
- **Character**: The same foot, a different floor. Softer and duller —
  something that gives underfoot: woven basket rim, straw, dry reed. Not a
  thud, not a creak-as-event. It should be immediately obvious that the
  ground changed without being a sound you'd get tired of standing on.
- **Why it exists**: the chime tells you a basket is *near* and gets
  louder as you approach, but never tells you you're *on* it — which is the
  one thing you need to know before pressing F.
- **Files** (3):
  - `footstep-basket-1.wav`
  - `footstep-basket-2.wav`
  - `footstep-basket-3.wav`

### `footstep-chest` — 3 variants
- **Trigger**: Same as `footstep`, but fires instead of it while you are
  stood within depositing range of a chest (5 m). Like the basket step, it
  changes at exactly the point **F** starts working.
- **Spatial**: no (plays at listener — still your own feet).
- **Duration**: 0.15–0.30 s.
- **Character**: A heavier, hollower knock than the basket: a boot on a
  wooden lid. The built-in one rings at D4, a little under 300 Hz below the
  basket step's D5. It must never be mistaken for either the ground or a
  basket.
- **Files** (3):
  - `footstep-chest-1.wav`
  - `footstep-chest-2.wav`
  - `footstep-chest-3.wav`

### `egg-warning` — 2 variants
- **Trigger**: Fires once per second on any held or basketed egg whose
  hatch timer is in its last 5 seconds. Same sample plays from the
  listener (held) or from the basket position (basketed).
- **Spatial**: yes when fired from a basket, no when fired for a held egg.
- **Duration**: 0.20–0.50 s. It repeats every second, so it must clear its
  own next repeat and must not become punishing on the fifth hearing.
- **Character**: A coo or distressed chirp from inside the shell. The
  same recording has to carry two emotional valences depending on context
  — anxiety for a held egg about to fly off, anticipation for a basketed
  egg about to hatch into your flock. A neutral "the egg is waking up"
  texture works for both.
- **This is the only alarm in the game.** It has to be unmistakable, and
  once was not: it was a single sine at 659.25 Hz, which is the exact pitch
  and near enough the length of `scan-start` — the blip you fire yourself
  several times a minute. An alarm that sounds like the commonest
  acknowledgement in the game is an alarm you stop hearing.
- **So the placeholder is TWO tones, falling, both off the scale**
  (Eb5 → Bb4). Off-key because it's then the only thing in the world that
  is. Falling because it reports something slipping away rather than asking
  for input — the same shape used everywhere else. Two events because that
  reads as urgency in a way no single tone does, which is why smoke alarms
  chirp rather than hold a note.
- **If you record this one, keep the shape.** Two events, falling, and not
  in key. A single pretty tone will be correct, pleasant, and ignored. A
  recorded sample plays once and whole — the engine will not fire a second
  tone over your take.
- **Files** (2):
  - `egg-warning-1.wav`
  - `egg-warning-2.wav`

### `bird-ambient` — 3 variants
- **Trigger**: Each wandering bird fires this on its own schedule, every
  15–40 seconds, independent of its bird-call timing. Two streams overlap
  unpredictably so the soundscape doesn't fall into a rhythm.
- **Spatial**: yes, at the bird's current position.
- **Duration**: 0.15–0.40 s.
- **Character**: Wing-flap, soft hop, brief rustle. *Not* a call — the
  bird is just moving around. Record 3 variants for organic variety.
- **Not a puff.** Same rule as `wild-bird-flyoff`, and it matters more here
  because this fires far more often: one schedule per bird, so a big flock
  is several a second. The built-in one is a single low-passed wingbeat
  (1100 Hz), 0.16 s. No treble hiss. However many birds are due at once,
  only one rustle plays per 0.7 s, from the nearest — see `eggpark/tally.py`.
- **Files** (3):
  - `bird-ambient-1.wav`
  - `bird-ambient-2.wav`
  - `bird-ambient-3.wav`

### `ambience` — 1 file (loops)
- **Trigger**: Plays continuously from boot, looped forever. Stops/starts
  when the Ambience toggle is flipped. Volume is dialed down to 10% by
  default since it sits under everything.
- **Spatial**: no.
- **Duration**: any length, but **the loop point matters** — make sure
  the start and end of the file blend cleanly (record long enough to
  avoid an obvious cycle, or fade-in/out to silence and let it cycle on
  silence). 30–120 seconds is a sweet spot.
- **Character**: Quiet outdoor bed. Distant air, faint wind, very soft
  rustling. *Not* music. *Not* foreground. The point is to give the
  silence a texture so an empty soundscape doesn't feel digital. If you
  can hear it clearly while standing still doing nothing, it's too loud.
- **Files** (1, or more if you want variants):
  - `ambience.wav`
  - `ambience-1.wav` (optional extra variant)
  - `ambience-2.wav` (optional extra variant)
  - …add more `ambience-N.wav` as you like. The engine picks one at boot.

### `scan-start` — 1 variant
- **Trigger**: Fires the instant Space is pressed, before the proximity
  ping sweep starts. Marks the moment the player triggered the action.
- **Spatial**: no.
- **Duration**: 0.15–0.30 s.
- **Character**: A quick sweep upward, a "scanning" cue. Not the same
  voice as the egg/basket pings — those are the *result*; this is the
  *initiation*. A swooshy or chime-rising-edge shape.
- **Files** (1):
  - `scan-start.wav`

### `fumble` — 1 variant
- **Trigger**: A non-pickup "you tried, no" cue. Fires on F-with-no-basket,
  F-with-empty-hands, and Space-with-nothing-in-range. Distinct from
  `refuse` (which is specifically for over-carry-cap pickup attempts).
- **Spatial**: no.
- **Duration**: 0.15–0.30 s.
- **Character**: A small dry tick, an empty thunk, a quiet "nothing here."
  Should communicate "your input did nothing" without sounding scolding.
- **Pairs with `refuse`** — see that entry. Neither is harsher than the
  other; they differ in weight and pitch. This one is the lower, drier of
  the two.
- **Files** (1):
  - `fumble.wav`

---

## A note on square waves

All three of the game's soft negatives — `refuse`, `fumble`, `basket-full` —
were originally square waves with 5 ms attacks, and all three contradicted
their own entries above.

That combination is not merely harsh, it is **specifically** the synthesis
used by medical and emergency alarms: rich odd harmonics, no attack
transient, low-mid register. It was reported as sounding "for all the world
like an EMS alarm", which is not a coincidence — it's the same recipe.

**Only one sound in this game should ever be built that way, and it isn't
built that way either.** `egg-warning` is the single genuine alarm, and it
deliberately uses a falling triangle pair rather than a square, so it can be
urgent without being clinical.

If you find yourself reaching for a square wave with a fast attack for
anything that isn't an emergency, that's the mistake.

### `boot` — 1 variant
- **Trigger**: Fires once at game start, alongside the "Egg Park ready"
  speech. Settles the player into the soundscape.
- **Spatial**: no.
- **Duration**: 0.8–1.5 s.
- **Character**: A warm bloom. Gentle, welcoming, not heroic. Think
  "lights coming up in a quiet room," not "fanfare."
- **Files** (1):
  - `boot.wav`

### `menu-open` — 1 variant
- **Trigger**: Fires when the settings screen opens (O from gameplay).
- **Spatial**: no.
- **Duration**: 0.15–0.30 s.
- **Character**: A rising tone — conventional "menu opening" shape.
  Light, transparent.
- **Files** (1):
  - `menu-open.wav`

### `menu-close` — 1 variant
- **Trigger**: Fires when the settings screen closes (O or Esc from
  inside settings).
- **Spatial**: no.
- **Duration**: 0.15–0.30 s.
- **Character**: A falling tone — the inverse of `menu-open`. Record
  back-to-back with `menu-open` so they pair tonally.
- **Files** (1):
  - `menu-close.wav`

### `origin` — 2 variants
- **Trigger**: Fires every 8 seconds from world position (0, 0, 0) —
  the player's spawn point. Functions as a navigational beacon; the
  player can always hear which direction "home" is. Distance attenuation
  carries it from much farther than other positional sources (max
  distance 500 m vs 80 m for everything else).
- **Spatial**: yes, at the origin.
- **Duration**: 1.0–2.0 s.
- **Character**: A warm bell or low hum-pulse. Tonally distinct from
  baskets (which sit at A3, D4, G4 in the pentatonic) so the player
  can tell them apart by ear — try E3 (164 Hz), a low gong, or a soft
  drone-pulse. Should feel like a landmark, not a chime; longer tail
  than the basket chimes so it carries across distance.
- **Files** (2):
  - `origin-1.wav`
  - `origin-2.wav`

---

## Suggested recording order (impact-weighted)

Start with the sounds you'll hear hundreds of times per session, then
work outward.

1. **`footstep`** (5 files) — fires more than anything else; you hear it
   every meter you walk. Single biggest perceptual presence in the game.
2. **`egg-call`** (5 files) — the second-constant sound while exploring.
3. **`basket-chime`** (3 files) — third-most-heard.
4. **`ambience`** (1 file) — only one file, and it's the bed under
   everything. Surprisingly load-bearing for atmosphere; missing it
   leaves the silence feeling digital.
5. **`origin`** (2 files) — navigational beacon, fires every 8 seconds.
   Players use it constantly for orientation; needs to be tonally
   distinct from baskets so it's not confusable.
6. **`egg-collect`** (3 files) — fires every successful pickup.
7. **`basket-deposit`** (3 files) — fires every deposit.
8. **`egg-warning`** (2 files) — real gameplay value (held eggs about to
   hatch out of your hand). Quick to record.
9. **`basket-discover`** (1 file) — fires once per basket, but it's *the*
   moment of finding something.
10. **`refuse` + `basket-full` + `fumble`** (3 files) — the three "no"
    cues. Quick to record as a set.
11. **`scan-egg-ping` + `scan-basket-ping` + `scan-start`** (9 files) —
    the signature mechanic. Worth doing once the constants are in.
12. **`bird-call` + `bird-ambient`** (8 files) — hatched birds are a
    later-game state, can wait.
13. **`hatch-in-basket` + `wild-bird-flyoff`** (6 files) — climactic
    moments but rare.
14. **`boot` + `menu-open` + `menu-close`** (3 files) — UI polish.
    Cosmetic; the game is fine without them.

## Grand total

| Category               | Files |
| ---------------------- | ----- |
| egg-call               | 5     |
| basket-chime           | 3     |
| scan-egg-ping          | 5     |
| scan-basket-ping       | 3     |
| scan-guide             | 1     |
| bird-call              | 5     |
| egg-collect            | 3     |
| refuse                 | 1     |
| basket-discover        | 1     |
| basket-deposit         | 3     |
| basket-full            | 1     |
| hatch-in-basket        | 3     |
| egg-laid               | 1     |
| chest-chime            | 1     |
| chest-chime-found      | 1     |
| chest-discover         | 1     |
| scan-chest-ping        | 1     |
| wild-bird-flyoff       | 3     |
| footstep               | 5     |
| egg-warning            | 2     |
| bird-ambient           | 3     |
| ambience               | 1     |
| scan-start             | 1     |
| fumble                 | 1     |
| boot                   | 1     |
| menu-open              | 1     |
| menu-close             | 1     |
| origin                 | 2     |
| **Total**              | **60** |

60 files for a complete sound replacement. Variant counts are
suggestions — record more if you want a bigger pool to draw from, fewer
if you're happy with less variety. The engine doesn't care how many.

## Workflow

1. Record a category (or part of one). Drop the files into
   `public/audio/samples/` using the naming from this doc.
2. In-game, press **R** to reload the sample bank (or restart). The
   loader auto-scans the folder and any matching files override the
   synth placeholders immediately. Missing files keep synth.
3. Walk around and listen. Tune levels via the per-category volume
   sliders in the settings screen (press O).
4. Move to the next category, or record more variants of an existing one.

Each category is independent and the fallback is per-file, so you can
do them in any order and the game keeps working with whatever's still
synth. You can also record a single note or a single variant of a
multi-variant category — only the picks that match a file get
overridden, the rest stay synth.
