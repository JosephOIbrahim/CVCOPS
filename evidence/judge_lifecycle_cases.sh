#!/usr/bin/env bash
# tools/check.py through a mission's life, in a scratch copy of the kit: lock, start M1, a throwaway M1, a loosened
# threshold, a cheat, a pause line, a broken environment, and the two rungs that need the workstation.
#   bash evidence/judge_lifecycle_cases.sh
# The throwaway M1 below is stock DIS: it proves the product adapter in tests/thresholds/impls.py reaches the
# engine's code and that the rows pass with it. It is not shipped; Mission 1 writes the real one.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); KIT=$(cd "$HERE/.." && pwd)
PY=${PYTHON:-python3}
D=$(mktemp -d "${TMPDIR:-/tmp}/cvcops_lifecycle.XXXXXX")
cp -r "$KIT"/. "$D"/ && cd "$D" || exit 1
find . -name __pycache__ -type d -prune -exec rm -r {} + 2>/dev/null
rm -f judge.lock local.toml
git init -q . && git config user.email t@example.com && git config user.name t && git add -A && git commit -qm kit
export PYTHONPATH="$D/src${PYTHONPATH:+:$PYTHONPATH}"
ok=1
case_() { want="$1"; phrase="$2"; desc="$3"; shift 3; out=$("$@" 2>&1); got=$?
          if [ "$got" = "$want" ] && printf '%s' "$out" | grep -q -- "$phrase"; then echo "ok   $desc"
          else ok=0; echo "BAD  $desc (exit $got, want $want)"; printf '%s\n' "$out" | tail -8 | sed 's/^/     /'; fi; }
lock() { $PY tools/lock_judge.py --yes >/dev/null && git add -A && git commit -qm "$1"; }

case_ 1 "never been locked"        "before the first lock, rung 1 fails on the lock"            $PY tools/check.py
lock "lock the judge"
case_ 0 "rung 1 passes for M0"     "after the lock, M0 passes rung 1"                            $PY tools/check.py
echo M1 >> tests/thresholds/mission.txt
case_ 1 "changed since the lock"   "starting M1 without re-locking fails"                        $PY tools/check.py
lock "start M1"
case_ 1 "Mission 1's work"         "M1 started, nothing built: its rows fail and say why"        $PY tools/check.py

cat > src/cvcops/ops/flow.py <<'EOF'
import cv2
from ..contract import RECIPES, ContractError, check_analysis_pair
_PRESET = {"dis_medium": cv2.DISOPTICAL_FLOW_PRESET_MEDIUM, "dis_fast": cv2.DISOPTICAL_FLOW_PRESET_FAST}
def estimate_flow(a, b, recipe="dis_medium"):
    check_analysis_pair(a, b)
    if recipe not in RECIPES:
        raise ContractError(recipe)
    return cv2.DISOpticalFlow_create(_PRESET[recipe]).calc(a, b, None)
