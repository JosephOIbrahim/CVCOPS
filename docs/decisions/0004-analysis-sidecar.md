# 0004. How the prep values, the request and the build reach the receipt and the cache key

Status: accepted, 11 November 2026, by Joe at the Mission 2 plan pause, with every default for OD-03 to OD-11.

## Decision

**The worker learns Houdini's prep values from a sidecar file, never from new flags. Everything the worker can
measure, it measures; everything it cannot, it records as null.**

| | Rule |
| --- | --- |
| (a) Sidecar | `<prefix>.json` beside `<prefix>.####.exr` (for `bake/analysis.####.exr`, `bake/analysis.json`). Its own schema id, `cvcops.analysis_sidecar.v1`, never the receipt's. It may set only `analysis.luminance_weights`, `analysis.gain`, `analysis.gamma`, `analysis.scale`, `analysis.color_space` and `frame.fps`. The worker finds it from `--in`. A measured field (`clipped_share`, `grey_levels`, `warnings`, `image`), an unknown key, another schema id or malformed JSON is a `ContractError`. |
| (b) No new flow option | No flag, no `controls.json` entry, no `test_controls.py` line, no manifest `argv` change for the prep values. Rejected: new flags (`test_every_flow_option_has_a_control` would demand `maps_to.cli`, and `analysis_scale`'s string choices collide), and EXR header attributes (ROP Image's metadata export is untested on 22.0.492, its key names are unknown, and parsing it would tie the worker to ROP Image). |
| (c) No sidecar | `scale` 1.0, meaning "the analysis image is the source as given"; weights, gain, gamma, color_space and fps null. |
| (d) Errors and backends (OD-04) | A preflight failure writes nothing: a missing or unreadable input, a bad argument, a refused backend. `cuda` with no CUDA device and `opencl` with no usable device exit 3. `opencl` with a device present exits 1, naming Mission 6. A `cpu` run calls `cv2.ocl.setUseOpenCL(False)`. A failure after both frames are hashed and read writes a `status: error` receipt, removes that pair's old flow file, and the run goes on and exits 1. |
| (e) Key and identity (OD-06) | `cv2.build_sha256` is the SHA-256 of `cv2.getBuildInformation()` with line endings normalised. `params.values` holds `tolerance_px`, `mask: false` and the LF-normalised source hashes of `read_analysis_exr`, `estimate_flow` and `validity`. The engine version is not in the key. Weights, gain, gamma and scale change the analysis image and so its digest; fps alone does not, so the sidecar is not in the key. `clipped_share` and `grey_levels` take the worse of A and B. Paths are absolute, with forward slashes. |
| (f) Timings (OD-07) | `timings_s` keys `read`, `hash`, `flow` (forward DIS), `validity` (backward DIS plus the check), `write`, `total`. Flow compute = flow + validity; worker I/O = read + hash + write. |
| (g) verify (OD-05) | Optional `--recipe`, `--backend`, `--tolerance`; unset means "as the receipt recorded". `--json` prints `{frames, counts {fresh, stale, missing}, pairs [{a, b, state, reason}]}`. Exit 0 when every pair is fresh, 1 otherwise, 3 for a broken environment. It writes nothing. |
| (h) Progress (OD-09) | One line per pair on stdout, flushed as it is printed; reasons on stderr. |
| (i) jsonschema (OD-08) | Dev-only. The worker checks the receipt's shape by hand; the tests validate against the locked schema. No new file under `docs/contracts` before v0.1; the sidecar and verify shapes live here and in `docs/ARCHITECTURE.md`. |
| (j) Field split | M2 fills every required receipt field without Houdini. Only M3's export fills weights, gain, gamma, a scale other than 1.0 and fps, through the sidecar. `color_space` stays null in v0.1. |
| (k) Reader (OD-10) | `read_analysis_exr` sets alpha aside (`A`, `*.A`, `*.a`), then takes exactly one channel of any name, or a bit-equal R, G, B trio, bare or under one common layer prefix in either case; FLOAT or HALF; a data window strictly containing the display window is cropped and reported. It returns `np.clip(np.rint(x * 255), 0, 255)` as uint8. Refused, naming the channels: unequal R, G, B; two or more unrelated channels; UINT; NaN or infinity; a data window not covering the display window; a multi-part file. |
| (l) Replace on Windows (OD-11) | `os.replace` is retried for about a second on `PermissionError` (a File COP holding the file), then the pair fails with an error receipt naming the lock. Temp names start with a dot and never match `flow.####.exr` or `flow.####.json`. |

The sidecar shape, `cvcops.analysis_sidecar.v1`:

```json
{"schema": "cvcops.analysis_sidecar.v1",
 "analysis": {"luminance_weights": [0.2126, 0.7152, 0.0722], "gain": 1.0, "gamma": 2.2, "scale": 0.5, "color_space": null},
 "frame": {"fps": 24.0}}
```

Every key below `schema` is optional; a missing one takes the no-sidecar value from (c).

## Why

The receipt schema requires `analysis.scale` and allows the other prep values, but only Houdini knows them. A flag
per value would drag each one through `controls.json`, its test and the manifest, and `analysis_scale` is a menu of
strings the worker would have to parse. A file the export writes beside the frames keeps the worker's command line
as it is and lets M3 fill it without reopening M2. The cache key already sees every value that changes pixels,
through the frame digests, so the sidecar can stay out of it.

## Consequences

- M3's export writes `analysis.json` beside the frames; until then every receipt says scale 1.0 and null prep values.
- The release's distribution record becomes decision 0005.
- Changing the reader, the flow recipe or the validity code changes every cache key, because their source hashes
  are in it. That is deliberate: a cached result made by different code is stale.
