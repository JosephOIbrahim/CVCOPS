# Mission M6b: OpenCV 5.1 with CUDA, built from source

This is the second half of M6. The first half scores DIS on OpenCL (blueprint, section 8); this half runs only if
that did not reach adopt and Joe says yes to a CUDA build.

**Goal.** Get one OpenCV 5.1.0 build with CUDA for the RTX 4090 into its own environment, and find out whether any
CUDA flow recipe passes the accuracy gate and makes a bake at least 20% faster end to end.

**Entry.** The M3 bake receipt shows the flow-compute median is at least a quarter of its median total. Or Joe chose
"GPU first" in section 3 of the blueprint; then this mission runs right after M2 and its verdict is provisional,
measured on the worker alone (analysis EXR in, flow EXR out), until M3 re-checks it on the bake.

**Done when.** `uv run python tools/check.py --gpu` passes, and `docs/STATE.md` holds a verdict: adopt one named
CUDA recipe that passes the holdout gate and cuts the M3 bake receipt's median time by 20%, or keep CPU. Both
verdicts count as done.

**Tier.** Heavy. Not unattended: a build failure needs a person.

## Start from the prep project, not from zero

Joe's OpenCV 5.1 prep project on the workstation (its folder goes in `local.toml` as `opencv_prep`) has already
checked a toolchain and pinned the same sources this mission needs (FACTS X5). One CUDA build serves both projects;
a second would double the cost and drift.

- Read its status page and decision log first. Use the toolchain it has frozen. If it has frozen none, ask Joe to
  settle that there (its decisions D04 and D05), not here.
- If its build exists and has passed its own GPU gate, skip to step 6.
- Do not install another CUDA toolkit or compiler, and do not change the driver. That project keeps driver 621.14.

## What a CUDA build does and does not buy

Read this before building. It decides what the mission can win.

| Fact | Consequence | Ledger |
| --- | --- | --- |
| The official wheels list every `cuda*` module as unavailable. | CUDA means compiling from source. | C10 |
| `cudaoptflow` has Farneback, TV-L1, Brox, pyramidal LK and NVIDIA hardware flow (`NvidiaOpticalFlow_2_0`). It has no DIS. | A CUDA build does not speed up the recipe the CPU path uses. Every CUDA option is a different algorithm and must pass the same gate on its own. | C6 |
| In 5.1, `cv2.UMat` can sit on CUDA memory, but no `cv2` function dispatches to CUDA for UMat input. | GPU work goes through explicit `cv2.cuda_GpuMat` and `cv2.cuda_*` classes, never through UMat. | C12 |
| Without CUDA, the CUDA flow constructors raise. | No silent fallback: a failed import or call is a loud error. | C11 |
| The NVIDIA flow headers download from GitHub at configure time, and the prep project blocks configure-time downloads on purpose. | `NvidiaOpticalFlow_2_0` needs those headers fetched by hand, with their hash recorded, or it is left out. Ask Joe which. | C6, X5 |
| OpenCV 5.1's CMake knows the Lovelace generation as architecture 8.9. | Build for 8.9 only. One architecture keeps the build smaller and faster. | C13 |
| NVIDIA's CCCL in CUDA 13 needs `/Zc:preprocessor` with MSVC; OpenCV's build adds it for CUDA after 12.0. | Do not add the flag by hand; check the generated command has it. | X5 |
| Windows 11 26H2 is newer than the last release NVIDIA's CUDA 13.3 support matrix lists. | A compile that passes is evidence, not support. Record the OS build next to every result. | X5 |
| Another job used 6,795 MiB of the 4090's memory during the prep inspection. | Time only when the GPU is idle, or record what else held it. | X5 |

## Steps

Record every version you see in `docs/STATE.md` as you go.

1. **Check the toolchain against the prep project's record.** Record `nvidia-smi`, `nvcc --version`,
   `cmake --version` and the MSVC version, and compare them with its frozen tuple. A mismatch is a broken
   environment: write `BLOCKED:` and the difference. cuDNN, TensorRT and the Video Codec SDK are not needed.
