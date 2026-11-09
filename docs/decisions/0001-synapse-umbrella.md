# 0001. CVCOPs joins SYNAPSE as its perception engine, and SYNAPSE depends on it

Status: accepted, 9 November 2026. Joe set the direction ("fold it in under SYNAPSE"); this record adds the
dependency rule and the order of the fold.

## Decision

**One engine, three ways in, and the arrows point toward the engine.** CVCOPs stays a standalone package with a
versioned contract. Artists reach it through a Houdini asset, pipelines through a command line, and SYNAPSE
through a capability manifest. CVCOPs never imports SYNAPSE. SYNAPSE's adapter lives in SYNAPSE's repository and
is written against the manifest and the receipt schema.

The fold happens in two steps. Now, at the contract: the manifest, the receipt schema and a field-by-field map
onto SYNAPSE's proposed observation message ship with this kit. Later, at the code: once the checklist at the end
of this record is met, the repository can move under SYNAPSE's name with its package name and contract unchanged.

## Why

SYNAPSE's own vision roadmap of 6 November (`E:\OpenCV5.1_Prep\03_SYNAPSE_Houdini\SYNAPSE_Houdini_Roadmap.md`)
draws the same boundary this blueprint reached on its own: an isolated OpenCV worker outside Houdini, its NumPy
and GPU runtime kept out of Houdini's Python, reached through a versioned local protocol. Two designs that met
at the same line are a good sign the line is right. FACTS X6 records what the roadmap says.

The first question that roadmap asks of a useful version is "what changed, where is it visible, and which frames
deserve attention?" The flow node answers half of it already. Pulling frame B onto A's grid with the forward
flow, which Mission 4 tests, leaves a residual: whatever the motion cannot explain. Ranking frames by that
residual finds pops and flicker. So the first operation SYNAPSE needs is one small step past v0.1.

The dependency has to point one way for three reasons:

| Reason | What breaks if the arrow points the other way |
| --- | --- |
| Artists install the node alone | A compositor would need an agent substrate to get optical flow |
| The judge runs anywhere | Rung-1 tests would need a SYNAPSE session, and the sandbox could not run them |
| SYNAPSE is moving toward 2.0 | Every SYNAPSE refactor would put the flow node's release at risk |

## Rules both sides keep

These come from SYNAPSE's safety rules as Joe describes them (atomic calls, check before you change, undo groups
for compound edits) and from the roadmap's authority section.

1. **One call, one operation, declared effects.** Each operation in the manifest states what it reads, that it
   writes only inside the output folder it is given, and that it touches no Houdini scene.
2. **Check before you change.** `verify` reports fresh, stale or missing from the receipts and cache key. An
   agent calls it first and skips work that is fresh. This is SYNAPSE's idempotent guard, with no extra code.
3. **The engine observes; it never edits a scene.** Building or changing a Houdini network stays with SYNAPSE's
   action layer and its undo groups, or with the artist.
4. **Unknown stays unknown.** A receipt field the engine cannot measure is absent or null, never guessed. The
   roadmap asks the same of its observation message.
5. **Budgets are SYNAPSE's to set when it runs the engine live.** The roadmap proposes at most 1 GiB of extra GPU
   memory for vision work, and less than 5% render-time and 10% viewport-frame-time regression. Those become
   Mission 6's limits if SYNAPSE drives the GPU lane.

## What ships now

| File | What it is |
| --- | --- |
| `src/cvcops/capabilities.json` | The manifest: every operation, its status, how to call it, its inputs, outputs, effects and guard |
| `docs/contracts/capabilities.schema.json` | The schema that manifest must satisfy, checked by a unit test |
| `docs/contracts/receipt.schema.json` | What every `flow.####.json` receipt contains |
| `docs/contracts/synapse_observation_mapping.md` | Where each receipt field lands in `synapse.vision.observation.v1` |
| `python -m cvcops capabilities` | Prints the manifest, so an adapter reads it from the installed engine, not from a copy |

## Fold-in checklist

The repository moves under SYNAPSE only when all of these hold.

- [ ] CVCOPs v0.1 has passed its release gate.
- [ ] SYNAPSE's tool interface has been read, and its adapter calls `flow` and `verify` through the manifest.
- [ ] An adapter test in SYNAPSE passes against a pinned CVCOPs version.
- [ ] The licence for CVCOPs is chosen and compatible with how SYNAPSE is released.
- [x] The asset namespace in `0002-names-and-namespace.md` is settled: `cvcops::`, chosen 9 November 2026.

## Alternatives considered

| Option | Why not |
| --- | --- |
| Build the node inside SYNAPSE now | Couples an artist tool to SYNAPSE's beta and 2.0 work, and makes the judge need SYNAPSE to run |
| Keep CVCOPs unaware of SYNAPSE | Two perception stacks and two CUDA builds on one workstation, and SYNAPSE's first question goes unanswered |
| SYNAPSE imports the engine as a library in its own process | Both the roadmap and the blueprint keep OpenCV, its NumPy and its GPU runtime out of Houdini's process |

## Consequences

Good: artists install one package file; SYNAPSE gets tested perception without loading OpenCV; one CUDA build
serves both (Mission 6 already starts from the OpenCV 5.1 prep toolchain).

Costs: the manifest and receipt schema are promises, so changing them means a new version and a note in
`docs/STATE.md`. SYNAPSE's real tool interface has not been read, so the adapter's shape is assumed (FACTS A14)
until someone writes it.
