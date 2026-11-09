"""One bake through the asset, for the M3 and M4 threshold rows. Mission 3 writes this; it runs in hython.

The judge calls it through tests/thresholds/impls.py (HoudiniImpl), whose docstring is the contract:

    --mode flow --dir DIR --preset MEDIUM --scale S
        read DIR/frame.1001.exr and DIR/frame.1002.exr (RGB float32, equal channels, grey in 0 to 1), bake them
        through the asset at that preset and analysis scale, and write DIR/flow.1001.exr: the conversion node's
        output through ROP Image, R and G the flow in Houdini's units, B validity, at the frames' full size.
    --mode pull --dir DIR
        write DIR/pulled.1001.exr: frame B pulled onto A's grid by the asset's forward flow through native
        Distort, grey in 0 to 1 in R.

Exit 0 on success, 3 for a broken environment (no licence, the asset missing), anything else for a failure. It
must build the network from the installed asset, so the test grades what an artist would run.
"""
import argparse
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("flow", "pull"), required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--preset", default="MEDIUM")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.parse_args()
    print("bake_once.py: not built yet. It is Mission 3's work.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
