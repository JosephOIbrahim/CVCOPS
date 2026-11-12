# Evidence scripts

These produced the numbers in `docs/FACTS.md`. They ran in a 2-thread Linux sandbox on 2026-11-08 and 2026-11-09.
Re-run them on the workstation in Mission 0 and record the results next to the sandbox numbers.

| Script | What it shows | Needs |
|---|---|---|
| `probe_cv.py` | OpenCV build flags: OpenCL, OpenEXR, CUDA stubs, API names | the worker's wheel, `opencv-contrib-python-headless==5.0.0.93` |
| `probe_dis.py` | DIS on known shifts: sign convention, accuracy, determinism, silent CPU fallback of `cv2.UMat`, timings | same |
| `probe_exr.py` | Bit-exact float32 EXR round trip and its cost | `OpenEXR`, `numpy` |
| `repro_recorder.py <path to mc_texture_to_volume_cpu.py>` | Two upstream recorder defects, reproduced without Houdini | `numpy` |
| `hda_extract.py <file.hda> <out dir>` | Read-only unpacker for Houdini asset files; used to read upstream kernels | standard library |
| `thresholds_reference.py` | Every row of the blueprint's threshold table on pinned fixtures, with PASS or FAIL, through the five-method seam the threshold tests use; `METRICS` holds one function per row, and `tests/thresholds/` calls the same ones. `--faults` plants nine faults that must each fail. `--seeds N` repeats the metrics on fresh draws. A row that cannot run fails | `opencv`, `numpy`, `OpenEXR` |
| `opportunities_reference.py` | Three uses after v0.1, on synthetic fixtures through the same seam: the temporal check ranks two planted frames first, a mark is carried along the flow, and seeds are kept where motion exceeds a threshold. Demonstrations, not locked thresholds (decision 0003) | `opencv`, `numpy` |
| `controls_dryrun.py` | Houdini builds every v0.1 control in `houdini/build/controls.json` on a throwaway node and reads it back. Run it through `probes/hython.py` | `hython` |
| `measure_validity.py` | What the validity flag catches by occlusion width, and what each tolerance costs | `opencv`, `numpy` |
| `measure_encoding.py` | What quantising scene-linear frames to 8 bits costs, with and without gain and gamma | same |
| `measure_threads.py` | Identical bytes across thread counts; the rounding a half-float layer would add to flow | same |
| `measure_scale.py` | Speed against error for analysis scales 1.0, 0.5 and 0.25 on the same frames | same |
| `hook_line_cases.sh` | The Stop hook line from `.claude/settings.json` against pass, fail, crash, missing tool, the two pause lines, subdirectories and a worktree | `bash` |
| `lock_judge_cases.py` | `tools/lock_judge.py` in a scratch repository: when the check must fail and when it may pass | `git` |
| `judge_lifecycle_cases.sh` | `tools/check.py` through a mission's life in a scratch repository: the lock, starting a mission, a throwaway M1, a loosened threshold, a cheat, a pause line, a broken environment, and rung 2 with a stand-in `hython` and asset | `bash`, `git`, the worker's packages |
| `unattended_cases.sh` | `tools/unattended.sh` with a stand-in for the CLI: it refuses a mission other than M1 or M2, one missing from the committed `mission.txt`, and a judge that differs from its lock; a run that touches a judge file is reported | `bash`, `git` |
| `release_numbers.py` | The release's numbers table: the rung-1 rows through the reference, the rung-2 rows from the last values run, the bake receipt's medians and the quarter ratio, and the owner's plate as numbers only. Writes nothing, imports no hou | `opencv`, `numpy`, `OpenEXR`; the results file from the values run |
| `package_install_check.py` | The shipped package file alone loads the asset: it writes the package into an empty folder, starts hython with an isolated environment and `HOUDINI_PACKAGE_DIR` at that folder, and reports whether the type resolves, whether the worker variable matches, and whether `cv2` leaked | `hython` |
| `bake_receipt.py` | The five timed bakes of the example and their receipt, `docs/facts/m3_bake_receipt.json` (`cvcops.bake.v1`): `runs` starts each bake as its own `probes/hython.py houdini/tests/bake_timing.py` call with a process snapshot before and after, `aggregate` writes the medians and the quarter ratio, `--check` re-derives them. It refuses fewer than five runs, a disagreeing workload, a negative or overlong phase, a skipped pair, a run that overlapped a hython or Houdini process (python processes are only counted) and an absolute path | standard library; `hython` for `runs` |
| `measure.py`, `measure_m3_m4.py` | Earlier reference numbers, kept for the history in FACTS M8 to M11 and E9 | `opencv`, `numpy` |
| `refinement/` | The gates, rubric and baseline used to refine the blueprint; `test_gates.py` proves the gates catch cheats. `gates.py` also ties the threshold table to `thresholds_reference.py` and checks `.claude/settings.json` | standard library |

Run each with the worker environment, for example: `uv run python evidence/probe_dis.py`.
`repro_recorder.py` executes four small functions extracted from the upstream script. They were read by hand first.
