"""One timed bake of the two-region example, for the bake receipt (M3.judge.bake_receipt). Runs in hython.

Started by evidence/bake_receipt.py `runs`, one fresh hython per run:

    uv run python evidence/bake_receipt.py runs --n 1 --out examples/two_region/out/timing

which calls `probes/hython.py houdini/tests/bake_timing.py --run <n> --out <out>/run_<n>`. Options (Joe's OK, 11 Nov):

    --source          File COP pattern, relative to the repository   examples/two_region/out/frames/two_region.$F4.exr
    --frames          first-last pair                               1001-1024
    --out             the run's folder; must be empty                (required)
    --recipe          dis_medium        --backend cpu        --colorspace raw
    --gain 1.0        --gamma 1.0       --analysis-scale 1.0
    --run             the run's number                               (required)

It builds houdini/examples/build_scene.py's example_network in memory (nothing is saved), sets the controls, bakes
into <out>/cache through cvcops_houdini.bake.bake (the Bake button's function), then reloads nothing more and cooks
the flow output at every frame of the range (Joe's choice for the load phase). wall_s.total runs from just before the
bake to the last of those cooks (OD-07). It then requires that every pair's receipt was written by this run, that the
asset's build stamp matches houdini/build/stamp.py over the tree, and that cv2 never entered this process, and writes
<out>/run.json (cvcops.bake_run.v1, the shape in evidence/bake_receipt.py) through a temporary name and os.replace.
Every path in run.json is relative to the repository. Exit 0 done, 1 a failure, 3 without hou or the asset.
"""
import argparse
import datetime
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_SCHEMA = "cvcops.bake_run.v1"
TIMING_KEYS = ("read", "hash", "flow", "validity", "write", "total")


def parse_frames(text):
    first, last = (int(v) for v in text.split("-", 1))
    if last < first:
        raise ValueError(f"--frames {text}: the last frame is before the first")
    return first, last


def git_head(root=ROOT):
    """The commit checked out, read from .git without starting git."""
    git = root / ".git"
    head = (git / "HEAD").read_text(encoding="utf-8").strip()
    if not head.startswith("ref: "):
        return head
    ref = head[5:]
    loose = git / ref
    if loose.is_file():
        return loose.read_text(encoding="utf-8").strip()
    for line in (git / "packed-refs").read_text(encoding="utf-8").splitlines():
        if line.endswith(" " + ref):
            return line.split()[0]
    raise LookupError(f"cannot resolve {ref}")


def write_json(path, obj):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".cvcops-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def fail(message, code=1):
    print(f"bake_timing.py: {message}", file=sys.stderr)
    return code


