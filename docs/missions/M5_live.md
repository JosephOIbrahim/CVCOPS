# Mission M5: the live lane

A proposal, written 2026-11-11 at Joe's request, not adopted. The blueprint's M5 row governs; this brief adds the order,
the files and the checks. Graph and conventions: `docs/missions/GRAPH.md`.

**Goal.** Make the flow cook inside Copernicus, frame by frame, so an artist can scrub the result instead of waiting for
a bake. The recipe does not change: the same `dis_medium` on the same analysis image, reached by whichever mechanism the
entry gate proves can carry a second frame into the cook. If no mechanism passes, M5 does not open and the asset's
planned `live` toggle stays planned.

**Entry.** M4 is closed and committed. P2 and P5 have passed, or a two-input OpenFX node cooks with frame B fed through
Time Shift (BLUEPRINT's M5 row). The committed `tests/thresholds/mission.txt` lists M5. If any of that is missing, write
`WAITING:` and stop.

**Done when.** `uv run python tools/check.py --houdini` passes the `live_cook` row beside the M3 and M4 rows, Joe has
scrubbed the example in Houdini and judged it, and `docs/STATE.md` holds the closing commands and their tails.

**Tier.** Heavy. Not unattended: the look is Joe's, and whether the `live` control ships at v0.1 is his call.

## What this brief assumes, and what it does not

- **It assumes no M5 node names exist.** None do: `docs/missions/` holds M2, M3, M4, M6 and the release, and no `M5.`
  name appears anywhere in the repository. Every node name here is proposed. Rename them freely at the start sitting.
- **It assumes the `live_cook` row does not exist.** It does not: `evidence/thresholds_reference.py` holds eleven keys
  and none is live. Adding a row is a judge change, so Joe adds it and locks it in the start sitting, exactly as the
  other rows were added.
- **It assumes P2 and P5 are unproven.** Both are deferred to this gate in `docs/FACTS.md`, and P5's row says it stays
  part of M5's entry gate.

## How the session runs

1. **Read** `CLAUDE.md`, `docs/BLUEPRINT.md`, `docs/FACTS.md`, `docs/STATE.md` and this brief.
2. **Baseline.** Rung 1 passes for M0 to M4. Rung 2 passes with `pull_warp` and both M3 rows. The hython path, size and
   sha256 match M4's baseline.
3. **Pause.** `WAITING:` with the plan, the new files and the row's definition. Stop for Joe's OK.
4. **Entry gate.** Run P2, P5 and the OpenFX route as one probe, each in its own hython call. Record which passed.
5. **Build the live path** in the passing mechanism, with no change to the recipe.
6. **First read.** Grade `live_cook` once. At most 1.5 levels: go on. Above: stop and put the numbers to Joe.
7. **Example.** Scrub the two-region scene with live on; record the cook time per frame.
8. **Look.** Joe scrubs it and closes Houdini after. The reviewer pass runs once the look is recorded.
9. **Close.** Rung 1, rung 2 with four rows, the example's cook-time table, the hython identity, STATE. Joe commits.

Budget: one session. Rung 2 grows to four rows; M4's close quotes the per-call time before this starts.

## The row it has to pass

The blueprint names the proof as "the `--houdini` live test" and does not define it. This brief proposes the definition,
for Joe to accept or change in the start sitting:

| | |
| --- | --- |
| Key | `live_cook` |
| Mission | M5 |
| Rung | 2, hython |
| Question | Does the live cook give the same flow as the bake, on the same frame and the same settings? |
| Metric | Mean absolute difference against the baked `flow.####.exr` for that pair, in 8-bit levels: mean flow mapped to 0 to 255 by the same `uvtorgb` the example renders, compared on the 24 px interior |
| Limit | 1.5 levels, the `pull_warp` limit |
| Second number | Cook wall time per frame at 1920x1080, recorded and reported, with a ceiling Joe sets in the start sitting (a proposal: 2 s) |
| Why a limit is needed | A live path that quietly degrades the answer, or one that takes ten seconds a frame, both fail the artist even though both "work" |

## Tasks

In dependency order. Support names who runs it; "(joe)" or "(hython)" is the resource it holds. Every node name is
proposed.

| # | Node | Task | Writes | Proves | Support |
| --- | --- | --- | --- | --- | --- |
| 1 | `M5.gate.start` | Joe adds M5 and the `live_cook` row, locks, commits 'Start M5' | `tests/thresholds/mission.txt`, `tests/thresholds/test_thresholds.py`, `evidence/thresholds_reference.py`, `judge.lock` | git show HEAD:tests/thresholds/mission.txt lists M5; uv run python tools/check.py --list shows live_cook listed as M5 rung 2 | joe (joe): the row is a judge change, so Joe adds it and locks it |
| 2 | `M5.judge.rung2_baseline` | M5 start: rung 1 and rung 2 baseline, the hython identity, the per-call time from M4 | `docs/STATE.md`, `probe_out/m5_baseline.log` | uv run python tools/check.py ends 'CHECK: rung 1 passes for M0, M1, M2, M3, M4, M5 (9 threshold rows)'; uv run python tools/check.py --houdini exits 1 with the three current rows passing and only live_cook failing | hython_serial (hython): rung 2 is now four rows |
| 3 | `M5.plan` | M5 plan: the entry gate's three routes, the new files, the row's definition, then the pause | `docs/STATE.md` | The first line of docs/STATE.md is the pause line carrying the plan; git diff --stat touches only docs/STATE.md | joe (joe): plan first, then pause for Joe's OK |
| 4 | `M5.cop.probe-entry-gate` | P2, P5 and the OpenFX route, one hython call each: does frame B reach the cook, and does a per-frame Python step survive a scrub? | `probes/m5_entry_gate.py`, `docs/FACTS.md` | uv run python probes/hython.py probes/m5_entry_gate.py p2 …; … p5 …; … ofx …, each exiting 0 or 1 with a printed verdict, and FACTS gaining one row per route with the mechanism found | hython_serial (hython): three serial hython calls; the verdict decides everything after it |
| 5 | `M5.cop.live-path` | Wrap the same recipe in the passing route, with the analysis image and the worker unchanged | `houdini/python3.13libs/cvcops_houdini/live.py`, `houdini/build/flow_network.py`, `houdini/build/controls.json` | uv run python probes/hython.py houdini/build/build_hdas.py --out houdini/otls; uv run python probes/hython.py houdini/tests/build_selftest.py: both exit 0, the self-test now covering the live path's controls | hython_serial (hython): the asset rebuilds, so the build stamp changes and M4's receipt no longer matches it |
| 6 | `M5.judge.live-first-read` | First read of live_cook: the decision point between finishing M5 and stopping | `docs/STATE.md`, `probe_out/m5_first.json`, `probe_out/m5_first.log` | CVCOPS_IMPL=houdini CVCOPS_ROWS=live_cook CVCOPS_RESULTS=probe_out/m5_first.json gives a value, recorded in STATE beside 1.5 levels and the ceiling, with the decision | hython_serial (hython): one serial read |
| 7 | `M5.cop.live-example` | The two-region scene scrubbed with live on: cook time per frame and a rendered sample | `houdini/examples/build_scene.py`, `examples/two_region/out/` | uv run python probes/hython.py houdini/examples/build_scene.py live --frames 1001-1024 exits 0 and prints a cook-time table; three sample frames render to EXR in the git-ignored folder | hython_serial (hython): scene build, cook and render in hython |
| 8 | `M5.gate.look` | Joe scrubs the live scene and judges it | `docs/STATE.md` | Joe says so; recorded in STATE | joe (joe): looks are Joe's gate |
| 9 | `M5.judge.review` | M5's one read-only reviewer pass | nothing | One subagent report on git diff <Start M5 commit>..HEAD: gaps with file:line, or 'no correctness gaps'; no cv2 under houdini/, no hou under src/, no judge file touched but the row Joe added | readonly_subagent: the mission's single pass |
| 10 | `M5.judge.close` | M5 closing evidence: four rung-2 rows, the cook-time table, the hython identity, STATE | `docs/STATE.md`, `probe_out/m5_rung2.log`, `probe_out/m5_rows.json`, `probe_out/m5_p1_close.json` | uv run python tools/check.py --houdini ends 'CHECK: rung 2 passes (4 threshold rows; Houdini's Python unchanged since P1)', exit 0; uv run python tools/check.py ends '… for M0, M1, M2, M3, M4, M5 (9 threshold rows)', exit 0; the live example's command exits 0 | hython_serial (hython): rung 2 plus the example plus the values run |
| 11 | `M5.gate.close` | Mission 5 closes | nothing | check.py --houdini exits 0 with live_cook listed and passing; Joe has scrubbed it; STATE holds the entry | main_only: evidence comes from M5.judge.close |

