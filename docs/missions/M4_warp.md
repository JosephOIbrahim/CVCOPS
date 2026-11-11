# Mission M4: the warp

A proposal from the planning panel of 2026-11-10, not adopted. The blueprint's M4 row governs; this brief adds the
order, the files and the checks. Graph and conventions: `docs/missions/GRAPH.md`.

**Goal.** Pull frame B onto A's grid through native Distort with the asset's converted forward flow. If that meets the
warp threshold, ship an example that carries a fix from a later frame onto earlier ones. If not, ask Joe before
building Flow Warp to the same test.

**Entry.** M3 is closed and committed, and the DEC.quarter verdict is in STATE. The committed
`tests/thresholds/mission.txt` lists M4. If not, write `WAITING:` and stop.

**Done when.** `uv run python tools/check.py --houdini` passes the M4 row (B pulled onto A, 12 pairs, at most 1.5
levels mean error, 8-bit) beside both M3 rows, the example renders, Joe has looked at it, and `docs/STATE.md` holds the
closing commands and their tails.

**Tier.** Heavy. Not unattended: the look is Joe's, and Flow Warp, if needed, is his call.

## How the session runs

1. **Read** `CLAUDE.md`, `docs/BLUEPRINT.md`, `docs/FACTS.md`, `docs/STATE.md` and this brief. Joe chose the
   example's look in the M4 start sitting (OD-21).
2. **Baseline.** Rung 1 passes for M0 to M4. Rung 2 exits 1 with both M3 rows passing and only `pull_warp` failing.
   The hython path and sha256 match M3's baseline.
3. **Pause.** `WAITING:` with the plan and the new files. Stop for Joe's OK.
4. **Probe Distort** against `cv2.remap` on the suite and on a field above 100 px, with Pixels per Step off and on.
5. **Build the pull** in `bake_once.py --mode pull` and `cvcops_houdini/pull.py`.
6. **First read.** Grade the `pull_warp` row once. At most 1.5 levels: go on. Above: stop and ask Joe about Flow Warp.
7. **Carry example.** Time Shift check first, then the unrolled chain, then the render.
8. **Look.** Joe looks at the render and closes Houdini after. The reviewer pass runs once the look is recorded.
9. **Close.** Rung 1, rung 2 with three rows, the render rerun, the hython identity, STATE. Joe commits.

Budget: one session. Rung 2 is 19 hython calls; M3's close projects their time against `check.py`'s 3600 s before
this session starts.

## Tasks

In dependency order. Support names who runs it; "(joe)" or "(hython)" is the resource it holds.

