# ML and AI in CVCOPs

ML and AI touch CVCOPs in two places. ML can do the measuring, as a flow recipe or as an input layer. AI agents
can drive the engine and build it. Both come in under the contract and the judge that already exist.

**Nothing here is built, and none of it starts before v0.1 ships** (decision 0003). Each lane has an entry gate
and a first probe.

## Rules that carry over

1. **One contract.** A neural recipe writes the same flow file and the same receipt. `recipe.name` carries the
   model's name and `recipe.source_sha256` the model file's hash.
2. **One judge.** A neural recipe passes the same threshold rows as stock DIS, and is promoted by the holdout
   rule in the blueprint's section 7. More accurate but slower enters as a named choice, not as the default.
3. **No network at run time.** The manifest's schema fixes `effects.network` to `none`. Weights are local files
   the user places. The engine never downloads one.
4. **Nothing is silent.** A missing model or an unavailable device is an error, never a quiet switch to DIS.
5. **A licence gate.** No weight file enters the repository. Before a model is first used, its code licence and
   the terms on its weights and training data go into `docs/FACTS.md`, and Joe decides.
6. **A budget.** Each pair's time goes in the receipt, as it does today. Peak GPU memory joins it as a field
   that may be null. SYNAPSE sets the budgets (decision 0001).

## ML lanes

| Lane | What it is | Where it runs | Judged by | Entry gate |
| --- | --- | --- | --- | --- |
| ML1 Mask input | A native ML mask, such as SAM2 from Neural Layer to Mask, feeds the planned Mask input, so validity is off outside the subject | Houdini makes the mask; the worker reads it | A new row: masked pixels are invalid, the rest unchanged | v0.1 shipped. Needs a `--mask` option and no new model |
| ML2 Neural flow in the worker | A learned flow model as a recipe, through ONNX Runtime | The worker, beside OpenCV | The Mission 1 rows and the holdout rule | v0.1 shipped, probes PM3 and PM4 passed, and Joe's OK for the new dependency |
| ML3 Neural flow in the graph | The same kind of model through the native ONNX Inference COP, with no bake and no OpenCV | Copernicus, on the GPU | The Mission 3 rows, through the same conversion node | Probes PM1 and PM2 passed |
| ML4 Learned confidence | A confidence value in place of the valid flag | Either home | New rows; this is a contract change, so `flow-contract-v2` | Parked. The flag is measured and honest today (FACTS M14) |

ML1 is the cheap one: Houdini 22 already ships the models (FACTS H3), and the worker only has to read one more
file. ML2 and ML3 are the same idea in two homes. ML3 is the live one, and it depends on what the ONNX
Inference COP accepts, which nobody has tested here.

## AI lanes

| Lane | What it is | Stands |
| --- | --- | --- |
| AI1 SYNAPSE drives the engine | SYNAPSE registers tools from `cvcops capabilities`, calls `verify` before `flow`, reads receipts | Contract shipped; adapter waits on decision 0001's checklist and on reading SYNAPSE's tool interface (FACTS A14) |
| AI2 Search for better recipes | OpenEvolve mutates the flow recipe against the evolve judge | Evaluator built and proven; no run made (blueprint, section 7) |
| AI3 Claude Code builds it | One mission per session against a judge it cannot loosen | `GOALS.md` holds the goal line for each session |
| AI4 Checks on AI-made pictures | The temporal check on generated video, denoised renders and relit plates | Ideas in `docs/OPPORTUNITIES.md`; they wait on the temporal check |
| AI5 Motion out to video models | The flow layer as guidance for a model that accepts it | Idea; depends on each model |

## Probes, before any ML code

| Probe | Question | If it fails |
| --- | --- | --- |
| PM1 ONNX Inference COP | Does it load a two-image flow model? Which device does it use, how long does a 1080p pair take, and how much GPU memory? | ML3 stays parked; ML2 is the route |
| PM2 Mapping | Does the model's output map onto the flow contract through the conversion node, on Mission 3's two-region fixture? | The model needs its own conversion, recorded as a recipe detail |
| PM3 Licences | For each candidate model: the code licence, and the terms on the weights and the data they were trained on | That model is not used |
| PM4 ONNX Runtime | Is there a wheel for CPython 3.13 on Windows, and which execution providers does it offer on the RTX 4090? | ML2 waits |

Candidates for ML2 and ML3 are learned flow models with public ONNX exports, such as RAFT and SEA-RAFT. Their
licences and the terms on their training data are **not verified here**. PM3 settles that before anything is
downloaded.

## What this changes today

Nothing in the v0.1 judge. The controls file carries the planned Mask input, the opportunity register marks the
uses that involve ML, and `docs/FACTS.md` lists the four probes as assumptions A16 to A19.