EOF
cat > src/cvcops/ops/validity.py <<'EOF'
import cv2, numpy as np
from ..contract import DEFAULT_TOLERANCE_PX, check_analysis_pair
from .flow import estimate_flow
def validity(a, b, tolerance_px=DEFAULT_TOLERANCE_PX, recipe="dis_medium", mask=None):
    check_analysis_pair(a, b)
    f, bwd = estimate_flow(a, b, recipe), estimate_flow(b, a, recipe)
    h, w = a.shape; ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    back = cv2.remap(bwd, xs + f[..., 0], ys + f[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=1e6)
    inside = (xs + f[..., 0] >= 0) & (xs + f[..., 0] <= w - 1) & (ys + f[..., 1] >= 0) & (ys + f[..., 1] <= h - 1)
    v = (np.sqrt(((f + back) ** 2).sum(-1)) <= tolerance_px) & inside
    return v if mask is None else v & mask
EOF
git add -A && git commit -qm "a throwaway M1"
case_ 0 "7 threshold rows"         "a working M1 passes all seven M1 rows through the adapter"   $PY tools/check.py

sed -i 's/limit=0.05, kind="max")/limit=0.50, kind="max")/' evidence/thresholds_reference.py
case_ 1 "thresholds_reference.py"  "a loosened threshold fails on the lock"                      $PY tools/check.py
git checkout -q -- evidence/thresholds_reference.py

printf 'import thresholds_reference\n' >> src/cvcops/ops/flow.py
case_ 1 "imports thresholds_reference" "the engine importing the reference is caught"            $PY tools/check.py
git checkout -q -- src/cvcops/ops/flow.py

printf 'WAITING: lock the judge\n' | cat - docs/STATE.md > /tmp/state.$$ && cp /tmp/state.$$ docs/STATE.md
case_ 1 "pause line"               "plain check fails while a pause line stands"                 $PY tools/check.py
case_ 0 "rung 1 passes"            "the hook's check ignores the pause line it already read"     $PY tools/check.py --hook
sed -i '1d' docs/STATE.md

mkdir -p shim && printf 'raise ImportError("simulated: jsonschema is not installed")\n' > shim/jsonschema.py
case_ 3 "BROKEN ENVIRONMENT"       "a missing package is a broken environment, exit 3"           env PYTHONPATH="$D/shim:$PYTHONPATH" $PY tools/check.py
rm -r shim

case_ 3 "no hython"                "rung 2 with no hython in local.toml is a broken environment" $PY tools/check.py --houdini
case_ 1 "M6 is not in"             "rung 3 with M6 not started has nothing to check, and fails"  $PY tools/check.py --gpu
case_ 0 "listed  M1"               "the listing marks the rows of the missions started"          $PY tools/check.py --list

# ---- rung 2, with a stand-in for hython and a stand-in asset that keeps bake_once.py's contract ----------------
mkdir -p fake && printf '#!/usr/bin/env bash\nexec %s "$@"\n' "$(command -v $PY)" > fake/hython && chmod +x fake/hython
printf 'hython = "%s"\n' "$D/fake/hython" > local.toml
$PY - "$D/houdini/tests/bake_once.py" <<'PYEOF'
import sys
open(sys.argv[1], "w").write('''import argparse, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "evidence"))
import numpy as np, thresholds_reference as ref
ap = argparse.ArgumentParser(); ap.add_argument("--mode"); ap.add_argument("--dir"); ap.add_argument("--preset", default="MEDIUM"); ap.add_argument("--scale", type=float, default=1.0)
o = ap.parse_args(); R = ref.Reference()
grey = lambda f: np.rint(R.read_exr(os.path.join(o.dir, f))[..., 0] * 255).astype(np.uint8)
a, b = grey("frame.1001.exr"), grey("frame.1002.exr"); h, w = a.shape
if o.mode == "flow":
    f = R.flow(a, b, o.preset, o.scale); s = max(w, h) / 2.0
    v_sign = 1.0 if os.environ.get("FAKE_ASSET_FORGETS_V") else -1.0
    out = np.dstack([f[..., 0] / s, f[..., 1] / s * v_sign, np.ones((h, w), np.float32)]).astype(np.float32)
    R.write_exr(os.path.join(o.dir, "flow.1001.exr"), out)
else:
    p = R.pull(a, b) / 255.0
    R.write_exr(os.path.join(o.dir, "pulled.1001.exr"), np.dstack([p, p, p]).astype(np.float32))
''')
PYEOF
printf 'M3\nM4\n' >> tests/thresholds/mission.txt
case_ 3 "P1 has not recorded"      "rung 2 before probe P1 records Houdini's Python is a broken environment" $PY tools/check.py --houdini
mkdir -p docs/facts && $PY probes/hython.py probes/p1_environment.py --site-packages > docs/facts/p1_site_packages.json
case_ 3 "P4 has not recorded"      "rung 2 before probe P4 records Houdini's units is a broken environment" $PY tools/check.py --houdini
printf '{"space": "image", "v_sign": -1, "recorded_by": "probe P4", "about": "stand-in"}\n' > tests/thresholds/houdini_units.json
lock "P1 and P4 recorded, M3 and M4 started"
case_ 0 "3 threshold rows"         "a stand-in asset that keeps the contract passes the M3 and M4 rows"    $PY tools/check.py --houdini
case_ 1 "analysis scale 1.0"       "an asset that forgets to flip v fails the M3 rows"                     env FAKE_ASSET_FORGETS_V=1 $PY tools/check.py --houdini
$PY -c 'import json; p = "docs/facts/p1_site_packages.json"; d = json.load(open(p)); d["sneaked-in-package"] = "1.0"; json.dump(d, open(p, "w"))'
case_ 1 "changed since P1"         "a package that appears in Houdini's Python is caught"                  $PY tools/check.py --houdini

[ "$ok" = 1 ] && echo "LIFECYCLE: every case behaves" || { echo "LIFECYCLE: a case misbehaves"; exit 1; }