| # | Node | Task | Writes | Proves | Support |
| --- | --- | --- | --- | --- | --- |
| 1 | `M4.gate.start` | Joe adds M4 to mission.txt, locks, commits 'Start M4' | nothing | git show HEAD:tests/thresholds/mission.txt lists M4 | joe (joe): Joe's own edit, lock and commit |
| 2 | `M4.judge.rung2_baseline` | M4 start: rung-1 and rung-2 baseline with only pull_warp failing, and the hython identity | `docs/STATE.md`, `probe_out/m4_baseline.log` | uv run python tools/check.py ends 'CHECK: rung 1 passes for M0, M1, M2, M3, M4 (8 threshold rows)'; uv run python tools/check.py --houdini (background, exit appended to probe_out/m4_baseline.log) exits 1 with both M3 rows passing and only pull_warp failing on bake_once.py --mode pull's not-built message | hython_serial (hython): Eight hython calls; nothing may overlap |
| 3 | `M4.plan` | M4 plan: baseline cited, node order, the new files, then the pause for Joe's OK | `docs/STATE.md` | The first line of docs/STATE.md is the pause line carrying the plan; git diff --stat touches only docs/STATE.md; Joe's OK is recorded when the session resumes | joe (joe): CLAUDE.md: plan first, then pause for Joe's OK; no spine gate follows this plan, so the node itself waits on Joe |
| 4 | `M4.cop.probe-distort` | Probe: Distort's step modes against cv2.remap on varying fields, including one above 100 px | `probes/m4_distort.py`, `docs/FACTS.md` | uv run python probes/m4_distort.py make probe_out/m4; uv run python probes/hython.py probes/m4_distort.py cook probe_out/m4; uv run python probes/m4_distort.py judge probe_out/m4 prints per-case level differences for both step modes and VERDICT step_mode, and exits 0 | hython_serial (hython): One hython cook of 13 cases in two modes; its verdict sets the pull and the carry chain |
| 5 | `M4.cop.pull` | bake_once --mode pull: frame B pulled onto A's grid by native Distort at Scale -1, with a reusable pull_network | `houdini/tests/bake_once.py`, `houdini/python3.13libs/cvcops_houdini/pull.py` | uv run python probes/hython.py houdini/tests/bake_once.py --mode pull --dir &lt;dir> exits 0 and writes &lt;dir>/pulled.1001.exr at full size, grey in R, within 600 s; with the asset uninstalled it exits 3 | hython_serial (hython): bake_once.py is a single-writer judge-facing script proved in hython |
| 6 | `M4.judge.warp_first_read` | M4 first read: the pull_warp row through native Distort decides between the example and Flow Warp | `docs/STATE.md`, `probe_out/m4_first.json`, `probe_out/m4_first.log` | CVCOPS_IMPL=houdini CVCOPS_ROWS=pull_warp CVCOPS_RESULTS=probe_out/m4_first.json uv run python -m pytest tests/thresholds/test_thresholds.py -q -rN -p no:cacheprovider (background, exit appended to probe_out/m4_first.log) gives a pull_warp value, recorded in docs/STATE.md beside 1.5 levels with the decision | hython_serial (hython): Twelve serial hython bakes |
| 7 | `M4.cop.flowwarp-decision` | Decision (only if Distort cannot pull): build Flow Warp, a new node | `docs/STATE.md` | docs/STATE.md records either 'Flow Warp not needed' beside the probe's and the row's numbers, or Joe's answer beside them | joe (joe): A new node and a new [tool.cvcops.names] entry are Joe's call; he is interrupted only when the numbers miss |
| 8 | `M4.cop.carry-example` | M4 example: a fix painted on a later frame carried back onto earlier frames | `examples/two_region/make_frames.py`, `houdini/examples/build_scene.py` | uv run python examples/two_region/make_frames.py --fix; uv run python probes/hython.py houdini/examples/build_scene.py carry --bake --render; uv run python examples/two_region/make_frames.py --check-carry: all exit 0, the last printing the carried mark's centroid error per frame | hython_serial (hython): Scene build, bake and render in hython; extends M3's example scripts with one writer |
| 9 | `M4.gate.look` | Joe picks the example's look and looks at the result | `docs/STATE.md` | Joe says so; recorded in docs/STATE.md | joe (joe): Looks are Joe's gate |
| 10 | `M4.judge.review` | M4's one read-only reviewer pass, with the promise-drift checks | nothing | One subagent report on git diff &lt;Start M4 commit>..HEAD plus git status --porcelain: gaps with file:line, or 'no correctness gaps'; git diff --stat &lt;Start M4 commit> -- src/cvcops/capabilities.json src/cvcops/receipt.py houdini/build/controls.json docs/contracts lists only changes named in STATE; uv run pytest tests/unit/test_controls.py tests/unit/test_cli.py tests/unit/test_manifest.py -q -p no:cacheprovider passes; uv run python evidence/audit_receipts.py &lt;M4 example cache> --frames &lt;range> --expect-sidecar exits 0 | readonly_subagent: Merges the judge review and the contract drift review into the mission's single pass |
| 11 | `M4.judge.close` | M4 closing evidence: three rung-2 rows, the example renders, the hython identity, STATE entry | `docs/STATE.md`, `probe_out/m4_rung2.log`, `probe_out/m4_rows.json`, `probe_out/m4_rows.log`, `probe_out/m4_p1_close.json` | uv run python tools/check.py --houdini (background, exit appended to probe_out/m4_rung2.log) ends 'CHECK: rung 2 passes (3 threshold rows; Houdini's Python unchanged since P1)', exit 0; uv run python tools/check.py ends 'CHECK: rung 1 passes for M0, M1, M2, M3, M4 (8 threshold rows)', exit 0; the example's render command exits 0 and its frames exist | hython_serial (hython): Rung 2 is 19 serial hython calls plus the render and values run |
| 12 | `M4.gate.close` | Mission 4 closes | nothing | uv run python tools/check.py --houdini exits 0 with the M4 row listed and passing; the example scene carries a fix from a later frame onto earlier ones; docs/STATE.md log entry | main_only: Evidence comes from M4.judge.close |

## What each task must show

