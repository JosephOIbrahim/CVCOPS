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

## Where everything lives

| Path | What it is | Written by | Locked |
| --- | --- | --- | --- |
| `src/cvcops/contract.py` | Flow contract v1 as code: conventions, checks, the cache key | The kit | No; a change is a contract change |
| `src/cvcops/ops/` | `estimate_flow` and `validity` | Mission 1 | No |
| `src/cvcops/io_exr.py`, `receipt.py`, `cli.py` | EXR in and out, receipts, `flow` and `verify` | Mission 2; the kit wrote `capabilities` and `package` | No |
| `src/cvcops/capabilities.json` | The manifest agents register tools from | The kit; missions flip `planned` to `available` | No, but its schema is |
| `docs/contracts/` | The manifest and receipt schemas, an example receipt, the map onto SYNAPSE's observation | The kit | Yes |
| `houdini/` | The asset's builder, its Python, `tests/bake_once.py` | Mission 3 | No |
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

## Houdini without your setup

Every `hython` the judge or a probe starts gets an empty preferences folder (`HOUDINI_USER_PREF_DIR` pointed at
`houdini/test_prefs/houdini__HVER__`, which SideFX requires to contain `__HVER__`), only this package (through
`HOUDINI_PACKAGE_DIR`), no `houdini.env`, and no `HSITE`. Your own packages, shelf tools and SYNAPSE stay out of
the tests. Probe P1 confirms that `hython` still finds its licence this way (FACTS A12).
