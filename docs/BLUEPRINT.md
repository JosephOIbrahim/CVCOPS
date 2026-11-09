# CVCOPs Blueprint v2: OpenCV perception for Houdini 22 Copernicus

As of 2026-11-09. Working title. Supersedes the MotionCOPs OpenCV 5.1 GPU Engineering Blueprint (v1).

Build one optical-flow node that bakes to disk on a stock OpenCV wheel, with every claim behind a command that passes or fails. GPU work and evolutionary search enter only where a measurement earns them. This is written to be run by Claude Code, one mission per session.

## Capsule

| Item | State |
| --- | --- |
| Where we are | Mile 0 of 5 to v0.1. Premises audited, sessions walked by hand, evidence re-run, the workstation's Houdini reference read. Nothing built. |
| Next action | Mission 0 at the workstation: seven probes, the self-test on Windows, your lock. The judge ships built. |
| Your calls first | A licence, and public or private. The asset namespace is settled: `cvcops::` (`docs/decisions/0002-names-and-namespace.md`). |
| The one judgment call | GPU as the goal, or GPU as the means. See section 3. |
| Blockers | None. |

## 1. Thesis

**Copernicus is the brush and OpenCV is the eye.** SideFX builds Copernicus for GPU acceleration, and Houdini 22's node list has no optical-flow or motion-vector node. OpenCV measures motion well, but Houdini's documented Python route hands it pixels in host memory only.

So OpenCV works at the edge of the graph, on small analysis images, and Copernicus does everything else. The first release is one optical-flow node built that way, plus a warp node only if native Distort cannot do the job.

The long game reverses the roles. OpenCV becomes the test bench, and native OpenCL kernels found by search do the work inside Copernicus. Section 7 shows how to get there without betting on it.

## 2. What v1 assumed, and what the evidence says

Four of v1's premises hold, seven change the plan, and two findings are new. Every verdict except one design call was checked against a source on 8 November 2026, and again on 9 November. Sandbox numbers come from a 2-thread Linux machine, not the workstation.