## What each task must show

- **`M5.cop.probe-entry-gate`.** The three routes, each asked the same two questions: can the cook see two frames at
  once, and can a per-frame step run without costing more than the ceiling. P2 asks whether layer buffers can carry frame
  B beside A (`allBufferElements` returns host memory, FACTS H10, and buffer space puts a pixel's origin at its lower-left
  corner, H15). P5 asks whether a Python Snippet COP can run the worker as a child process each cook, given that its
  interpreter clears between cooks unless Maintain State is on (`CLAUDE.md`, FACTS H7) and that `houdini/` may never
  import cv2 (`tests/thresholds/test_guards.py`). The OpenFX route asks whether a two-input plug-in cooks with frame B
  fed through Time Shift; Copernicus loads OpenFX plug-ins from `OFX_PLUGIN_PATH` and lists them under OFX (FACTS H14).
  Exactly one verdict is written, naming the route and its cost.
- **`M5.cop.live-path`.** The route is wrapped, not rebuilt: the same prep kernel, the same Resample Box, the same recipe
  and tolerance. The `live` control in `houdini/build/controls.json` moves from `planned` to `v0.1` **only if Joe says
  so** — that file is the contract's interface, and `tests/unit/test_controls.py` holds it to the worker's options and the
  manifest. If live calls the worker as a child process, it uses `worker.py`'s existing argv builder and scrubbed
  environment, with no new flag and no new dependency.