- **`M4.judge.rung2_baseline`.** Split from the judge's first-read node. Exit 3, or a licence or start-up FAIL, means the blocked line and no code edit (OD-19). The hython path, size and sha256 from local.toml equal M3's baseline. STATE records the tail and wall time beside M3's projection.
- **`M4.plan`.** Cites the baseline and M3's per-call projection onto M4's 19 calls. Lists node order and every new file: probes/m4_distort.py and houdini/python3.13libs/cvcops_houdini/pull.py, plus the edits to houdini/tests/bake_once.py (--mode pull), houdini/examples/build_scene.py (carry mode) and examples/two_region/make_frames.py (--fix, --check-carry). Restates Joe's look choice from joe batch 7 (OD-21). States that Flow Warp is not planned and is asked only if the first read misses (OD-20). No judge file, dependency or new node.
- **`M4.cop.probe-distort`.** 12 non-exposure suite pairs (ground truth in image units per houdini_units.json) plus one smooth zoom-and-rotate field reaching about 150 px on a textured 1920x1080 frame, through Distort at Scale -1, Scale by Timestep off, Bilinear, with Pixels per Step off and on at defaults. Per case and mode: mean absolute 8-bit difference from cv2.remap(B, p + f, INTER_LINEAR, BORDER_REPLICATE) on the 24 px interior, and the pull_warp metric against A. FACTS records the step tokens, the edge behaviour found, defaults and numbers. Verdict picks the mode within 0.1 level of remap on every case (proposed), states whether the large field hits the step cap, and states the varying-field risk. If no mode is within 1.5 levels of A on every pair, M4.cop.flowwarp-decision opens.
- **`M4.cop.pull`.** Merges the COP and HOM pull nodes. pull.py sits under the stamped houdini/python3.13libs/, so once it is written this node rebuilds the asset (uv run python probes/hython.py houdini/build/build_hdas.py --out houdini/otls) and re-runs houdini/tests/build_selftest.py before the pull is proved; the first read, the example and rung 2 use that build. The pull branch sits beside --mode flow and adds only that branch. frame.1001.exr feeds the asset's source and frame.1002.exr Distort's source, both with P3 File COP settings; bakes 1001 at defaults through bake(node). Distort takes B and the asset's Flow output on dir at Scale -1, Scale by Timestep off, the probe's step mode, Bilinear, edge handling as the probe found: no second conversion. pull_network(parent, b, flow, settings) lives in cvcops_houdini/pull.py for the examples, imports no cv2 and runs nothing at import. ROP Image writes raw float32 to &lt;dir>/pulled.1001.exr. Exit 3 for a missing asset or licence; no cv2. STATE records wall time per call so the row's 12 calls are known before grading.
- **`M4.judge.warp_first_read`.** At most 1.5: record 'native Distort passes; ship the example'. Above 1.5: the pause line for Joe with the value, through M4.cop.flowwarp-decision; nothing built first. Value, decision and wall time go into STATE.
- **`M4.cop.flowwarp-decision`.** Conditional (OD-20). Within bounds: main records 'not needed' and Joe is not asked. Otherwise the pause line puts to Joe the failed cases and margins, the one-node shape, the names entry and the cost. No Flow Warp code before his yes; a yes inserts a Flow Warp build node, graded by the same row, before M4.cop.carry-example, and names its new files in STATE as M4.plan did; a no records the miss and stops M4.
- **`M4.cop.carry-example`.** (1) First: Time Shift (Custom) on the flow output returns that frame's flow, checked against its own cook. (2) The look chosen at M4's start (default OD-21: premultiplied RGBA mark on the disc at key 1024) is carried back onto 1016-1023 by an unrolled chain of K = 8 pull_network steps; step k gets frame 1024-k's flow via Time Shift; a Switch on 1024 - $F picks the step; Blend Over composites on the plate; frames after the key show no fix (forward flow only). (3) Frames 1016-1024 render to EXR in a git-ignored folder; the centroid lands within 0.5 px per step of the disc's true motion. The carry mode keeps build_scene.py's hou check at the top of main().
- **`M4.judge.review`.** Checks: the pull feeds the asset's converted flow to Distort at Scale -1 with no second conversion node; bake_once.py --mode pull keeps impls.py's contract; the example is built by script and nothing launches the GUI; Flow Warp exists only if the first read failed and Joe said yes; manifest, receipt.py, sidecar and controls unchanged unless STATE names the change; the hython path and sha256 match M3's baseline; no judge file touched and no dependency added. Correctness only.
- **`M4.judge.close`.** After Joe's look. The render rerun lists frames with count, size and sha256 in a git-ignored folder; rung 1 timed (entry-point test now covers new houdini scripts); rung 2 wall time quoted against 3600 s; values run for all three rows beside their limits; probes/p1_environment.py --record probe_out/m4_p1_close.json reports 22.0.492 and the licence, and the hython path, size and sha256 equal M3's baseline; --list shows 11 rows listed; gates.py PASS. STATE: capsule and one log entry with tails, the first read's decision, Joe's look, reviewer gaps and fixes, closing command and tail.

