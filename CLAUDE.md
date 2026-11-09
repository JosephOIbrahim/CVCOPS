# CVCOPs (working title)

OpenCV perception nodes for Houdini 22 Copernicus, built beside MotionCOPs.
Spec: `docs/BLUEPRINT.md`. Layout and boundaries: `docs/ARCHITECTURE.md`. Verified facts and open probes: `docs/FACTS.md`. Decisions: `docs/decisions/`.
The asset's parameters: `docs/CONTROLS.md`. After v0.1: `docs/OPPORTUNITIES.md` and `docs/ML_AND_AI.md`. The goal line for each session: `GOALS.md`.
State: `docs/STATE.md`. Read it first and update it last.

## Commands
- Rung 1, anywhere: `uv run python tools/check.py`
- Rung 2, workstation with Houdini 22: `uv run python tools/check.py --houdini`. It runs `hython` with an empty preferences folder (`houdini/test_prefs/houdini__HVER__`; SideFX requires `__HVER__`), only this package through `HOUDINI_PACKAGE_DIR`, no `houdini.env` and no `HSITE`.
- Anything in hython, the judge's way: `uv run python probes/hython.py <script> <args>`. Probe helpers: `probes/p1_environment.py`, `probes/p3_transport.py`.
- Rung 3, RTX 4090: `uv run python tools/check.py --gpu`
- Prove the judge before a lock: `uv run python tools/check.py --selftest`. Print it beside its tests: `--list`
- The reference the thresholds come from: `uv run python evidence/thresholds_reference.py`, and with `--faults`
- One test: `uv run pytest tests/unit/test_contract.py -k cache_key -q`
- Worker: `uv run python -m cvcops flow --help`. The manifest agents read: `uv run python -m cvcops capabilities`. The package file: `uv run python -m cvcops package --write <dir>`
- Build assets: `hython houdini/build/build_hdas.py --out houdini/otls`, with `hython` taken from `local.toml`
- Evolve lane: `uv run python evolve/flow_recipe/test_gaming.py`, then `sweep.py`, then `promote.py <program>`. OpenEvolve itself: `uv sync --group evolve`
- Unattended run, started by Joe: `bash tools/unattended.sh M1`
- Locking the judge (`tools/lock_judge.py`) is Joe's alone, run outside Claude. The kit ships the tool; do not rewrite it. A deny rule blocks any command that names `lock_judge`, `git add` included, so Joe commits that file.

## Conventions
- `src/cvcops/` is pure. It never imports `hou`, SYNAPSE, the evidence scripts or the tests; `houdini/` never imports `cv2`. Guard tests check both.
- SYNAPSE depends on this engine, never the reverse (`docs/decisions/0001-synapse-umbrella.md`). The interface is `src/cvcops/capabilities.json` and the receipt schema: every operation declares its effects, writes only inside its output folder and never edits a Houdini scene. When an operation becomes available, flip its status in the manifest.
- Names live only in `[tool.cvcops.names]` in `pyproject.toml` (decision 0002). Read them from there; never hard-code the asset namespace.
- Stored flow is `opencv_px`: x right, y down, analysis-image pixels, forward from A to B. Convert to Houdini units in exactly one node of the asset.
- Backends are explicit: `cpu`, `opencl`, `cuda`. Never substitute one for another. Record what ran in the receipt.
- Write every output to a temp name, then `os.replace`. Write the receipt last. It also records threads, the share of clipped analysis pixels and the grey levels used.
- Thresholds and their tests live in `tests/thresholds/`, each tagged with its mission, and are the spec. The kit ships them, wired from `evidence/thresholds_reference.py`. Each test grades an object with five methods, `flow`, `valid`, `pull`, `write_exr` and `read_exr`; `tests/thresholds/impls.py` builds it from the engine's code (rung 1) or by running `houdini/tests/bake_once.py` in hython (rung 2), whose contract is in that file. Your own tests go in `tests/unit/`, never in `tests/thresholds/`. In Mission 0 you write P4's result into `tests/thresholds/houdini_units.json` and P1's site-packages into `docs/facts/p1_site_packages.json`; both are judge files. Joe locks once `--selftest` passes on the workstation. That lock arms the `ask` rules on `tests/thresholds/`, `tools/check.py` and `docs/contracts/`.
- `check.py` runs the tests of the missions listed in `tests/thresholds/mission.txt`, every mission started so far, skips the rest, and fails if a listed threshold has no test. At the start of each mission Joe adds it, runs `tools/lock_judge.py` and commits both. Before you start a mission, confirm the committed `mission.txt` lists it; if not, write `WAITING:` and stop. Later missions only make locked tests pass.
- `check.py` imports `tools/lock_judge.py` and calls `verify()`: it fails if a judge file or `.claude/settings.json` differs from `judge.lock`, or `judge.lock` differs from its committed version. Do not change one without a line in `docs/STATE.md` and Joe's OK.
- `check.py` exits 1 for a failed check and 3 for a broken environment: no `hython`, no licence, no device, or a timeout. Every check runs under a time limit: 120 s for rung 1, 600 s for one `hython` call. `--hook` runs rung 1, the lock check and the pause line only, and prints the failing rows to stderr; rungs 2 and 3 run only with `--houdini` and `--gpu`.
- Assets are built by script from source. Never hand-edit a `.hda` file. The flow asset's inputs, outputs and parameters come from `houdini/build/controls.json` and nowhere else; `tests/unit/test_controls.py` holds it to the worker's options, the contract and the receipt schema. Build only entries whose status is `v0.1`.
- The scaffold beyond v0.1 is specs, registers and stubs (decision 0003). Do not write the body of a parked stub such as `src/cvcops/ops/temporal.py`, add an operation, or start an ML lane before v0.1 ships and its rows are locked.
- The evolve search edits only the marked block of the program it starts from, `evolve/flow_recipe/swept_program.py`. It never edits the evaluator, fixtures, gaming tests or `promote.py`.

