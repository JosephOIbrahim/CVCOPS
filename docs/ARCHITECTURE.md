# Architecture

As of 2026-11-09. `docs/BLUEPRINT.md` says what to build and why; this says where each part lives and what may
talk to what.

## One engine, three ways in

**Every arrow points toward the engine, and a layer knows only the layers below it.**

```text
  artists                        pipelines                       agents
  Houdini asset, Bake button     python -m cvcops flow ...       SYNAPSE's adapter (in SYNAPSE's repo)
          |                              |                               |
          | a subprocess, files          |                               | capabilities, verify, flow
          +------------------------------+-------------------------------+
                                         |
              worker CLI                 src/cvcops/cli.py
                                         |
              operations                 src/cvcops/ops/          pure functions of arrays
                                         |
              contract                   src/cvcops/contract.py and docs/contracts/
                                         |
              runtime                    one OpenCV wheel, NumPy, OpenEXR, in the worker's own uv venv
```

The asset reaches the worker the same way SYNAPSE does: it starts a process with files in and files out. So the
artist's path and the agent's path test each other. Decision 0001 records why SYNAPSE sits above the engine
rather than around it.

## Three processes, and what each may load

| Process | Runs | Loads | Never loads |
| --- | --- | --- | --- |
| Houdini, or `hython` | The asset: prep, ROP Image, File COP, the conversion node, Distort | `hou`, Houdini's own NumPy | OpenCV (a guard test scans `houdini/`) |
| The worker, one per bake | `python -m cvcops flow` | OpenCV, NumPy, OpenEXR | `hou`, SYNAPSE, the evidence scripts, the tests (a guard test scans `src/`) |
| SYNAPSE | Its own agent, and an adapter that calls the worker | Whatever SYNAPSE loads | The engine's Python, in Houdini's process |

## The worker's promises (Mission 2, decision 0004)

| What | Promise |
| --- | --- |
| Call | `python -m cvcops flow --in <cache>/analysis.####.exr --out <cache> --frames f1-f2 --recipe R --backend B --tolerance T`. The `#` run is zero-padded; pair `a` writes `flow.<a>.exr` (R = u, G = v in `opencv_px`, B = valid; float32, ZIP, at analysis size, never resized), then `flow.<a>.json` last. |
| Writes | Only inside `--out`, each file through a temporary name starting with a dot, then `os.replace` (retried about a second on Windows). A fresh pair is skipped; there is no force flag, so a recompute means a fresh folder. |
| Exit codes | 0 every pair written or fresh. 1 a pair failed, or the request was refused before anything was written (missing frames, a bad pattern or range, a bad sidecar, `--backend opencl` or `cuda` with a device present). 3 no OpenCV or OpenEXR, or no device for the requested backend; the cpu backend is never substituted. A bad argument is 1, not argparse's 2. An interrupt (Ctrl-C, a cancelled bake) ends the process with the platform's interrupt status; the atomic writes leave no half-written file, and the interrupted pair reads as missing. |
| Error receipts | A failure before both frames are hashed and read writes nothing for that pair. A later one removes the pair's old flow file and writes `status: error` with the reason; the run goes on. |
| Progress | One line per pair on stdout, flushed at once: `flow <a>-<b> ok <seconds>s`, `skip fresh` or `error`. Reasons go to stderr. |
| Timings | `timings_s`: `read`, `hash`, `flow` (forward DIS), `validity` (backward DIS plus the check), `write` (flow file and its hash), `total`. Flow compute = flow + validity; worker I/O = read + hash + write. |
| Cache key | `contract.cache_key` over the two frame digests, `params.digest` (tolerance, mask, and the line-ending-normalised source hashes of the reader, `estimate_flow` and the validity code), the recipe's source hash, the backend, `cv2.__version__` and the SHA-256 of `cv2.getBuildInformation()`. Not threads, not the engine version, not the folder. |
| `verify` | Same `--in`, `--out`, `--frames`; optional `--recipe`, `--backend`, `--tolerance` (unset: as each receipt recorded). Writes nothing. Exit 0 all fresh, 1 otherwise, 3 broken environment. `--json` prints `{"frames": {"first", "last"}, "counts": {"fresh", "stale", "missing"}, "pairs": [{"a", "b", "state", "reason"}]}`. Missing: no receipt or no flow file. Stale: an unreadable or failed receipt, an input gone, another cache key, or a flow file that differs from its receipt. |
| Sidecar | `<prefix>.json` beside the frames (`analysis.json` for `analysis.####.exr`), schema `cvcops.analysis_sidecar.v1`: `{"schema", "analysis": {"luminance_weights", "gain", "gamma", "scale", "color_space"}, "frame": {"fps"}}`, every key optional. No file means scale 1.0, the source as given, the rest null. Anything else is refused. |
| Analysis frames | One channel of any name, or R = G = B (bare or under one layer prefix); alpha ignored; FLOAT or HALF; a data window wider than the display window is cropped. Read as `rint(x * 255)` clipped to 0-255. |

## Where everything lives