## Open questions

| ID | Question | Default | Blocks here |
| --- | --- | --- | --- |
| OD-19 | How are licence losses and rung-1 timeouts classified? | A rung-2 FAIL whose message is a licence or hython start-up error counts as exit 3: write the blocked line and make no code edit. Never run two hython at once, and no hython while Joe's GUI is open. If pytest --durations pins a rung-1 timeout on a test this session added, trim that test and note it in STATE. Any other exit 3 is blocked. | `M4.judge.rung2_baseline`, `M4.judge.close` |
| OD-20 | Which Distort step mode pulls like cv2.remap, and if none passes 1.5 levels, is Flow Warp built? | Pixels per Step off (one lookup at p + f), confirmed on the suite and on a 150 px field. If no mode passes, stop and ask. The proposal is cvcops::flowwarp::1.0, built from a new hda_flowwarp names entry by the same builder and graded by the same row. Nothing is built before Joe says yes. | `M4.cop.pull`, `M4.cop.flowwarp-decision`, `M4.cop.carry-example` |
| OD-21 | What fix does the M4 example carry, from which key frame, how far back, and with what look? | A soft-edged coloured mark painted on the disc at key frame 1024, carried back 8 frames (1016-1023) by an unrolled Distort chain and composited Over the plate. Joe can change any of these at the M4 start sitting. | `M4.cop.carry-example`, `M4.gate.look` |

## Risks

| Risk | Signal | Response |
| --- | --- | --- |
| Distort with a per-pixel varying field does not pull like `cv2.remap` | The probe's level differences, or the first read above 1.5 | Stop and ask Joe about Flow Warp (OD-20). Nothing is built before his yes. |
| Large motions hit Distort's step cap | The 150 px case diverges with Pixels per Step on | Use the mode with one lookup at p + f; the README states the cap. |
| Distort's edge handling differs from `BORDER_REPLICATE` | The edge ring differs; there is no `border` id on the 22.0.492 page | Grading uses the 24 px interior; the probe records what Distort does at edges. |
| A second conversion slips into the pull | Flow scaled or flipped again before Distort | The pull feeds the asset's converted output to Distort at Scale -1 directly; the reviewer checks it. |
| Time Shift on the flow output does not cook the asset at the shifted frame | Step 1 of the carry example fails | Fix that before building the chain; it is the only untested link. |
| Rung 2 runs past 3600 s | M3's projection, or the baseline's wall time | Report it at the plan pause; the judge's limit is not changed. |
| hython runs while Joe's GUI holds the licence | A licence error in a log | Every hython node is ordered against the look gate; nothing runs until Joe says Houdini is closed. |

## Houdini names

| Name | Status | Source | Node |
| --- | --- | --- | --- |
| distort scale=-1, scalebytimeinc=0, dir from a UV layer | locally_tested | docs/FACTS.md P4; probes/p4_units.py | `M4.cop.probe-distort` |
| distort cfl (Pixels per Step), maxsteps | documented | help:22.0.492/nodes.zip/cop/distort.txt; values not in FACTS | `M4.cop.probe-distort` |
| distort Pixels per Step on/off token | proposed | help:22.0.492/nodes.zip/cop/distort.txt has no separate toggle id (maxsteps applies 'when Pixels per Step is on'); read by this probe | `M4.cop.probe-distort` |
| distort filter = Bilinear | documented | help:22.0.492/nodes.zip/cop/distort.txt, #id filter | `M4.cop.probe-distort` |
| distort edge handling (border) | proposed | no border id on help:22.0.492/nodes.zip/cop/distort.txt; read by this probe | `M4.cop.probe-distort` |
| distort Scale -1 as the pull | locally_tested | docs/FACTS.md P4 | `M4.cop.pull` |
| distort step mode and filter per the probe | documented | help:22.0.492/nodes.zip/cop/distort.txt | `M4.cop.pull` |
| file, rop_image P3 path | locally_tested | docs/FACTS.md P3 | `M4.cop.pull` |
| distort on a per-pixel varying direction field | proposed | P4 tested constant directions only; this row decides | `M4.judge.warp_first_read` |
| cvcops::flowwarp::1.0 (needs an hda_flowwarp names entry) | proposed | BLUEPRINT section 8, M4 row | `M4.cop.flowwarp-decision` |
| opencl kernel pulling @source.imageSample(@P + flow) | proposed | docs:vex/ocl.md documents imageSample; the kernel is not | `M4.cop.flowwarp-decision` |
| timeshift mode = Custom, frame | documented | help:22.0.492/nodes.zip/cop/timeshift.txt, #id mode, frame | `M4.cop.carry-example` |
| timeshift on the asset's flow output cooking the asset at the shifted frame | proposed | untested; acceptance step 1 | `M4.cop.carry-example` |
| switch input indexed by key - $F | documented | help:22.0.492/nodes.zip/cop/switch.txt, #id input | `M4.cop.carry-example` |
| blend mode = Over | documented | help:22.0.492/nodes.zip/cop/blend.txt, #id mode | `M4.cop.carry-example` |
| distort parm scale | locally_tested | FACTS P4: Scale -1 is the pull direction, not a second conversion | `M4.judge.review` |
| visualizevelocity method menu tokens | proposed | read off 22.0.492 by the M3 probe | `M4.judge.close` |

