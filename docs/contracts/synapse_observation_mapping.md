# From a CVCOPs receipt to a SYNAPSE observation

**SYNAPSE's adapter builds one `synapse.vision.observation.v1` message per frame pair from that pair's receipt.**
The message shape is the one proposed in SYNAPSE's vision roadmap of 6 November; it is a proposal there, and this
map follows it until SYNAPSE fixes its own. The adapter lives in SYNAPSE (decision 0001). Fields the receipt
cannot fill stay null: neither side guesses.

| Observation field | From the receipt | Note |
| --- | --- | --- |
| `schema` | none | The adapter writes `synapse.vision.observation.v1` |
| `session_id`, `sequence` | none | SYNAPSE's own |
| `frame_id` | `cache_key` and `frame.a` | Stable: the same inputs, parameters and build give the same id |
| `source.kind` | none | `approved_existing_image`: baked frames on disk, not a capture |
| `source.path` | `inputs.a.path` | Frame B is `inputs.b.path` |
| `capture.timestamp`, `capture.clock` | none | Null: files were not captured from a screen |
| `capture.received_utc` | `created_utc` | When the receipt was written |
| `scene.timeline_frame` | `frame.a` | |
| `scene.revision`, `scene.camera_path` | none | Null unless SYNAPSE knows them from the scene |
| `view.*` | none | Null: no viewport was involved |
| `image.width`, `image.height` | `image.width`, `image.height` | Analysis resolution; `analysis.scale` relates it to the plate |
| `image.channels` | none | `grey`: the analysis image is one channel |
| `image.color_space` | `analysis.color_space` | Null means unknown, and the roadmap asks for exactly that |
| `state.synchronized` | none | True: both frames came from files the receipt hashed |
| `state.completion` | `status` | `ok` or `error` |
| `state.stale` | `verify` | True when `verify` reports the pair stale |
| `analysis.build_id` | `cv2.version`, `cv2.build_sha256`, `backend.ran` | Which OpenCV build ran, and where |
| `analysis.model_id` | `recipe.name`, `recipe.source_sha256` | Which recipe ran, by name and source hash |
| `analysis.findings` | `summary`, `analysis.warnings`, `output.path` | Motion and validity numbers to rank frames by, and the flow file as evidence |

What a receipt adds that the observation has no slot for, such as timings and threads, stays in the receipt. An
adapter links to it rather than copying it.