- **`M5.judge.live-first-read`.** At most 1.5 levels and inside the time ceiling: record 'the live lane passes' and go
  on. Above either: the pause line with both numbers. Nothing is built past this node until Joe answers.
- **`M5.cop.live-example`.** The cook-time table is the deliverable that matters to an artist: per frame, at analysis scale
  1.0 and at 0.5, beside the baked pair time from `docs/facts/m3_bake_receipt.json` (median 21.15 s for 24 pairs, flow
  compute 5.78 s of it). A live path slower than a bake is a finding, not a failure, and it goes in STATE and the README.
- **`M5.judge.review`.** Checks: no cv2 under `houdini/` and no hou under `src/`; the recipe, tolerance, sidecar and
  receipts unchanged; the `live` control's status changed only if STATE says Joe approved it; the row Joe added is the
  only judge change; no dependency added; the asset builds only by script.
- **`M5.judge.close`.** Rung 1 timed; rung 2's wall time quoted against `check.py`'s 3600 s with four rows; the values
  run for four rows beside their limits; `probes/p1_environment.py --record` reports 22.0.492 and the licence and the
  hython identity matches M4's baseline; `--list` shows the new row; `gates.py PASS`. STATE: capsule, one log entry with
  tails, the entry-gate verdict, the first read, Joe's look, the cook-time table.

## Open questions

| ID | Question | Default | Blocks here |
| --- | --- | --- | --- |
| OD-30 | Which route opens M5: P2 layer buffers, P5 Python Snippet, or a two-input OpenFX plug-in? | Whichever passes the probe; if more than one passes, prefer the one that keeps `houdini/` free of cv2 and costs least per frame. If none passes, M5 does not open and STATE says so | `M5.cop.probe-entry-gate`, `M5.cop.live-path` |
| OD-31 | Does the `live` control ship at v0.1, or stay planned? | Stays planned unless M5 closes before the release gate and Joe moves it; promoting it is a `controls.json` change and a contract change | `M5.cop.live-path`, `REL.release.plan` |
| OD-32 | What is the time ceiling per frame for `live_cook`? | 2 s at 1920 by 1080, analysis scale 1.0, proposed; Joe sets it in the start sitting | `M5.judge.live-first-read` |
| OD-33 | Is M5 on v0.1's path or optional after it? | On the path per BLUEPRINT's mission order (M4, M5, M6, release gate), and its entry gate may close it. Joe can move it after v0.1 | `M5.gate.start`, `REL.release.plan` |

## Risks

| Risk | Signal | Response |
| --- | --- | --- |
| No route carries frame B into the cook | All three probe routes fail | M5 does not open; the `live` toggle stays planned; STATE records the three failures with their messages |
| A live cook at 1080p is slower than the bake | The cook-time table, or the first read's time | Report it; the lane is still correct, and the README states the cost. Do not tune the recipe to hide it |
| The Python Snippet interpreter clears between cooks | The first frame is right and the second is not | Maintain State on, or re-establish the child process each cook; the probe measures both |
| cv2 leaks into `houdini/` | `test_guards.py` fails | The live path calls the worker as a process, or uses OpenCL; it never imports cv2 |
| Promoting the `live` control breaks the contract | `tests/unit/test_controls.py` fails | The control stays `planned` unless Joe approves the promotion and the test, manifest and controls move together |
| The asset rebuild stales M4's bake receipt | The build stamp differs from `docs/facts/m3_bake_receipt.json` | Expected: M5 records its own build and does not re-time M4; the release re-times everything it quotes |
| Live cooking holds the licence while a rung-2 run needs it | A licence error in a log | The look gate is ordered last, and nothing runs hython while Joe's GUI is open |

