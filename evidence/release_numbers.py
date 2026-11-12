"""The release's numbers table (REL.release.numbers): every row beside its limit, from the receipts, not from prose.

    uv run python evidence/release_numbers.py

Reads, and writes nothing:

- the locked rows from `tests/thresholds/impls.py`, so the limits are the judge's own numbers,
- the rung-1 values by running the reference over those rows (no Houdini, no hython),
- the rung-2 values from `probe_out/m4_rows.json`, Joe's last values run through the asset,
- the bake receipt at `docs/facts/m3_bake_receipt.json`, for the timing medians and the quarter ratio DEC.quarter read,
- the plate summary at `docs/facts/rel_plate_summary.json`, numbers only.

Imports no hou, adds no dependency, and writes nothing in the repository.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "thresholds"))

RUNG2_RESULTS = ROOT / "probe_out" / "m4_rows.json"
BAKE_RECEIPT = ROOT / "docs" / "facts" / "m3_bake_receipt.json"
PLATE_SUMMARY = ROOT / "docs" / "facts" / "rel_plate_summary.json"


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def rung2_values():
    """Key -> value from the last values run through the asset, or {} if it was not kept."""
    data = _load(RUNG2_RESULTS) or {}
    out = {}
    for name, row in data.items():
        if "test_row[" in name and isinstance(row.get("value"), (int, float)):
            out[name.split("test_row[", 1)[1].rstrip("]")] = float(row["value"])
    return out


def rung1_values():
    """The reference over the rung-1 rows: the numbers every row is graded against here, not a product run."""
    import impls
    import thresholds_reference as ref
    cache = {}
    out = {}
    for row in ref.ROWS:
        if impls.RUNG.get(row["mission"]) == 1:
            out[row["key"]] = ref.METRICS[row["key"]](ref.Reference(), cache)
    return out


def fmt(row, value):
    if value is None:
        return "not recorded"
    if isinstance(value, bool):
        return f"{value} (limit {'true' if row['limit'] else 'false'})"
    return f"{value:.5g} ({row['threshold']})"


def main():
    import impls
    import thresholds_reference as ref

    r1 = rung1_values()
    r2 = rung2_values()
    print("## Rung 1, the reference, beside the locked thresholds\n")
    print("| Row | Mission | Value (limit) | Verdict |")
    print("| --- | --- | --- | --- |")
    for row in ref.ROWS:
        if impls.RUNG.get(row["mission"]) != 1:
            continue
        v = r1.get(row["key"])
        print(f"| `{row['key']}` -- {row['label']} | {row['mission']} | {fmt(row, v)} | "
              f"{ref.verdict(row, v) if v is not None else 'n/a'} |")

    print("\n## Rung 2, through the asset\n")
    print("| Row | Mission | Value (limit) | Verdict |")
    print("| --- | --- | --- | --- |")
    for row in ref.ROWS:
        if impls.RUNG.get(row["mission"]) != 2:
            continue
        v = r2.get(row["key"])
        print(f"| `{row['key']}` -- {row['label']} | {row['mission']} | {fmt(row, v)} | "
              f"{ref.verdict(row, v) if v is not None else 'n/a'} |")

    receipt = _load(BAKE_RECEIPT)
    if receipt:
        m, q = receipt["medians_s"], receipt["quarter"]
        print("\n## The bake receipt, five timed runs\n")
        print("| Phase | Median seconds |")
        print("| --- | --- |")
        for key in ("total", "export", "flow_compute", "worker_io", "worker_other", "load", "other"):
            print(f"| {key} | {m[key]:.3f} |")
        print(f"\nQuarter rule (DEC.quarter): median flow compute over median total = **{q['ratio']:.4f}**, "
              f"{'at least a quarter' if q['at_least_a_quarter'] else 'less than a quarter'}.")
    else:
        print("\n## The bake receipt\n\nnot recorded")

    plate = _load(PLATE_SUMMARY)
    if plate:
        chosen = plate["chosen"]
        run = next(r for r in plate["runs"] if r["run"] == chosen["run"])
        print("\n## The owner's plate, numbers only\n")
        print(f"{plate['plate']['pairs']} pairs at {plate['plate']['size'][0]}x{plate['plate']['size'][1]}, "
              f"{plate['plate']['colour_space']}, gain {run['gain']}, gamma {run['gamma']}")
        print(f"max clipped share {run['max_clipped_share']:.3f}, min grey levels {run['min_grey_levels']}, "
              f"valid share {run['valid_share_min']:.3f} to {run['valid_share_median']:.3f}, "
              f"largest p99 motion {run['largest_p99_motion_px']} px, warnings: "
              + (", ".join(run["warnings"]) if run["warnings"] else "none"))
    else:
        print("\n## The owner's plate\n\nnot recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
