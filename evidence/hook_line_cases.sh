#!/usr/bin/env bash
# The Stop hook line from .claude/settings.json, run against every case that matters.
# Claude Code blocks a stop only on exit code 2. Anything else from a Stop hook lets the turn end,
# so a crash or a missing tool must come out as 2, and a declared pause must come out as 0.
# Hooks run in Claude's current directory, which follows `cd`, so the line finds the project root itself.
#   bash evidence/hook_line_cases.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
PY=$(command -v python3 || command -v python)
HOOK=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['hooks']['Stop'][0]['hooks'][0]['command'])" "$HERE/../.claude/settings.json") || exit 1
D=$(mktemp -d "${TMPDIR:-/tmp}/cvcops_hook.XXXXXX"); cd "$D" || exit 1
mkdir -p docs tools bin src/cvcops/deep vendor/upstream/docs .claude/worktrees/m1/docs .claude/worktrees/m1/tools .claude/worktrees/m1/src
cat > tools/check.py <<'PY'
import os, sys
mode = os.environ.get("FAKE", "pass")
if mode == "fail": print("M1 threshold failed: mean error 0.31 > 0.12", file=sys.stderr); sys.exit(1)
if mode == "crash": raise RuntimeError("check.py itself is broken")
if mode == "env": print("ENVIRONMENT: hython not found", file=sys.stderr); sys.exit(3)
PY
printf 'import sys\nprint("worktree check ran", file=sys.stderr)\nsys.exit(1)\n' > .claude/worktrees/m1/tools/check.py
printf '#!/bin/sh\nshift; exec "$@"\n' > bin/uv; chmod +x bin/uv          # stands in for `uv run`
printf '#!/bin/sh
exec "%s" "$@"
' "$PY" > bin/python; chmod +x bin/python
ok=1
case_() { want="$1"; where="$2"; desc="$3"; shift 3; ( cd "$D/$where" && "$@" bash -c "$HOOK" ) >/dev/null 2>"$D/err.txt"; got=$?
          [ "$got" = "$want" ] || ok=0; printf '%-4s exit %s (want %s)  %s\n' "$([ "$got" = "$want" ] && echo ok || echo BAD)" "$got" "$want" "$desc"; }
export PATH="$D/bin:$PATH"; W=env
echo "# State" > docs/STATE.md
case_ 0 .  "tests pass"                                   $W FAKE=pass
case_ 2 .  "a test fails"                                 $W FAKE=fail
case_ 2 .  "check.py crashes"                             $W FAKE=crash
case_ 2 .  "the environment is broken"                    $W FAKE=env
case_ 2 .  "uv is not on PATH"                            env PATH=/usr/bin:/bin FAKE=pass
case_ 2 src/cvcops/deep "a test fails, run from a subdirectory"      $W FAKE=fail
case_ 0 src/cvcops/deep "tests pass, run from a subdirectory"        $W FAKE=pass
case_ 2 vendor/upstream "a test fails, run from inside vendor/"      $W FAKE=fail
printf 'WAITING: plan for M1, need your OK\n# State\n' > docs/STATE.md
case_ 0 .  "a test fails, first line WAITING:"            $W FAKE=fail
case_ 0 src/cvcops/deep "first line WAITING:, run from a subdirectory" $W FAKE=fail
printf 'BLOCKED: P3 cannot be made raw\n# State\n' > docs/STATE.md
case_ 0 .  "a test fails, first line BLOCKED:"            $W FAKE=fail
echo "# State" > .claude/worktrees/m1/docs/STATE.md
case_ 2 .claude/worktrees/m1/src "a worktree is judged by its own state and checks, not the main checkout's" $W FAKE=pass
grep -q "worktree check ran" "$D/err.txt" || { ok=0; echo "BAD  the worktree's own check.py did not run"; }
printf '# State\nWAITING: not on the first line\n' > docs/STATE.md
case_ 2 .  "WAITING lower down, a test fails"             $W FAKE=fail
mv docs/STATE.md docs/STATE.gone
case_ 2 .  "STATE.md missing, a test fails"               $W FAKE=fail
case_ 0 .  "STATE.md missing, tests pass"                 $W FAKE=pass
[ "$ok" = 1 ] && echo "HOOK LINE: every case behaves" || { echo "HOOK LINE: a case misbehaves"; exit 1; }
