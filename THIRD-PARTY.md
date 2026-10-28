# Third-party components

What Egg Park uses, under what terms, and what that means for anyone
redistributing it.

Two of these are redistributed inside this repository: `openal32.dll`,
which the game uses, and Mesa under `tests/mesa/`, which only the tests use.
Everything else is installed separately by `pip` and is listed here for
completeness, not because this repo carries a copy.

---

## Redistributed in this repository

### OpenAL Soft — `openal32.dll`

| | |
| --- | --- |
| **What** | Software implementation of the OpenAL 3D audio API. Provides the HRTF positional audio the whole game is built on. |
| **Version** | The binary reports **1.18.2**. |
| **Licence** | **LGPL v2 or later.** Full text in `LICENSES/LGPL-2.1.txt`. |
| **Upstream** | https://github.com/kcat/openal-soft — see `COPYING` there for the project's own copy. |
| **Modified?** | **No.** Unmodified upstream binary. |

**Why it's committed rather than left to the user:** the game is unplayable
without positional audio, and telling someone to go and source an audio
runtime before they can hear anything is a worse first experience than a
874 KB file in the repo.

**How the LGPL is satisfied here:**

- The library is **dynamically loaded at runtime**, not statically linked.
- The DLL is a **loose, replaceable file** sitting next to `main.py`. Anyone
  can drop in their own build of OpenAL Soft and the game will use it, with
  nothing recompiled — which is the substance of what LGPL §6 asks for.
- The full licence text ships in `LICENSES/LGPL-2.1.txt`.
- The upstream source is linked above.

**If you modify the DLL**, you take on the LGPL's source obligations for
your modified version. Nobody here has modified it.

### HRTF dataset (inside OpenAL Soft)

OpenAL Soft's default HRTF dataset is derived from the **SADIE II
database** and is provided under the **Apache License 2.0** — text in
`LICENSES/Apache-2.0.txt`.

This matters more here than in most projects that bundle OpenAL: HRTF isn't
an optional extra in Egg Park, it's the mechanism the entire game runs on.
Distributing the DLL distributes that dataset with it.

### Mesa — `tests/mesa/opengl32.dll` and `tests/mesa/libgallium_wgl.dll`

| | |
| --- | --- |
| **What** | Software OpenGL (the llvmpipe driver). Lets the tests open the game window on the hidden desktop they run on. |
| **Version** | **26.2.4**, the 64-bit MSVC build from https://github.com/pal1000/mesa-dist-win (`mesa3d-26.2.4-release-msvc.7z`). Only these two files from it. |
| **SHA-256** | `opengl32.dll` 75b295fc80df0eaa8f1264c28663f6932c8b72d36513eb092556608858b7f5e0, `libgallium_wgl.dll` 53e49adf87590d5b0cab8553b1e98084812040cc1fca8c487695b17b7af3702e |
| **Licence** | Mesa's core is **MIT**: text in `LICENSES/MIT-Mesa.txt`, taken from Mesa's own `licenses/MIT`. llvmpipe is built with LLVM linked in, which is **Apache 2.0 with the LLVM exception** (`LICENSES/Apache-2.0.txt`). Individual Mesa source files can carry other permissive licences; the full set is in `licenses/` in the Mesa source. |
| **Upstream** | https://gitlab.freedesktop.org/mesa/mesa |
| **Modified?** | **No.** Unmodified binaries from that release. |

**Why it's committed:** the game tests run on a hidden Windows desktop so
they can't take focus from a screen reader. On the machine this is developed
on, both GPU drivers (Intel and NVIDIA) refuse to make an OpenGL context
current on a desktop that isn't the one being used, and Windows' own software
OpenGL there is version 1.1, too old for pyglet 2. Without this the tests
could not run at all.

**The game never loads it.** `tests/_isolated_desktop.py` loads it by full
path, and only in a test process that has already moved onto the hidden
desktop. Deleting `tests/mesa/` puts the tests back on the GPU driver's
OpenGL.

---

## Installed separately (via pip)

Not redistributed here. Listed so the licence position is complete.

| Package | Version | Licence | Notes |
| --- | --- | --- | --- |
| `pyglet` | 2.1.14 | BSD 3-Clause | Window, input, media, OpenAL binding. |
| `accessible_output2` | 0.17 | **MIT** (© 2019 Christopher Toth) | Screen-reader speech. Its package metadata says `License: UNKNOWN`, which is a packaging gap — the bundled `LICENSE` file and the PyPI classifier both say MIT. |
| `numpy` | 2.1.3 | BSD 3-Clause | Optional. Only imported inside a `try` for one audio helper. |
| `scipy` | 1.17.1 | BSD 3-Clause | Optional, same helper. |

All four are permissive. None imposes conditions on this project's own
licence.

`accessible_output2` in turn ships screen-reader bridge libraries of its
own (NVDA, SAPI, and others), each under their respective terms. Those
arrive through `pip` and are not carried in this repository.

---

## Recorded sounds

Anything under `public/audio/samples/` is original work by this project's
author unless a file says otherwise, and is covered by this repository's
own licence.

**If you add a sample you did not record yourself**, note its source and
terms here before committing it. A sound with no provenance is the hardest
kind of licence problem to unpick later, because nothing about the file
records where it came from.
