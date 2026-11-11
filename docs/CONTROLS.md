# Controls

The flow asset's parameters come from one file, `houdini/build/controls.json`. Mission 3's builder reads it, and
`tests/unit/test_controls.py` fails if it drifts from the worker's command line, the contract or the receipt
schema. To add or change a control, edit that file. Never edit the built asset.

## What the artist sees

**Two inputs, two outputs, four folders.** The node takes a source image and gives back `flow` as a UV layer and
`valid` as Mono. Everything else is a parameter.

| Folder | Control | What it does | Default |
| --- | --- | --- | --- |
| Analysis | Luminance Weights | How red, green and blue are weighed into the grey analysis image | Rec. 709 |
| Analysis | Gain | Multiplies the image before it is quantised to 8 bits | 1.0 |
| Analysis | Gamma | Scene-linear plates usually want 2.2 with a gain, or they clip (FACTS M15) | 1.0 |
| Analysis | Analysis Scale | 1.0, 0.5 or 0.25. Half scale is about 3.3x faster for about 0.08 px more error (FACTS M18) | 1.0 |
| Flow | Recipe | The named flow recipe, from `contract.RECIPES` | `dis_medium` |
| Flow | Backend | `cpu`, `opencl` or `cuda`. An unavailable one is an error, never a quiet substitute | `cpu` |
| Flow | Validity Tolerance | Pixels of forward-backward disagreement allowed (FACTS M14) | 1.0 |
| Bake | Frame Range | First and last frame; the export writes one extra frame | `$FSTART` to `$FEND-1`, so the last baked frame has a successor |
| Bake | Cache Folder | Holds the analysis frames, the flow files and the receipts | `$HIP/cvcops/$OS` |
| Bake | Bake | Exports, runs the worker once for the range, loads the result | Button |
| Bake | Check Cache | Asks the worker which frames are fresh, stale or missing | Button |
| Status | Cache | Fresh, stale and missing counts. Missing is an error; stale is a warning | Read-only |
| Status | What Ran | Recipe, backend and OpenCV version from the newest receipt | Read-only |
| Status | Analysis Encoding | Clipped share and grey levels; warns above 5% clipped or below 32 levels | Read-only |

The defaults for Recipe, Backend and Validity Tolerance are the worker's own, and the test holds them equal. The
other defaults are proposals. Joe confirms them, and every label, in Mission 3, because looks are his gate.

## Proven buildable

**Houdini 22.0.492 builds all 14 of these from the file** (FACTS K21). The dry run makes each control on a
throwaway node and reads it back: name, folder, default and menu items.

```bash
uv run python probes/hython.py evidence/controls_dryrun.py
```

The dry run covers parameters only. The two inputs, the two outputs and the Bake button's behaviour arrive with
Mission 3, which also takes Joe's word on every label and default.

## Rules

1. **One source.** The builder makes parameters from `controls.json` and from nowhere else.
2. **The node and the worker agree.** Every option of `cvcops flow` has a control, and every control that names
   an option names a real one with the same default and choices.
3. **Menus come from the contract.** Recipe and Backend list `contract.RECIPES` and `contract.BACKENDS`, so a new
   recipe appears on the node when it enters the contract, not before.
4. **Status is read, never typed.** The Status folder shows what `verify` and the newest receipt say.
5. **No control changes the stored convention.** Scale, sign and units are applied once, in the conversion node.
6. **A control that changes nothing is noise.** Each one maps to a prep step, a worker option, an action or a
   receipt field, and the test checks that it does.
7. **Analysis values reach the receipt through the sidecar.** Luminance Weights, Gain, Gamma and Analysis Scale
   are not worker options: the export writes them to `analysis.json` beside the frames
   (`cvcops.analysis_sidecar.v1`, decision 0004), and the worker copies them into each receipt.

## Planned, not built

These are in the file with `"status": "planned"`, so the builder skips them until their mission.

| Control | Waits for |
| --- | --- |
| Mask input | A `--mask` option on the worker. A SAM2 mask from Neural Layer to Mask fits here (`docs/ML_AND_AI.md`). |
| Backward Flow output | The backward layer (`docs/OPPORTUNITIES.md`). |
| Live toggle | Mission 5, if its entry gate passes. |