2. **Use its sources.** OpenCV tag `5.1.0` at commit `e4f78fb` and opencv_contrib tag `5.1.0` at commit `b67a855`,
   as the prep project pinned and hashed them. Do not download them again.
3. **Configure with CUDA for 8.9 only**, in the prep project's build tree, from its staged configure arguments.
   The switches this mission needs, as CMake arguments:
   ```bash
   -DWITH_CUDA=ON -DCUDA_ARCH_BIN=8.9 -DWITH_CUDNN=OFF -DWITH_NVCUVID=OFF -DWITH_NVCUVENC=OFF \
   -DBUILD_TESTS=OFF -DBUILD_PERF_TESTS=OFF -DBUILD_EXAMPLES=OFF -DBUILD_opencv_cudaoptflow=ON
   ```
   Its first scope leaves out EXR; the worker reads and writes EXR with the `OpenEXR` package, so that costs
   nothing here.
4. **Build and install only into that project's tree**, with its isolated Python. Keep the full log.
5. **Point the worker at it.** Its Python is CPython 3.12, the worker's CPU path uses 3.13, and the CUDA path
   needs its own interpreter anyway. Put that interpreter's path in `local.toml` as `cuda_python`; `check.py --gpu`
   runs the GPU tests with it. Never install the build next to the CPU wheel: all OpenCV builds provide `cv2` and
   overwrite each other.
6. **Qualify the build.** With `cuda_python`:
   - `cv2.__version__` is `5.1.0`.
   - `cv2.getBuildInformation()` shows CUDA enabled with architecture 8.9. Save the whole text to `docs/facts/`.
   - A real CUDA round trip: upload a fixture to `cv2.cuda_GpuMat`, run one CUDA flow call, synchronise, download,
     and compare with the same algorithm's CPU result; record the largest difference. A device count or `WITH_CUDA=ON` alone does not
     qualify the build.
   - If `import cv2` fails with a DLL error on Windows, add the CUDA `bin` directory with `os.add_dll_directory`
     before the import, and record that this was needed.
7. **Score the CUDA recipes through the existing gate.** Write each as `estimate_flow(a, b)` that uploads to
   `cv2.cuda_GpuMat`, runs, and downloads float32 (H, W, 2) flow, so transfers count in the timing:
   CUDA Farneback, CUDA TV-L1, CUDA Brox, and `NvidiaOpticalFlow_2_0` at output grid size 1 if its headers were
   supplied, converted to float. Run each through `evolve/flow_recipe/promote.py` for its holdout gate only: its
   15% margin belongs to the evolve lane, and adoption here follows the 20% bake rule. A recipe that fails the
   gate is out, however fast it is.
8. **Measure the job, not the operation.** For any recipe that passes the gate, bake the M3 example with it and
   with the CPU recipe, and compare the two bake receipts: the median total, with the medians for export, flow
   compute, worker I/O and load, over five runs. Record free VRAM (`nvidia-smi`) before each run. On the GPU-first
   path there is no bake yet: compare the worker end to end and mark the verdict provisional.
9. **Write the verdict** in `docs/STATE.md`: the recipe, its gate result, both bake timings, and adopt or keep CPU.

## Rules

- Adopt only a recipe that passes the holdout gate and cuts end-to-end bake time by 20% (principle 9).
- The CUDA backend is chosen explicitly by name. If CUDA is requested and unavailable, the worker errors.
- One session of build errors is the limit. On a second, stop with `BLOCKED:` and the log tail (risk table).
- A build that fails is a broken environment, not a failing test: do not edit product code to cure it.
- Do not touch `.venv` (the CPU worker), and change nothing in the prep project beyond its own build tree.

## What could make this not worth it

The CPU path is the bar, and it is not slow: DIS MEDIUM at 4K took 0.79 s per pair on two sandbox threads, and the
workstation has many more cores. File I/O is in every bake whichever backend runs the flow. If the gate rejects
every CUDA algorithm, or the bake gets less than 20% faster, the verdict is "keep CPU", and that is a result.
