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
| `measure_validity.py` | What the validity flag catches by occlusion width, and what each tolerance costs | `opencv`, `numpy` |
| `measure_encoding.py` | What quantising scene-linear frames to 8 bits costs, with and without gain and gamma | same |
| `measure_threads.py` | Identical bytes across thread counts; the rounding a half-float layer would add to flow | same |
| `measure_scale.py` | Speed against error for analysis scales 1.0, 0.5 and 0.25 on the same frames | same |
| `hook_line_cases.sh` | The Stop hook line from `.claude/settings.json` against pass, fail, crash, missing tool, the two pause lines, subdirectories and a worktree | `bash` |
| `lock_judge_cases.py` | `tools/lock_judge.py` in a scratch repository: when the check must fail and when it may pass | `git` |
| `judge_lifecycle_cases.sh` | `tools/check.py` through a mission's life in a scratch repository: the lock, starting a mission, a throwaway M1, a loosened threshold, a cheat, a pause line, a broken environment, and rung 2 with a stand-in `hython` and asset | `bash`, `git`, the worker's packages |
| `unattended_cases.sh` | `tools/unattended.sh` with a stand-in for the CLI: it refuses a mission other than M1 or M2, one missing from the committed `mission.txt`, and a judge that differs from its lock; a run that touches a judge file is reported | `bash`, `git` |
| `measure.py`, `measure_m3_m4.py` | Earlier reference numbers, kept for the history in FACTS M8 to M11 and E9 | `opencv`, `numpy` |
| `refinement/` | The gates, rubric and baseline used to refine the blueprint; `test_gates.py` proves the gates catch cheats. `gates.py` also ties the threshold table to `thresholds_reference.py` and checks `.claude/settings.json` | standard library |

Run each with the worker environment, for example: `uv run python evidence/probe_dis.py`.
`repro_recorder.py` executes four small functions extracted from the upstream script. They were read by hand first.