## Support (proposal)

Serial. Every build and proof runs in hython, and the writes chain through bake_once.py, cvcops_houdini/pull.py, build_scene.py and make_frames.py. Only read-only help applies.

*Read-only subagents.*

- Distort step-mode, filter, edge-handling and Time Shift token lookups before M4.cop.probe-distort and M4.cop.carry-example
- M4.judge.review: the one reviewer pass, with the promise-drift checks

*Worktree lanes.* None.

*Serial points.*

- M4.judge.rung2_baseline -> M4.plan (Joe's OK) -> probe-distort -> pull -> warp_first_read -> flowwarp-decision (Joe only if the numbers miss) -> carry-example -> M4.gate.look -> review -> close
- M4.gate.look: Joe's GUI holds the licence
- M4.judge.close writes STATE last; Joe commits

## Contracts this mission makes or keeps

| From | To | Contract |
| --- | --- | --- |
| `M3.hom.bake` | `M4.cop.pull` | cvcops_houdini.bake.bake(node) is the one bake callable, the same one the button runs. It writes $cache/bake.json last and returns the phase wall times. M4 and the release bake only through it. |
| `M3.cop.convert` | `M4.cop.pull` | The asset's Flow output is in Houdini image units (v up, half the longer side per unit), so Distort at Scale -1 pulls with no second conversion. The internal node names (source_in, prep, downscale, export, load, convert, out) are stable. |
| `M3.judge.build_selftest` | `M4.cop.pull` | test_houdini_entry_points.py discovers every \_\_main\_\_ script under houdini/build, houdini/tests and houdini/examples, and requires exit 3 without hou within 10 s. M4's and the release's scripts are covered with no change to the test, as long as each keeps the hou check at the top of main(). |
| `M3.cop.example` | `M4.cop.carry-example` | examples/two_region/make_frames.py and houdini/examples/build_scene.py, with modes and example_network(parent, frames_dir) and frames 1001-1025 at 1920x1080. M4 adds the carry mode and the release adds the plate mode. |
| `M3.judge.close` | `M4.judge.rung2_baseline` | M3's passing rung 2 gives the mean wall time per hython bake call, projected onto M4's 19 calls under check.py's 3600 s, before M4 starts. |
| `M4.cop.pull` | `REL.cop.plate-review` | pull_network(parent, b, flow, settings) in cvcops_houdini/pull.py, with the probe's step mode. M4 also reports to the release's README nodes whether native Distort passed or Flow Warp was built, and the step cap for large motions. |

## Joe's asks

**7. M3 close, DEC verdict and M4 start (one sitting)**

- Review and commit Mission 3
- Read the DEC.quarter verdict and choose whether to open ME or M6 now (default: not before v0.1, OD-22)
- Add M4 to mission.txt, lock and commit 'Start M4' (M4.gate.start)
- Pick the M4 example's fix, key frame, span and colour up front (OD-21)

**8. M4 plan pause (after the M4 baseline)**

- OK the M4 plan and its new files (M4.plan)

**9. M4, only if Distort misses 1.5 levels**

- Decide whether to build Flow Warp as a new node and add its names entry (M4.cop.flowwarp-decision, OD-20)

**10. M4 look**

- Look at the carry render and confirm or change the look (M4.gate.look); close Houdini afterwards

**11. M4 close and release plan (one sitting)**

- Review and commit Mission 4
- OK the release plan, decision 0005 and the new files; consent to the release/v0.1.0 candidate branch and the fresh clone (REL.release.plan, OD-23, OD-26)
- Confirm the packages-folder path the lookup found and the stamp rebuild rule (OD-24)
- Confirm v0.1 ships with no licence file, and say what happens to decision 0001's licence item (OD-29)
- Supply the plate: pattern, range, colour space, what may be quoted, and the defect policy (REL.gate.plate, OD-25)