| v1 premise or new finding | Verdict | Evidence | v2 response |
| --- | --- | --- | --- |
| Baseline is motion-cops `d2a22ad`, 26 Oct 2026 | Holds | It is the current HEAD of [main](https://github.com/Boning1011/motion-cops/tree/d2a22ade06132381a1ce68ddbc9df80782e35a51). | Pin it as a read-only submodule. |
| Three volume-recorder defects | Hold | Read in the [source](https://github.com/Boning1011/motion-cops/blob/d2a22ade06132381a1ce68ddbc9df80782e35a51/scripts/mc_texture_to_volume_cpu.py). Two reproduced: Fixed8 white reads 255.0 in luminance mode, 1.0 in channel mode; schedule (1, 2, 0.3) leaves its last sample unindexed. | Send upstream as test plus patch. |
| Pixel sort is odd-even transposition with a write conflict | Holds | Extracted kernel: an active pixel writes `pos` and `next_pos`; the inactive neighbour also writes `next_pos`. | Send upstream as a gather rewrite. |
| No C++ plug-in route into Copernicus | Half holds | [HDK docs](https://www.sidefx.com/docs/hdk/_h_d_k__op_basics.html): "At present there is no HDK support for Copernicus." But Copernicus loads [OpenFX plug-ins](https://www.sidefx.com/docs/houdini/copernicus/openfx.html), except nodes that need access to time. | Python and files for v0.1. OpenFX is the in-process candidate for the live lane. |
| Optical flow is the right first feature | Holds | Houdini 22's [COP index](https://www.sidefx.com/docs/houdini/nodes/cop/index.html) lists no Optical Flow or Motion Vector node. | Flow is v0.1. |
| Refactor MotionCOPs in place | Fails | The repo tracks no licence file. Its assets are binary `.hdalc`; `git diff` shows only "Binary files differ". | Build beside it. Send fixes upstream. |
| Target OpenCV 5.1 | Half holds | [5.1.0](https://github.com/opencv/opencv/releases/tag/5.1.0) was tagged 5 Nov 2026 in both repos. The newest [PyPI wheel](https://pypi.org/project/opencv-python-headless/) is 5.0.0.93, and the official wheels carry no CUDA modules. | Pin 5.0.0.93 now and re-qualify when the 5.1 wheel ships. Only a CUDA build needs source. |
| CUDA execution is required | Not supported | CPU DIS MEDIUM recovered known shifts to about 0.02 px. Sandbox: a 4K pair took 0.79 s (MEDIUM) or 0.12 s (FAST); a worst-case 4K float EXR write, 1.3 s. | GPU is a gated mission. CUDA has no DIS, so it means another algorithm through the same gate. |
| NVIDIA hardware flow is the preferred backend | Demoted | It is in contrib 5.1.0, behind a custom CUDA build. The [SDK docs](https://docs.nvidia.com/video-technologies/optical-flow-sdk/index.html) were last updated in Feb 2023 and do not cover RTX 50. | Optional backend under the same contract. |
| Polish the native ripple, time and cache tools | Mostly moot | [Houdini 22](https://www.sidefx.com/docs/houdini/news/22/copernicus.html) ships native Time Shift, Time Blend and a Ripple solver. | Leave them. |
| Worker protocol with job ids and stale-completion handling | Design call | One process per bake, files in and files out, covers what v1 needed. | Files are the protocol. Receipts are the state. |
| New: `cv2` cannot handle the EXR files | Changes the worker | OpenCV 5 dropped its bundled OpenEXR. The 5.0 Linux wheel reports `OpenEXR: NO`. | The worker uses the `OpenEXR` package. A 4K float32 round trip was bit-exact. |
| New: `cv2.UMat` does not prove GPU | Changes the receipts | With no OpenCL device, UMat calls ran on CPU, returned identical results and raised nothing. DIS takes its OpenCL path only with a UMat output, patch size 8 and spatial propagation on. | An unavailable OpenCL request is an error. Receipts record `cv2.ocl.useOpenCL()` and the device. |

## 3. The one judgment call

**Is the GPU the goal, or the means?** v1 made CUDA execution a requirement. This version treats the GPU as a means and ships the capability first.

| Option | What it costs | What you get |
| --- | --- | --- |
| Capability first (my pick) | Five missions and no compiler | A working flow node on a stock wheel, then GPU work where a measurement earns it |
| GPU engineering first | A custom OpenCV 5.1 CUDA build on Windows as soon as the worker exists | The GPU story early, on a backend tied to one vendor |

The choice turns on what you want from the project, not on performance data. If the GPU work itself is what you want to build or show, say so: Mission 6 then runs right after M2 and gives a provisional verdict on worker timings, and M3 re-checks the 20% on the bake before adoption.

My view: the GPU path worth owning is native OpenCL inside Copernicus, with no vendor build.

## 4. First principles

Nine rules drive every decision below.

1. **Cross the boundary once, with the smallest payload.** Houdini's documented Python route moves pixels through host memory, and Copernicus has no HDK. Every hop is GPU to host to file and back, so prepare and post-process in native COPs and send one small grey image per frame.
2. **OpenCV is the eye; Copernicus is the brush.** OpenCV is used only for analysis Copernicus lacks. Anything Copernicus already filters on the GPU stays native.
3. **Operations are pure functions.** Arrays and parameters go in; arrays and a receipt come out. The library never imports `hou`, so every operation is testable anywhere.
4. **The agent can only verify what it can run.** Every mission ends in one command that passes or fails. There are three rungs: pure tests anywhere, `hython` on the workstation, GPU on the 4090.
5. **If you can score it, you can search it.** A pass or fail check lets an agent finish. A numeric score lets a search improve. Evolution is allowed where a trustworthy score exists, and nowhere else.
6. **Nothing is silent.** A requested backend that is unavailable is an error, never a quiet substitute. What ran is recorded. A missing cache is an error on the node, and a stale one is a warning. A check that cannot run is a failure, never a pass.
7. **Use Houdini's machinery before writing ours.** ROP Image writes and File COP reads. There is no job queue and no socket protocol.
8. **Build beside upstream.** Their repo stays pinned and untouched. Fixes travel as pull requests.
9. **Earn every optimisation.** Try what is already here first: analysis scale 0.5 was 3.3 to 3.4 times faster for 0.08 px more error. A new backend must cut the M3 bake receipt's median time by 20%. Even at infinite speed that needs flow to be a fifth of the bake, so GPU and evolve work start when the flow-compute median is a quarter of the receipt's median total, unless you choose GPU first (section 3). A recipe is promoted by the holdout rule in section 7.

## 5. Architecture

**Each frame crosses the boundary once, as a small file.** Houdini prepares and exports a grey analysis image, one worker process estimates the flow, and Houdini loads the result and converts it in a single node.

1. **Prep, in native COPs.** Luminance, gain, gamma and an optional downscale produce one grey analysis layer. Scene-linear plates need the gain and the gamma: in the sandbox, frames three stops over, quantised as they were, clipped four fifths of their pixels and doubled the error.
2. **Export, by ROP Image.** It writes `analysis.####.exr`, raw, plus one extra frame so every baked frame has a successor.
3. **Estimate, in the worker.** One process per bake: `python -m cvcops flow --frames 1001-1100` pairs each frame with the next, runs the recipe, and writes `flow.####.exr` with its receipt.
4. **Import, by File COP.** Incoming Colorspace Raw, Precision 32-bit (Default follows the network's setting), and Missing Data on Report Message, so a missing frame is an error.
5. **Convert, in one node.** It applies analysis scale, axis sign and units, and outputs `flow` as a UV layer, which Visualize Velocity reads, and `valid` as Mono.

A Bake button runs steps 2 to 4, starting the worker with the interpreter an environment variable names. One Houdini package file sets that variable and the asset path, so install is one file.

Two later lanes reuse the contract: Live, a Python Snippet COP calling the same recipe each cook (M5), and GPU (M6). SYNAPSE is the third consumer: it calls the same worker through `src/cvcops/capabilities.json`, and the engine never imports SYNAPSE (`docs/decisions/0001-synapse-umbrella.md`). `docs/ARCHITECTURE.md` maps every file.

The worker has its own environment: a `uv`-managed CPython 3.13 with exactly one OpenCV wheel, `opencv-contrib-python-headless==5.0.0.93`, plus `numpy` and `OpenEXR`. Houdini's own Python is never modified.


## 6. Flow contract v1

**Treat flow like a motion-vector AOV: comp never asks which renderer wrote it, only whether channels, units and space match.** The comparison breaks in one place. A renderer's vectors are ground truth from geometry, and optical flow is an estimate, so this file carries a validity channel. "Verified" below means in the Linux sandbox; probe P6 repeats it on Windows.

| Item | Contract | Status |
| --- | --- | --- |
| Analysis image | 8-bit, one channel, same size for A and B. Luminance weights, gain, gamma and analysis scale are recorded, with the share of clipped pixels and the grey levels used. The node warns above 5% clipped or below 32 levels. | Verified: DIS asserts 8-bit, one channel |
| Exchange in | `analysis.####.exr`, raw, written by ROP Image. The worker quantises to 8-bit. | Probe P3 |
| Direction | Forward, A to B: the content at pixel p in A is at p + flow(p) in B. | Verified by fixture |
| Stored convention | `opencv_px`: x right, y down, pixels of the analysis image, per frame pair. The worker never converts. | Verified |
| Conversion | Exactly one node in the asset applies scale, sign and units. The M3 fixture tests it. | Probe P4 |
| Exchange out | `flow.####.exr`, float32 RGB: R is u, G is v, B is validity, 1 or 0. Houdini loads it at 32-bit float: half float rounds motions of 512 to 1024 px by up to 0.25 px, and larger ones by more. | Round trip verified bit-exact |
| Validity | Forward-backward agreement within a tolerance (1.0 px by default, recorded), an in-bounds destination, and the optional input mask. It catches wide occlusions and misses narrow ones: a flag, not a confidence. | Measured; thresholds in section 8 |
| Time | A, B, fps and interval are recorded. No temporal hints, so cook order never matters. | Design |
| Resolution | Mismatched sizes are rejected. Nothing resizes implicitly. | Design |
| Recipe | A named pure function `estimate_flow(a, b)`. Stock presets are recipes too. The receipt records its name and source hash. | Design |
| Determinism | Same inputs, parameters and build give identical bytes on CPU, at any thread count. | Verified on 5.0.0, 1 to 48 threads |
| Receipt | `flow.####.json`, written last through a temp file and an atomic rename: status, input digests, parameter digest, recipe, `cv2` version and build hash, backend, threads, timings. | Design |
| Cache key | Input digests, parameter digest, recipe hash, backend, `cv2` version and build hash, contract version. The asset shows fresh, stale or missing. | Design |
| Limits | Patch size stays at or below 16 before OpenCV 5.1, which fixes a heap overflow above that. | From the 5.1 source and commit log |

## 7. Evolve lane

**OpenEvolve fits exactly one part of this project today: the flow recipe.** [OpenEvolve](https://github.com/codelion/openevolve) mutates a marked region of a program with an LLM and keeps what an evaluator scores higher. It needs four things: a program to edit, a numeric score, cheap evaluations and a budget.

| Target | Score | Cost per evaluation | Verdict |
| --- | --- | --- | --- |
| Flow recipe `estimate_flow(a, b)` | Speedup behind an accuracy gate against exact ground truth | 11.2 s on the 15-pair suite in the sandbox, CPU only, no Houdini | First target |
| Native OpenCL kernels | Speedup behind an exact-match gate | Unknown until probe P8 | Later, for a kernel the receipts show is hot |

I built the evaluator first, after OpenEvolve's [background-blur example](https://github.com/codelion/openevolve/tree/main/examples/background_blur): quality is a hard gate and speed is the score.

| Check | Result in the sandbox, OpenCV 5.0.0, 960 by 540 |
| --- | --- |
| Runs under OpenEvolve 0.4.1 | The config loads and the cascade evaluator runs. No model calls were made. |
| Six deliberate cheats | All score 0, each with a stated reason. |
| My first dev suite | Too easy: stock FAST scored 4.4 to 4.7 times and half-resolution MEDIUM 3.6 to 3.9, yet both fail the holdout. Drawing motion from ranges fixed it; on the 15-pair dev suite both score 0. |
| A sweep before any search | MEDIUM with two refinement iterations instead of five: 1.22 times on dev and 1.33 to 1.36 on the holdout. It becomes the seed and the bar, so the search must reach about 1.53 times. |
| Not done | No evolution run. The sandbox had no model for it to call. |

So the search has one concrete question: is there a recipe 15% faster than the swept one that holds the gate on the 25-pair holdout? If 300 iterations find none, the swept recipe ships.

Nine rules govern the lane.

1. **The evaluator is the product.** The cheats and the known dead ends must score zero before a token is spent.
2. **Gates are hard and relative to a reference.** Fast and wrong scores zero. Each fixture is judged against the reference's own error on it.
3. **Grade the worst region, not the average.** A mean hides an erased object. The worst 32 by 32 block does not.
4. **Time fairly.** One evaluation at a time, reference and candidate interleaved, a warm-up, the minimum of several runs, an idle machine. A local model runs on another machine, or the spread is measured with it loaded.
5. **The search never touches its judge.** Only the marked block in one file may change. The judge files sit under `ask` rules and a hash lock (section 9).
6. **Sweep before you search.** Numeric knobs are a sweep's job. The search starts from the sweep's winner and looks for structure a sweep cannot express.
7. **The holdout decides.** 25 pairs from the same distribution with unseen seeds. A candidate must pass every pair and beat the best passing rival by 15%, or by the workstation's measured spread if that is wider.
8. **Evolved code enters like any other code.** A reviewed change, rung-1 tests green, recipe name and hash in the receipt.
9. **Budget first.** A local model behind an OpenAI-compatible endpoint is the default; Claude through the Claude Code CLI is a one-block swap with a per-call cap. A run is a background command outside any Claude session, with its total cap written in `docs/STATE.md` before launch. Up to three runs of 100 iterations; read the trace after the first 20 to 50; stop at 300 without a promotion.

**The north star is OpenCV as oracle and OpenCL as runtime.** After the lane's first verdict, the same evaluator can score native OpenCL kernels, so flow could run live inside Copernicus. It waits on probe P8.

## 8. Missions

**Five missions reach v0.1, and each closes on one command that passes or fails.** Run one mission per Claude Code session. A mission that needs a second session records why in `docs/STATE.md`; one that needs a third stops, because the plan is wrong. Optional missions have their own entry gate.

| Mission | Goal | Done when | Needs you | Tier |
| --- | --- | --- | --- | --- |
| M0 Ground truth | In order: confirm the shipped rules, probes P1 to P7 (P4 fills `tests/thresholds/houdini_units.json`), the judge's self-test on Windows, then your lock. | `uv run python tools/check.py` passes, `check.py --selftest` shows the reference passing and every planted fault failing, and `docs/FACTS.md` records all seven probe results | A licence; trust the folder and confirm the rules; run `tools/lock_judge.py` when asked. The workstation. | Heavy |
| M1 Flow operation | `estimate_flow` and validity as pure functions, with ground-truth fixtures | `uv run python tools/check.py` meets every M1 threshold below | Nothing | Light |
| M2 Worker CLI | `python -m cvcops flow` reads EXR and writes flow plus receipts atomically. `verify` reports fresh, stale or missing. | `check.py` passes the M2 row and the agent's own tests in `tests/unit/`: a CLI round trip, an interrupted write, and stale on a changed `cv2` version | Nothing | Light |
| M3 Bake asset | The asset is built by script. It bakes, loads and converts. One example scene, whose bake receipt records medians over five runs. | `uv run python tools/check.py --houdini`: the M3 fixture is within tolerance, and the bake receipt holds medians for export, flow compute, worker I/O and load. Under GPU first, also bake with the provisional CUDA recipe (M6 step 8) and write adopt or keep CPU in `docs/STATE.md` | Confirm the arrows in the example follow the pattern | Heavy |
| M4 Warp | Pull frame B onto A's grid through native Distort with the converted forward flow. If it meets the warp threshold, ship an example; if not, build Flow Warp to that test. | `--houdini` passes the warp threshold and the example renders | Pick the example's look | Heavy |
| Release gate v0.1 | A README with measured numbers, limits and the one-file install | Every rung that applies is green on the workstation, and one plate of yours bakes | A plate, and your sign-off on what the flow does to it | |
| ME Evolve the recipe | Entry: the M3 bake receipt shows flow is a quarter of the time. Sweep, then search in the background. | `promote.py` returns a verdict; it refuses to run until `test_gaming.py` passes and `sweep.py` has run. At most 300 iterations | A model choice and an idle machine | Light |
| M5 Live lane | Entry: P2 and P5 passed, or a two-input OpenFX node cooks with frame B fed through Time Shift. Wrap the same recipe in whichever passed. | The `--houdini` live test | Scrub and judge | Heavy |
| M6 GPU lane | Entry: the M3 bake receipt shows flow is a quarter, or you chose GPU first. Score DIS on OpenCL first; if it reaches adopt, stop. Otherwise ask before the CUDA build in `docs/missions/M6_cuda_build.md`, which reuses your OpenCV 5.1 prep toolchain. | `check.py --gpu` passes and `docs/STATE.md` records a verdict: adopt a named recipe that passes the holdout gate and cuts the M3 bake by 20%, or keep CPU; under GPU first, a provisional verdict on worker timings | The CUDA decision | Heavy |
| MN Native kernels | Entry: ME returned a verdict and probe P8 passed: a headless harness compiles and times an OpenCL COP kernel. | An OpenCL flow kernel scored by the evolve evaluator | Parked | |
| MU Upstream | Entry: any time. Five fixes as failing test plus patch in `upstream-fixes/`, a separate clone at `d2a22ad`, never in `vendor/`. A licence request. | Each test fails on `d2a22ad` and passes with its patch | You send the pull requests | Light |

Mission 0 answers seven questions by running code. P2 and P5 serve the live lane, so they wait for M5's entry gate.

| Probe | Question | If it fails |
| --- | --- | --- |
| P1 Environment | `probes/p1_environment.py` records the Houdini build, Python, NumPy, licence category and site-packages. Are Git Bash and `uv` present? Does `hython` get a licence with the kit's own preferences folder? Does `import OpenEXR` work in it? Machine paths go in an untracked `local.toml`. | Rung-2 tests read EXR via the worker. |
| P2 Layer buffers | What are the row order and origin of `allBufferElements`? | Deferred unless P3 fails. |
| P3 Raw round trip | Which File COP and ROP Image settings carry the kit's transport pattern through Houdini bit for bit? Start from Raw and 32-bit on both; `probes/p3_transport.py` judges what comes back. The pattern has negative values, values far above 1 and values half float cannot hold. | Exchange `.npy` through a Python node instead; P2 becomes required. |
| P4 Vector convention | How does pixel motion to the right and down map to Houdini image space? What do Distort, UV Inverse and Visualize Velocity expect? Copernicus puts pixel origins at the lower left, so expect v to flip. | The M3 two-region fixture decides. |
| P5 Python Snippet COP | What types arrive in `kwargs`? Does `cv2`, loaded from a side directory on `sys.path`, work with Houdini's NumPy? Is the overhead under a third of the flow time, and flat over 500 cooks, with Maintain State on and off? | The live lane stays parked. |
| P6 Worker environment | Does the `uv` venv build with pinned wheels on Windows? Which `cv2.ocl` device does the 4090 report? Re-run the evidence scripts and record workstation timings. | Use a plain venv on python.org CPython 3.13. |
| P7 Asset build | Can `hython` build the HDA by script, and which licence flavour does it carry? | Build once in a GUI session from the script's steps, and ship the script. |

**The table below is the exam, and the kit already holds a reference that passes it.** `evidence/thresholds_reference.py` computes every row on pinned fixtures with stock DIS and shows nine planted faults each failing a row. `tests/thresholds/` calls those same computations, one test per row, and invents nothing. Each test grades an object with five methods, `flow`, `valid`, `pull`, `write_exr` and `read_exr`. `tests/thresholds/impls.py` builds one from the engine's code, one that runs the asset through `hython` for M3 and M4, and the reference and its faults for the self-test. A scratch run of a mission's life, a stand-in asset included, passes 18 cases.

You lock them once, after `check.py --selftest` shows the reference passing and every fault failing, and after comparing `check.py --list` with this table. `check.py` runs the tests of the missions listed in `tests/thresholds/mission.txt`, every mission started so far, skips the rest, and fails if a listed threshold has no test. At each mission's start you add it, run `tools/lock_judge.py` and commit both; a session that finds its mission missing writes `WAITING:`. Later missions only make locked tests pass. Changing one needs a line in `docs/STATE.md`, your approval and a re-lock.

| Mission | Test | Threshold | Sandbox measurement |
| --- | --- | --- | --- |
| M1 | Periodic shifts, DIS MEDIUM, mean error | at most 0.05 px | 0.018 to 0.023 px |
| M1 | Periodic shifts, DIS FAST, mean error | at most 0.15 px | 0.058 to 0.102 px |
| M1 | Zero motion, mean error | at most 0.01 px | 0.000 px |
| M1 | The 15-pair suite, MEDIUM, mean error over the pairs | at most 0.12 px | 0.083 px |
| M1 | Validity at 1.0 px: valid pixels flagged invalid, worst pair of the suite | at most 3% | 1.92% |
| M1 | Validity at 1.0 px: occluded pixels caught, two regions 16 px apart in motion | at least 0.85 | 0.929 |
| M1 | Determinism on CPU | identical bytes across two runs and two thread counts | identical |
| M2 | EXR write then read, the transport pattern | bit-exact | bit-exact |
| M3 | two regions with different motion, dx and dy unequal and non-zero, MEDIUM, valid pixels 8 px from the boundary, full-resolution pixels, at analysis scale 1.0 | at most 0.10 px | 0.037 px |
| M3 | the same at analysis scale 0.5 | at most 0.25 px | 0.115 px |
| M4 | frame B pulled onto A's grid by the forward flow, against A, the 12 pairs of the suite without a brightness change | at most 1.5 levels mean error, 8-bit | 0.33 to 1.00 levels |

On 100 fresh draws no row failed; the occlusion row came closest, 0.869 against 0.85.

## 9. Operating rules for Claude Code

**Rules that cannot bend are enforced by the harness, and the rest live in a short CLAUDE.md.**

| Rule | Enforced by | Why |
| --- | --- | --- |
| A turn ends green, or says why not | A Stop hook runs `tools/check.py --hook` (rung 1, the lock and the pause line) and blocks on any failure, a crash or a missing tool included. It lets the turn end only when the first line of `docs/STATE.md` starts with `WAITING:` (a plan or a question for you; the agent clears it on resuming) or `BLOCKED:` (stuck, or a judge change is needed; only you clear it). Plain `check.py` fails while either stands | "Looks done" is not done, yet a pause for you must not cost eight blocked retries |
| The judge does not move | `ask` rules on `tests/thresholds/` (thresholds, locked tests, `mission.txt`), `tools/check.py`, `tools/lock_judge.py` and the evolve judge files. The rules on the tests and on `check.py` arm at your first lock, so M0 can draft them. Claude Code itself prompts on any write under `.claude/` or `.git/`. `check.py` fails when a judge file or `.claude/settings.json` differs from `judge.lock` | An agent graded by its own tests can pass by loosening them |
| A broken environment is not a failing test | `check.py` exits differently for the two and runs every check under a time limit, two minutes for rung 1. On no `hython`, no licence, no device or a timeout, the agent writes `BLOCKED:` and edits no code | Code edits cannot cure a licence error |
| `vendor/` is read-only | A deny rule | Upstream is not ours to change |
| No install into Houdini's Python | Deny rules on `hython -m pip`, by any path to `hython`, and `check.py --houdini` fails if Houdini's site-packages listing changes from P1's record. It runs `hython` with a kit-owned preferences folder | Protects the install |
| No `hou` import under `src/` | A unit test that scans imports | Keeps operations testable anywhere |
| One mission per session, then `/clear`; evidence with every "done"; no Houdini GUI; no fan-out; model tiers | CLAUDE.md | Habits, not walls: evidence goes into `docs/STATE.md`, a viewport needs eyes, one reviewer pass per mission at most |

The kit ships these rules as `.claude/settings.json`, so they hold from the first session; confirm them with `claude doctor` (the file passed on Claude Code 2.1.319), `/hooks` and `/permissions`. Rules match the text of a command and miss a script that writes a file, so they are guard rails and the lock is the check: it makes a judge change impossible to miss, not impossible. Only you lock, by running `tools/lock_judge.py` outside Claude and committing `judge.lock`.

Only M1 and M2 run unattended. `bash tools/unattended.sh M1` refuses unless the committed `mission.txt` lists the mission and the judge matches its lock, then starts a print-mode run on its own worktree branch, capped at 60 turns, where nobody can approve a judge edit. The script ends by listing any judge file the branch touched anyway. Merge only if that list is empty and `check.py` passes on your checkout. Never use `bypassPermissions`: it lets writes to `.claude/settings.json` through without a prompt.

## 10. Upstream track

**Five fixes and one request go to MotionCOPs as pull requests, not into a fork.** Each arrives as a failing test plus a patch. Every fix reaches Houdini only when the author rebuilds the asset, since the recorder script ships inside it and a pull request cannot carry a reviewable binary.

| Finding | Where | Fix | Test |
| --- | --- | --- | --- |
| Integer luminance loses its scale | `_layer_values`, lines 161 to 195 of the recorder script | Normalise integer samples before the weighted sum | Fixed8 and Fixed16 white read 1.0 in both modes |
| The final fractional sample has no index | `_frame_index`, lines 283 to 292 | Search the actual sample list with a tolerance | Schedule (1, 2, 0.3) maps to indices 0 to 4 |
| Bookkeeping precedes publication | `_append_slice`, lines 584 to 621 | Update `captured`, `last_frame` and the range only after the cooks succeed | A forced failure leaves the state unchanged |
| Pixel sort write conflict | The `pixel_sort` kernel in the Pixel Sorting 1.1 asset | Gather form: each pixel reads its pair and writes only itself | Every pass is a permutation of the row, checked against a CPU model |
| The builder uses absolute paths | Lines 10 and 11 of the builder script | Repo-relative paths and arguments | Builds from a fresh clone |
| No licence | Repo root | Ask the author to add one | |

## 11. Risks and kill criteria

**Each risk has a signal to watch and a response decided in advance.**

| Risk | Signal | Response |
| --- | --- | --- |
| The agent loosens its own judge | `judge.lock` mismatch | Stop with `BLOCKED:`. Re-lock only after your approval. |
| Orientation, sign or colour is wrong at the Houdini boundary | The M3 fixture fails | Fix it in the one conversion node. Fall back to `.npy` only if EXR cannot be made raw. |
| File I/O dominates the bake | Receipt timings show it | Run frame chunks in parallel processes, test EXR compression, lower the analysis scale. Do not reach for CUDA. |
| The CUDA build becomes a time sink | More than one session | Stop and keep CPU and OpenCL. |
| OpenCL runs partly on CPU | OpenCL timing equals CPU timing | Judge OpenCL by timing, not by the flag. |
| Upstream stays unlicensed | No reply | Ship none of their files. |
| No evolved recipe beats the swept one | 300 iterations without a promotion | Stop. Ship the swept recipe and record the result. |
| Scope creep | A node beyond flow (and Flow Warp, if M4 needs it) before v0.1 | Park it in section 12. |
| Indie-built assets may downgrade commercial sessions | Probe P7 | Ship the builder script, so each user builds under their own licence. This one is unverified. |

## 12. Parked until v0.1 ships

**Nothing below starts before the release gate.** Ranked by my judgment of value for motion design.

1. Temporal check: rank frames by what the flow cannot explain, which finds pops and flicker for SYNAPSE.
2. Backward flow as a second layer: the worker already computes it for validity.
3. Motion matte: MOG2 or KNN background subtraction from locked-off footage.
4. Feature tracks: KLT points with ids, delivered to SOPs.
5. Stabilise and match: multi-scale ECC to transform parameters.
6. Neural flow through the native ONNX Inference COP, behind the same contract and without OpenCV.
7. Native OpenCL flow kernels, the north star in section 7.

Do not build an HDK plug-in, zero-copy GPU sharing, a job queue, a socket protocol, or any node Houdini 22 ships, such as corner detection, blobs to points, MoGe-2 depth, SAM2 masks, denoise or FFT. Zero-copy is FRAGMENT's question, at its fourth milestone.

## 13. Kickoff prompt

**Paste this as the first message of the first Claude Code session, in a fresh repo that holds the kit, on a machine with Git Bash and `uv`.**

```text
Read CLAUDE.md, docs/BLUEPRINT.md, docs/FACTS.md and docs/STATE.md. We are at Mission 0.
Plan first: list the seven probes, what each records and where, and what you need from me.
Whenever you need me, put WAITING: and what you need on the first line of docs/STATE.md, then stop. Do that now, for the plan.
Then run Mission 0 only. Stop the same way when the probes are recorded and the self-test passes, for my lock. Finish when tools/check.py passes and docs/FACTS.md records all seven probe results.
Finish by updating docs/STATE.md: where we are, evidence, next action, blockers.
```

## 14. Sources

Every page below was opened on 8 or 9 November 2026. Repositories were read at the commits named. On 9 November the workstation's copy of the 22.0.429 docs, from 4 October, agreed with them.

- [motion-cops at d2a22ad](https://github.com/Boning1011/motion-cops/tree/d2a22ade06132381a1ce68ddbc9df80782e35a51) and its [recorder script](https://github.com/Boning1011/motion-cops/blob/d2a22ade06132381a1ce68ddbc9df80782e35a51/scripts/mc_texture_to_volume_cpu.py)
- [OpenCV 5.1.0 release](https://github.com/opencv/opencv/releases/tag/5.1.0) and [opencv_contrib 5.1.0, cudaoptflow](https://github.com/opencv/opencv_contrib/tree/5.1.0/modules/cudaoptflow)
- [opencv-python-headless on PyPI](https://pypi.org/project/opencv-python-headless/)
- SideFX Houdini 22: [Copernicus what's new](https://www.sidefx.com/docs/houdini/news/22/copernicus.html), [platform changes](https://www.sidefx.com/docs/houdini/news/22/platforms.html), [COP node index](https://www.sidefx.com/docs/houdini/nodes/cop/index.html), [OpenFX](https://www.sidefx.com/docs/houdini/copernicus/openfx.html), [spaces](https://www.sidefx.com/docs/houdini/copernicus/spaces.html), [ROP Image](https://www.sidefx.com/docs/houdini/nodes/cop/rop_image.html), [Python Snippet COP](https://www.sidefx.com/docs/houdini/nodes/cop/pythonsnippet.html), [File COP](https://www.sidefx.com/docs/houdini/nodes/cop/file.html), [hou.ImageLayer](https://www.sidefx.com/docs/houdini/hom/hou/ImageLayer.html), [hou.CopNode](https://www.sidefx.com/docs/houdini/hom/hou/CopNode.html), [packages](https://www.sidefx.com/docs/houdini/ref/plugins.html), [HDK operator basics](https://www.sidefx.com/docs/hdk/_h_d_k__op_basics.html) and the [`IMX_Layer` reference](https://www.sidefx.com/docs/hdk/class_i_m_x___layer-members.html)
- [NVIDIA Optical Flow SDK documentation](https://docs.nvidia.com/video-technologies/optical-flow-sdk/index.html)
- [OpenEvolve repository](https://github.com/codelion/openevolve) at commit 3e72b5b, and the [blog post](https://huggingface.co/blog/codelion/openevolve) that introduced it
- Claude Code [best practices](https://code.claude.com/docs/en/best-practices), [permissions](https://code.claude.com/docs/en/permissions), [permission modes](https://code.claude.com/docs/en/permission-modes), [hooks](https://code.claude.com/docs/en/hooks), [tools](https://code.claude.com/docs/en/tools-reference), [CLI flags](https://code.claude.com/docs/en/cli-reference) and [headless runs](https://code.claude.com/docs/en/headless)
- [FRAGMENT](https://github.com/JosephOIbrahim/FRAGMENT) at commit f5a023e
