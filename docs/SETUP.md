# Setup: a new checkout

These are the first-session steps for someone building CVCOPs, moved here from the README on 10 November 2026.
The public overview is `README.md`. Where things stand is `docs/STATE.md`.

## First session

`uv run python tools/install.py` does steps 3 and 4 for you: it finds `hython`, writes `local.toml` without a
byte-order mark, builds the environment and runs the self-test. It never overwrites an existing `local.toml`.

1. Put this folder in a git repository on a machine with Git Bash and `uv`, and commit it. The lock and the
   unattended launcher read committed files.
2. Pin MotionCOPs, read-only: `git submodule add https://github.com/Boning1011/motion-cops vendor/motion-cops`,
   then `git -C vendor/motion-cops checkout d2a22ad`, and commit. Only the upstream track and
   `evidence/repro_recorder.py` read it. Claude Code prompts on any write to `.gitmodules`, so this step is yours.
3. Copy `local.toml.example` to `local.toml` and point it at `hython`. Save it as UTF-8 without a byte-order
   mark, or `tomllib` refuses it (FACTS K18).
4. `uv sync`, then `uv run python tools/check.py --selftest`.
5. Start Claude Code here and paste the first prompt from `GOALS.md`. After you OK its plan, paste the
   Mission 0 goal line from the same file.

On the owner's workstation, steps 1, 3, 4 and 5 are done (`docs/STATE.md`). Step 2 is open.

## Not in the repository, by design

Each of these is made later, by the step named.

| Not shipped | Made by | When |
| --- | --- | --- |
| `.venv` | `uv sync` | First session |
| `local.toml` | You, from `local.toml.example` | First session |
| `judge.lock` | The owner, with `tools/lock_judge.py` | Mission 0, after the self-test |
| `houdini/test_prefs/` | `check.py --houdini`, on its first run | Mission 0 onward |
| `houdini/otls/` | `houdini/build/build_hdas.py` | Mission 3 |
| `tests/gpu/` | Mission 6 | Mission 6 |
| `upstream-fixes/` | A separate clone of MotionCOPs at `d2a22ad` | The upstream track |
| OpenEvolve 0.4.1 | `uv sync --group evolve`, pinned in `uv.lock` | The evolve lane |

## Install, once the node exists

`uv run python -m cvcops package --write "$HOUDINI_USER_PREF_DIR/packages"` writes one package file. It points
Houdini at this checkout and names the worker's interpreter. Nothing is installed into Houdini's Python.

## Brand files

`docs/media/` holds the logo as outlines, so it needs no font: `logo-light.svg` and `logo-dark.svg` (mark and
name), `logo-mark.svg`, `logo-mark-dark.svg`, `logo-mark-small.svg` (for 32 px and below) and `social-card.png`
(1280 by 640, for the repository's social preview). `explainer-preview.gif` is the silent loop in the README, and
`video-poster.jpg` is a still with a play button. The full video is an asset on the `v0.0.0` pre-release. `docs/media/make_logo.py` regenerates the SVGs; it needs
`fonttools` and the Fraunces, Archivo and JetBrains Mono font files, which are not in the repository.
