# Motion opportunities

Seventeen uses sit on top of the same two layers, `flow` and `valid`. This page says where each one stands and
what comes first. The register is `docs/opportunities.json`; `tests/unit/test_opportunities.py` keeps it well
formed and tied to the capability manifest. Zones are judgment, not measurement.

**Nothing here enters a mission until its rows are in the blueprint's threshold table and locked** (decision
0003). v0.1 ships first.

## The pick: the temporal check

**Build the temporal check first once v0.1 ships.** It reuses the pull that Mission 4 tests, it answers
SYNAPSE's first question (which frames deserve attention), and the generative-video and denoiser checks run on
the same machinery.

| Part | Definition |
| --- | --- |
| Pair residual | Mean absolute difference, in 8-bit levels, between frame A and frame B pulled onto A's grid, on valid pixels only |
| Frame score | The smaller of a frame's two neighbour residuals. A pop disagrees with both neighbours; a hard cut disagrees with one |
| Output | Frames ranked by score, as a report beside the receipts. The engine still writes only inside its output folder |
| Reference | `uv run python evidence/opportunities_reference.py`: two planted problems in 16 frames score 2.52 and 9.96 against a median of 0.66 |
| Signatures | `src/cvcops/ops/temporal.py`, as stubs |
| Not yet tested | A hard cut, real footage, and how small a pop it can find |

## Start here

| Use | Home | Stands | First step |
| --- | --- | --- | --- |
| Temporal check | Engine | Next after v0.1 | Draw rows from fresh sequences, lock them, then write the operation |
| Carry a fix across frames | Houdini | v0.1, toward earlier frames | Mission 4's example. Carrying toward later frames needs the backward layer |
| Generative-video check | Outside | Idea, untested | The temporal check on one generated clip and one filmed clip |
| Denoiser boil check | Houdini | Idea, untested | The temporal check on a denoised sequence and its noisy source |

Carrying a fix has a direction. Mission 4 pulls a later frame onto an earlier one with the forward flow, so a
fix painted on a late key frame travels back to earlier frames in v0.1. Travelling forward needs the flow from
each frame back to the key, which is the backward layer.

## Quick wins

| Use | Home | Stands | First step |
| --- | --- | --- | --- |
| See motion on unrendered footage | Houdini | v0.1, Mission 3 | The example scene feeds flow to Visualize Velocity |
| Particles from motion | Houdini | v0.1 data; the SOP pairing is untested | Read the flow layer in SOPs and emit above a threshold |
| Backward flow as a layer | Engine | Parked | Write it as a second file, with a row against the reversed pair |
| Stillest frame of a burst | Outside | Idea, untested | Median flow inside the subject per pair; the lowest wins |

## Worth the climb

| Use | Home | Stands | First step |
| --- | --- | --- | --- |
| Motion matte | Engine | Parked | A new operation with its own contract: MOG2 or KNN |
| Feature tracks into SOPs | Engine | Parked | A new operation: KLT points with ids |
| Stabilise and match | Engine | Parked | A new operation: ECC to transform parameters |
| Relight that holds still | Outside | Idea, untested | The temporal check on a relit sequence against its plate |
| Motion as a guide for video models | Outside | Idea, untested | Find out what one model accepts |

## Later, maybe

| Use | Home | Stands | First step |
| --- | --- | --- | --- |
| Receipts on the USD stage | Outside | Idea | A writer from receipts to a small USD layer |
| Vector motion blur | Houdini | Idea | A blur along the flow layer, as an OpenCL COP |
| In-betweens for a retime | Houdini | Idea | A two-sided warp, mixed by validity; needs the backward layer |
| Motion-aware sampling | Outside | Idea | Needs a hook into the renderer |

## How an opportunity becomes a mission

1. Joe picks it and says so in `docs/STATE.md`.
2. Its reference goes into `evidence/`, the way `opportunities_reference.py` holds three of them today.
3. Its rows are drawn from fresh fixtures, added to the blueprint's threshold table and to `tests/thresholds/`.
4. Joe adds the mission to `mission.txt` and locks.
5. One session builds it against the locked rows. A new engine operation flips from `parked` to `planned` to
   `available` in `src/cvcops/capabilities.json` as it goes.
