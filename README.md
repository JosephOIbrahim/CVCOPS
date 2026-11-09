# CVCOPs (working title)

OpenCV perception for Houdini 22 Copernicus: one optical-flow node that bakes to disk on a stock OpenCV wheel,
built by Claude Code one mission at a time against a judge it cannot loosen. It is planned to become SYNAPSE's
perception engine, with SYNAPSE calling it and never the other way round (`docs/decisions/0001-synapse-umbrella.md`).

**Status, 9 November 2026: nothing of the node is built. The judge is built and proven.** The contract, the
schemas, the capability manifest, the threshold tests and `tools/check.py` are in place. The self-test passes the
reference on every row and catches all nine planted faults, and a scratch walk through a mission's life passes
18 cases. Mission 0 is next, at the workstation.

## Start here

| Read | For |
| --- | --- |
| `docs/STATE.md` | Where things stand and the next action |
| `docs/BLUEPRINT.md` | What gets built, in which missions, against which thresholds |
| `docs/ARCHITECTURE.md` | Where each part lives and what may talk to what |
| `docs/FACTS.md` | Every verified fact, measurement and open assumption, with its source |
| `docs/decisions/` | The SYNAPSE umbrella (0001), the names, with the asset namespace `cvcops::` (0002), and the scaffold beyond v0.1 (0003) |
| `CLAUDE.md` | The rules Claude Code works under in this repo |
| `GOALS.md` | The first prompt, and one `/goal` line per Claude Code session |
| `docs/CONTROLS.md` | The asset's inputs, outputs and parameters, from `houdini/build/controls.json` |
| `docs/OPPORTUNITIES.md` | Seventeen uses of the two layers, and which comes first after v0.1 |
| `docs/ML_AND_AI.md` | Where ML and AI come in, each lane behind a gate and a probe |

## First session

1. Put this folder in a fresh git repository on the workstation, which needs Git Bash and `uv`, and commit it.
   The lock and the unattended launcher read committed files.
2. Pin MotionCOPs, read-only: `git submodule add https://github.com/Boning1011/motion-cops vendor/motion-cops`,
   then `git -C vendor/motion-cops checkout d2a22ad`, and commit. Only the upstream track and
   `evidence/repro_recorder.py` read it. Claude Code prompts on any write to `.gitmodules`, so this step is yours.
3. Copy `local.toml.example` to `local.toml` and point it at `hython`.
4. `uv sync`, then `uv run python tools/check.py --selftest`.
5. Start Claude Code here and paste the first prompt from `GOALS.md`. After you OK its plan, paste the
   Mission 0 goal line from the same file.

On the workstation this kit is unpacked at `E:\Myth_and_Logic\Software\CVCOPS`, with `local.toml` written and
steps 3 and 4 done (`docs/STATE.md`). Steps 1 and 2 remain: the first prompt asks the session to run `git init`
and make the first commit once you OK the plan, and the submodule is yours.

## Not in the kit, by design

Each of these is made later, by the step named.

| Not shipped | Made by | When |
| --- | --- | --- |
| `.venv` | `uv sync` | First session |
| `local.toml` | You, from `local.toml.example` | First session |
| `docs/facts/p1_site_packages.json`, and the values in `tests/thresholds/houdini_units.json` | Probes P1 and P4 | Mission 0 |
| `judge.lock` | You, with `tools/lock_judge.py` | Mission 0, after the self-test |
| `houdini/test_prefs/` | `check.py --houdini`, on its first run | Mission 0 onward |
| `houdini/otls/` | `houdini/build/build_hdas.py` | Mission 3 |
| `tests/gpu/` | Mission 6 | Mission 6 |
| `upstream-fixes/` | A separate clone of MotionCOPs at `d2a22ad` | The upstream track |
| OpenEvolve 0.4.1 | `uv sync --group evolve`, pinned in `uv.lock` | The evolve lane |

## Install, once the node exists

`uv run python -m cvcops package --write "$HOUDINI_USER_PREF_DIR/packages"` writes one package file. It points
Houdini at this checkout and names the worker's interpreter. Nothing is installed into Houdini's Python.