## Gotchas
- `vendor/motion-cops` is a pinned, read-only submodule with no licence upstream. Fixes go to `upstream-fixes/`.
- Never install anything into Houdini's Python; `check.py --houdini` compares its site-packages listing with P1's record. The worker has its own `uv` venv on CPython 3.13, pinned by a committed `uv.lock`, with exactly one OpenCV wheel, `opencv-contrib-python-headless==5.0.0.93`. The OpenCV wheels all provide `cv2` and overwrite each other.
- Never launch the Houdini GUI. Use `hython`. Looks are Joe's gate.
- File COP: Incoming Colorspace Raw, Precision 32-bit (Default follows the COP network's setting), Missing Data on Report Message. The writer is ROP Image. P3 decides the rest by bits.
- Copernicus loads OpenFX plug-ins but not nodes that need other frames. A Python Snippet COP clears its interpreter between cooks unless Maintain State is on.
- List Houdini's Python packages with `importlib.metadata`, never with pip.
- Windows: every command runs in Git Bash. The settings switch the PowerShell tool off so the Bash rules cover every command. `hython` is not on PATH; its path is in the untracked `local.toml`.
- A CUDA build has no DIS. GPU flow means `cv2.cuda_*` classes on `GpuMat`, never `UMat`. Spec: `docs/missions/M6_cuda_build.md`.
- OpenCV 5 wheels have no EXR support. Use the `OpenEXR` package for all EXR I/O.
- `cv2.UMat` falls back to CPU without an error when OpenCL is unavailable. Check `cv2.ocl.useOpenCL()` and record it.
- DIS needs 8-bit single-channel input. Scene-linear frames need a gain and a gamma before they are quantised, or they clip. Keep patch size at or below 16 on OpenCV before 5.1.
- Houdini must load flow at 32-bit float. Half float rounds motions of 512 to 1024 px by up to 0.25 px, and larger ones by more.
- The official wheels have no CUDA modules. The CUDA flow classes raise without a CUDA build; they never fall back.
- If the docs and the running build disagree, the build wins. Write the finding to `docs/FACTS.md`.

## Working agreement
- One mission per session. Plan first, then pause for Joe's OK. `/clear` between missions.
- A `/goal` covers one mission (`GOALS.md`). When you pause with `WAITING:` or `BLOCKED:`, say so plainly in your last message so the goal's check can see it, and stop.
- To pause for Joe, put `WAITING: <what you need>` on the first line of `docs/STATE.md` and stop. Remove it when you resume. The Stop hook lets a turn end only when the checks pass or that first line starts with `WAITING:` or `BLOCKED:`.
- Stuck, a broken environment (exit 3), or a fix that would need a judge change: put `BLOCKED: <reason>` on the first line of `docs/STATE.md` and stop. Do not edit code to get around a broken environment. Only Joe removes `BLOCKED:`. Plain `check.py` fails while either line stands.
- Done means the mission's command exits 0, and the command plus the tail of its output is pasted into `docs/STATE.md`.
- Budget: one session per mission. A second needs a line in `docs/STATE.md` saying why. At a third, stop with `BLOCKED:`, because the plan is wrong.
- No parallel agents. One read-only reviewer pass per mission is allowed: compare the diff against the mission in `docs/BLUEPRINT.md`, report correctness gaps, skip style.
- Model tiers: Heavy = the default model at high effort. Light = sonnet at medium effort. To swap, edit this line and set `CVCOPS_LIGHT_MODEL`.
- A new dependency, a new node, or anything outside the current mission: stop and ask.
- Unattended runs (M1 and M2 only) start from `tools/unattended.sh`, which refuses unless the committed `mission.txt` lists the mission and the judge matches its lock: print mode, 60 turns, a worktree branch, nobody to approve a prompt. The launcher lists any judge file the run touched, and such a branch is not merged. Never `bypassPermissions`, and never `WAITING:` there.
- Evolve runs are background commands outside a Claude session, with a total cap written in `docs/STATE.md` first. A later session reads the trace and runs `promote.py`.
- Upstream fixes live in `upstream-fixes/`, a separate clone of MotionCOPs at `d2a22ad`. Never in `vendor/`.