def main():
    try:
        import hou
    except ImportError:
        print("bake_timing.py: no hou; evidence/bake_receipt.py runs it through probes/hython.py", file=sys.stderr)
        return 3
    ap = argparse.ArgumentParser(description="One timed bake of the two-region example.")
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--source", default="examples/two_region/out/frames/two_region.$F4.exr")
    ap.add_argument("--frames", default="1001-1024")
    ap.add_argument("--recipe", default="dis_medium")
    ap.add_argument("--backend", default="cpu")
    ap.add_argument("--colorspace", default="raw")
    ap.add_argument("--gain", type=float, default=1.0)
    ap.add_argument("--gamma", type=float, default=1.0)
    ap.add_argument("--analysis-scale", default="1.0")
    args = ap.parse_args()

    if os.path.isabs(args.source):
        return fail("--source must be relative to the repository, so the receipt holds no absolute path")
    first, last = parse_frames(args.frames)
    out = (ROOT / args.out).resolve() if not os.path.isabs(args.out) else Path(args.out)
    if out.exists() and any(out.iterdir()):
        return fail(f"{args.out} is not empty; each timed run needs a fresh empty folder")
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "cache"

    sys.path.insert(0, str(ROOT / "houdini" / "examples"))
    sys.path.insert(0, str(ROOT / "houdini" / "build"))
    import build_scene
    import stamp as stamp_mod
    from cvcops_houdini import bake as bake_mod

    names = build_scene.names()
    tname = f"{names['hda_namespace']}::{names['hda_flow']}::1.0"
    defn = hou.hda.definitionsInFile(str(ROOT / "houdini" / "otls" / f"{names['hda_namespace']}_{names['hda_flow']}.hda"))
    if hou.nodeType(hou.copNodeTypeCategory(), tname) is None or not defn:
        return fail(f"{tname} is not installed; build it with houdini/build/build_hdas.py", 3)
    stamp_path = ROOT / "houdini" / "otls" / f"{names['hda_namespace']}_{names['hda_flow']}.hda.stamp.json"
    built = json.loads(stamp_path.read_text(encoding="utf-8"))["stamp"]
    tree = stamp_mod.stamp()
    if built != tree:
        return fail(f"the asset was built from another tree (stamp {built[:12]}, tree {tree[:12]}); rebuild it first")

    hou.setFps(24.0)
    hou.setFrame(first)
    pattern = (ROOT / args.source).as_posix()
    try:
        nodes = build_scene.example_network(hou, hou.node("/obj"), pattern, colorspace=args.colorspace, name="timing")
    except LookupError as e:
        return fail(str(e), 3)
    node = nodes["flow"]
    scale_menu = node.parm("analysis_scale").menuItems()
    if args.analysis_scale not in scale_menu:
        return fail(f"--analysis-scale {args.analysis_scale} is not on the menu {list(scale_menu)}")
    for parm, value in (("recipe", args.recipe), ("backend", args.backend), ("gain", args.gain),
                        ("gamma", args.gamma), ("analysis_scale", args.analysis_scale)):
        node.parm(parm).set(value)
    if node.parm("recipe").evalAsString() != args.recipe or node.parm("backend").evalAsString() != args.backend:
        return fail(f"the recipe or backend menu refused {args.recipe!r} / {args.backend!r}")
    node.parmTuple("frange").deleteAllKeyframes()
    node.parmTuple("frange").set((first, last))
    node.parm("cache_dir").set(cache.as_posix())

    started_utc = datetime.datetime.now(datetime.timezone.utc)
    t0 = time.perf_counter()
    try:
        timings = bake_mod.bake(node, names["env_prefix"])
    except bake_mod.BakeError as e:
        return fail(f"the bake failed: {e}", 3 if e.code == 3 else 1)
    t_cooks = time.perf_counter()
    convert = node.node("convert")
    for frame in range(first, last + 1):
        hou.setFrame(frame)
        convert.cook(force=True)
        if convert.errors():
            return fail(f"cooking the flow output at {frame} failed: {convert.errors()}")
    t_end = time.perf_counter()
    hou.setFrame(first)

    if "cv2" in sys.modules:
        return fail("cv2 was imported into hython; houdini/ must never import it")
    with open(cache / "bake.json", encoding="utf-8") as f:
        record = json.load(f)
    progress = record.get("progress", [])
    pairs, receipts = [], []
    for a in range(first, last + 1):
        path = cache / f"flow.{a:04d}.json"
        with open(path, encoding="utf-8") as f:
            r = json.load(f)
        receipts.append(r)
        created = datetime.datetime.fromisoformat(r["created_utc"].replace("Z", "+00:00"))
        computed = created >= started_utc and any(line.startswith(f"flow {a}-{a + 1} ok") for line in progress)
        pairs.append({"a": a, "b": a + 1, "state": "computed" if computed else "skipped",
                      "timings_s": {k: float(r["timings_s"][k]) for k in TIMING_KEYS}})
    skipped = [p["a"] for p in pairs if p["state"] != "computed"]
    first_r = receipts[0]
    if any(r["backend"]["ran"] != args.backend for r in receipts):
        return fail(f"a pair ran on another backend than {args.backend}")

    run = {"schema": RUN_SCHEMA, "run": args.run,
           "workload": {"source": args.source, "size": [first_r["image"]["width"], first_r["image"]["height"]],
                        "frames": [first, last], "pairs": last - first + 1, "analysis_scale": args.analysis_scale,
                        "recipe": args.recipe, "backend": args.backend, "threads": first_r["threads"],
                        "cv2_version": first_r["cv2"]["version"], "cv2_build_sha256": first_r["cv2"]["build_sha256"],
                        "houdini_build": hou.applicationVersionString(),
                        "licence": str(hou.licenseCategory()).rsplit(".", 1)[-1], "build_stamp": built,
                        "git_head": git_head()},
           "wall_s": {"export": timings["export"], "worker": timings["worker"],
                      "load": timings["load"] + (t_end - t_cooks), "total": t_end - t0},
           "pairs": pairs}
    write_json(str(out / "run.json"), run)
    w = run["wall_s"]
    print(f"run {args.run}: total {w['total']:.2f} s (export {w['export']:.2f}, worker {w['worker']:.2f}, "
          f"load {w['load']:.2f}); {len(pairs) - len(skipped)} of {len(pairs)} pairs computed this run")
    if skipped:
        return fail(f"pairs {skipped} were not computed by this run; a timed run needs an empty cache")
    return 0


if __name__ == "__main__":
    sys.exit(main())