## Houdini names

| Name | Status | Source | Node |
| --- | --- | --- | --- |
| `allBufferElements` returns bytes, `setAllBufferElements` takes them | documented | docs/FACTS.md H10 | `M5.cop.probe-entry-gate` |
| Buffer space: a pixel's origin is its lower-left corner; texture space 0 to 1 | documented | docs/FACTS.md H15 | `M5.cop.probe-entry-gate` |
| Python Snippet COP: kwargs inputs and return dict; clears its interpreter unless Maintain State | documented | docs/FACTS.md H7; CLAUDE.md gotchas | `M5.cop.probe-entry-gate` |
| OpenFX plug-ins load from `OFX_PLUGIN_PATH` and appear under OFX | documented | docs/FACTS.md H14 | `M5.cop.probe-entry-gate` |
| OpenCL COP kernel and bindings | locally_tested | docs/FACTS.md H30, H31 | `M5.cop.live-path` |
| Resample Box at Analysis Scale | locally_tested | docs/FACTS.md H32 | `M5.cop.live-path` |
| Time Shift mode Custom, frame | documented | help:22.0.492/nodes.zip/cop/timeshift.txt | `M5.cop.probe-entry-gate` |
| A Python step inside a cook, per frame, inside the ceiling | proposed | untested; this mission's whole question | `M5.judge.live-first-read` |
| Layer buffers carrying a second frame | proposed | P2 is deferred, not passed | `M5.cop.probe-entry-gate` |
| The `live` control as a v0.1 toggle | proposed | `houdini/build/controls.json` holds it as `planned` | `M5.cop.live-path` |

## Support (proposal)

Serial. Every route needs hython, and the asset rebuilds once.

*Read-only subagents.*

- The P2, P5 and OpenFX token lookups before `M5.cop.probe-entry-gate`
- `M5.judge.review`: the one reviewer pass

*Worktree lanes.* None.

*Serial points.*

- `M5.judge.rung2_baseline` -> `M5.plan` (Joe's OK) -> entry gate -> live path -> first read -> example ->
  `M5.gate.look` -> review -> close
- `M5.gate.look`: Joe's GUI holds the licence
- `M5.judge.close` writes STATE last; Joe commits

## Contracts this mission makes or keeps

| From | To | Contract |
| --- | --- | --- |
| `M3.hom.bake` | `M5.cop.live-path` | The same recipe, tolerance and analysis image the bake uses. A live frame and a baked frame for the same pair must agree within the `live_cook` limit, or the lane is not the same product |
| `M3.cop.convert` | `M5.cop.live-path` | Flow stays in Houdini units from the one conversion node; a live path may not scale or flip a second time |
| `M3.judge.build_selftest` | `M5.cop.live-path` | Every new script keeps the hou check at the top of `main()`, so `test_houdini_entry_points.py` covers it with no change |
| `M4.cop.pull` | `M5.cop.live-path` | `pull_network(parent, b, flow, settings)` is the reusable pull; a live review that shows B pulled onto A reuses it rather than rebuilding the chain |
| `M5.cop.live-path` | `REL.release.limits` | The README's Limits section quotes the cook-time table and the entry gate's verdict. If M5 does not open, the release says the `live` control is planned, not shipped |

## Joe's asks

**12. M5 start (one sitting)**

- Add the `live_cook` row to `tests/thresholds/`, add M5 to `mission.txt`, lock and commit 'Start M5' (`M5.gate.start`)
- Set the per-frame ceiling (OD-32) and say whether the `live` control may ship at v0.1 (OD-31)
- Say whether M5 is on v0.1's path or after it (OD-33)

**13. M5 plan pause (after the baseline)**

- OK the plan, the route preference and the new files (`M5.plan`)

**14. M5, only if the entry gate finds no route**

- Decide whether to close M5 with the three failures recorded, or to open a different route (`M5.cop.probe-entry-gate`, OD-30)

**15. M5 look**

- Scrub the live example and say whether it is fast enough and right enough to ship (`M5.gate.look`); close Houdini after