| Path | What it is | Written by | Locked |
| --- | --- | --- | --- |
| `src/cvcops/contract.py` | Flow contract v1 as code: conventions, checks, the cache key | The kit | No; a change is a contract change |
| `src/cvcops/ops/` | `estimate_flow` and `validity` | Mission 1 | No |
| `src/cvcops/io_exr.py`, `receipt.py`, `cli.py` | EXR in and out, receipts, `flow` and `verify` | Mission 2; the kit wrote `capabilities` and `package` | No |
| `src/cvcops/capabilities.json` | The manifest agents register tools from | The kit; missions flip `planned` to `available` | No, but its schema is |
| `docs/contracts/` | The manifest and receipt schemas, an example receipt, the map onto SYNAPSE's observation | The kit | Yes |
| `houdini/` | The asset's builder, its Python, `tests/bake_once.py` | Mission 3 | No |
| `houdini/build/stamp.py`, `houdini/otls/` | The build stamp every install compares against; the per-user build, untracked, with its `.stamp.json` beside it | Mission 3, extended by the release | No |
| `tools/install.py`, `tests/unit/test_install.py` | One-command install: the worker environment, `local.toml`, the self-test, the asset under your licence, one package file | The release | No |
| `houdini/build/controls.json` | The asset's inputs, outputs and parameters; the builder's only source (`docs/CONTROLS.md`) | The kit; Mission 3 confirms it with Joe | No; `tests/unit/test_controls.py` guards it |
| `docs/opportunities.json`, `src/cvcops/ops/temporal.py` | The register of uses after v0.1, and the stub for the first one (`docs/OPPORTUNITIES.md`, decision 0003) | The kit | No |
| `GOALS.md` | One `/goal` line per Claude Code session | The kit | No |
| `probes/` | P1 and P3 helpers, and `hython.py`, which runs anything in hython the judge's way | The kit; Mission 0 adds the rest | No |
| `tests/thresholds/` | One test per threshold row, the guards, and the adapters that build what is graded | The kit | Yes |
| `tests/unit/` | Each mission's own tests | Every mission | No |
| `tools/check.py` | The judge's front door: rungs, exit codes, the self-test | The kit | Yes |
| `tools/lock_judge.py`, `tools/unattended.sh` | The lock, and the unattended launcher | The kit | The lock tool is |
| `evidence/` | The scripts behind every number in FACTS, the reference the tests call, and the case files that test the kit's own tools | The kit | `thresholds_reference.py` is |
| `local.toml` | Machine paths: `hython`, `opencv_prep`, `cuda_python` | You, from `local.toml.example` | Untracked |

## The judge

**A mission is done when its command exits 0, and nothing the mission writes can change what that command
measures.**

| Rung | Command | What it runs | Where |
| --- | --- | --- | --- |
| 1 | `uv run python tools/check.py` | Guards, `tests/unit/`, the M1 and M2 rows of the missions listed in `tests/thresholds/mission.txt`, the lock, the pause line | Anywhere |
| 2 | `check.py --houdini` | The M3 and M4 rows through `hython`, and Houdini's site-packages against probe P1's record | The workstation |
| 3 | `check.py --gpu` | `tests/gpu/`, with the CUDA interpreter | The 4090 |
| none | `check.py --selftest` | Every row against the reference, which must pass, and against nine planted faults, which must each fail one | Anywhere, before the lock |

Each row grades an object with five methods: `flow`, `valid`, `pull`, `write_exr` and `read_exr`.
`tests/thresholds/impls.py` builds three kinds: one from the engine's code, one that drives the asset through
`hython`, and the reference with its faults. The adapters sit in the locked folder so a mission cannot hand the
tests the reference instead of its own code. `evidence/judge_lifecycle_cases.sh` walks the judge through a
mission's life, including a stand-in asset at rung 2.

Exit codes are the same everywhere: 0 pass, 1 a check failed, 3 a broken environment. On 3, the agent writes
`BLOCKED:` and edits no code.

## Versions and promises

| Promise | Where | When it changes |
| --- | --- | --- |
| Engine version | `pyproject.toml`, and the manifest's `engine.version` (a guard keeps them equal) | Every release |
| `flow-contract-v1` | `src/cvcops/contract.py`, `docs/BLUEPRINT.md` section 6 | Only with a line in `docs/STATE.md`; every cache key changes with it |
| `cvcops.receipt.v1` | `docs/contracts/receipt.schema.json` | A new field that may be null is compatible; anything else is v2 |
| `cvcops.capabilities.v1` | `docs/contracts/capabilities.schema.json` | The same rule; SYNAPSE's adapter pins the version it reads |
| Asset name | `[tool.cvcops.names]` in `pyproject.toml` | Never, once scenes use it (decision 0002) |
| `cvcops.analysis_sidecar.v1` | `src/cvcops/io_exr.py`'s reader and `cvcops_houdini/sidecar.py`'s writer, shape in decision 0004 | Its allowed keys only grow: weights, gain, gamma, scale, colour space, fps |
| `verify`'s JSON | `src/cvcops/cli.py` (`--json`), shape in decision 0004(g) | `frames`, `counts` and `pairs` keep their names |
| `cvcops.bake.v1` | `docs/facts/m3_bake_receipt.json`; the per-bake record at `$cache/bake.json` keeps its own shape | A new phase key is compatible; `quarter` keeps its formula |
| Distribution | Decision 0005: the builder and `tools/install.py`, no built `.hda`, the pre-release carries `install.py` pinned to the tag | Every release |

## Houdini without your setup

Every `hython` the judge or a probe starts gets an empty preferences folder (`HOUDINI_USER_PREF_DIR` pointed at
`houdini/test_prefs/houdini__HVER__`, which SideFX requires to contain `__HVER__`), only this package (through
`HOUDINI_PACKAGE_DIR`), no `houdini.env`, and no `HSITE`. Your own packages, shelf tools and SYNAPSE stay out of
the tests. Probe P1 confirms that `hython` still finds its licence this way (FACTS A12).
