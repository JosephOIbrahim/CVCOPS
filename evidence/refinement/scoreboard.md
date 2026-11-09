# Refinement scoreboard

Each pass: fix the reviewer's defects in the current best, run the hard gates, then a fresh reviewer scores the
current best and the candidate blind (labels randomised). The candidate replaces the best only if the gates pass
and the reviewer prefers it. Scores out of 50; different reviewers calibrate differently, so compare within a pass.

| Pass | Compared | Gates | Reviewer scores (old / new) | Winner | Main fixes |
| --- | --- | --- | --- | --- | --- |
| 0 | v0 alone | pass | 37 | baseline | |
| 1 | v0 vs v1 | pass | 26 / 39 | v1 | Judge lock and BLOCKED escape; validity, M3, M4 thresholds; cache key; probe fallbacks; ME entry gate; dev suite that rejects the holdout's failures; sweep before search |
| 2 | v1 vs v2 | pass | 33 / 40 | v2 | Warp test pulls B onto A with the forward flow (re-measured); M3 thresholds measured per scale; BLOCKED needs the owner to clear; MU works in a separate clone; evolve runs in the background with a total cap |
| 3 | v2 vs v3 | pass | 36 / 40 | v3 | Agent cannot re-lock its own judge (deny rule plus committed-lock check); M6 can close on "keep CPU"; evolve promotion separated from the 20% backend rule; local model off the timing machine; tiers defined |
| 4 | v3 vs v4 | pass | 36 / 39 | v4 | Thresholds tagged by mission with bound tests; a bake receipt defines the 20% and quarter gates; GPU-first gets a provisional verdict; M0 lock order; Houdini site-packages guarded |
| 5 | v4 vs v5 | pass | 36 / 40 | v5 | Every threshold test written and locked once in M0, so later missions need no mid-session lock; permission rules before the lock; P1 records site-packages; GPU-first verdict path; "a quarter of what" defined |
| 6 | v5 vs v6 | pass | 37 / 41 | v6 | `check.py` learns the current mission from `mission.txt`; locked tests, `check.py` and `lock_judge.py` under `ask` rules and the hash lock; every threshold tagged by mission; ME closes on one command |

Final: v6 with pass 6's five defects fixed. `mission.txt` lists the missions to run and the owner re-locks at each
mission start; M6 scores DIS on OpenCL before asking about a CUDA build; M1 closes on its own thresholds; the M3
receipt records a median total, which is the denominator of the quarter gate; `promote.py` refuses to run until
`test_gaming.py` passes and `sweep.py` has run. These edits passed the hard gates but no reviewer scored them.

## After the six passes (9 November)

| Step | What happened | Evidence |
| --- | --- | --- |
| First-principles review (v7) | Each session walked by hand; two unmeetable validity rows, a Stop hook that failed open, and slipping Windows rules found and fixed; settings, lock tool and launcher shipped as files | `gates.py` PASS at 5,875 words |
| Independent review of v7 | A fresh reviewer scored it 38 of 50. Two high findings: the launcher never checked `mission.txt`, and the tests' seam was unnamed, so M3 and M4 tests would be locked unrun | Its report, applied in v8 |
| Workstation cross-reference (v8) | The Houdini AI reference on E: (SideFX 22.0.429 docs, 4 Oct) and the OpenCV 5.1 prep project read through computer use. One premise changed (OpenFX), P1 and P3 to P5 made concrete, M6 now starts from the prep toolchain | `gates.py` PASS at 5,871 words; `test_gates.py`, the reference with its faults, and the hook, lock and launcher cases all pass |

v8 was not re-scored by a blind reviewer. The next information worth having comes from Mission 0 on the workstation, not from another pass on the document.
