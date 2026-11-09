#!/usr/bin/env bash
# Run one mission with nobody watching. Only M1 and M2 qualify: rung 1 can verify all of their work.
#   bash tools/unattended.sh M1
# Before the run it refuses (exit 2) unless the committed tests/thresholds/mission.txt lists the mission and the
# judge matches its committed lock. The run gets its own worktree branch, a 60-turn cap, file edits without
# prompts, and nobody to answer a prompt, so an edit to a judge file through Claude's own tools is denied. When
# the run ends this script lists any judge file the branch touched anyway.
# Exit codes: 2 refused before the run; 3 do not merge; otherwise Claude's own exit code.
# Swap the model with CVCOPS_LIGHT_MODEL (default: sonnet).
set -uo pipefail
mission="${1:?usage: bash tools/unattended.sh M1}"
case "$mission" in
  M1|M2) ;;
  *) echo "REFUSED: unattended runs are for M1 and M2 only; $mission needs someone there."; exit 2 ;;
esac
name="$(printf '%s' "$mission" | tr '[:upper:]' '[:lower:]')"
root="$(git rev-parse --show-toplevel)" || { echo "Run this inside the repository."; exit 1; }
cd "$root" || exit 1
base="$(git rev-parse HEAD)"

if command -v uv >/dev/null 2>&1 && [ -f pyproject.toml ]; then py=(uv run python)
elif command -v python3 >/dev/null 2>&1; then py=(python3)
else py=(python); fi

if ! git show "HEAD:tests/thresholds/mission.txt" 2>/dev/null | tr -d '\r' | grep -qx "$mission"; then
  echo "REFUSED: the committed tests/thresholds/mission.txt does not list $mission."
  echo "Add it, run tools/lock_judge.py, commit both, then start again."; exit 2
fi
if ! "${py[@]}" tools/lock_judge.py --check >/dev/null 2>&1; then
  echo "REFUSED: the judge differs from its committed lock. See: ${py[*]} tools/lock_judge.py --check"; exit 2
fi

claude -p "Run mission ${mission} from docs/BLUEPRINT.md. Nobody is here: never write WAITING. If you are stuck, write BLOCKED: and the reason on the first line of docs/STATE.md and stop." \
  --max-turns 60 --permission-mode acceptEdits --permission-prompts none \
  --allowedTools "Bash(uv run *),Bash(git add *),Bash(git commit *)" \
  --model "${CVCOPS_LIGHT_MODEL:-sonnet}" --effort medium -w "$name"
status=$?

wt="$root/.claude/worktrees/$name"
if [ ! -d "$wt" ]; then
  echo "The run left no worktree at $wt (Claude exited $status)."; exit "$status"
fi
mapfile -t judge < <("${py[@]}" tools/lock_judge.py --paths 2>/dev/null)
if [ "${#judge[@]}" -eq 0 ]; then
  echo "DO NOT MERGE YET: could not read the judge's paths from tools/lock_judge.py."; exit 3
fi
touched="$( { git -C "$wt" diff --name-only "$base" HEAD -- "${judge[@]}"; git -C "$wt" status --porcelain -- "${judge[@]}" | cut -c4-; } | sort -u )"
branch="$(git -C "$wt" rev-parse --abbrev-ref HEAD)"
echo
if [ -n "$touched" ]; then
  echo "DO NOT MERGE: this run touched judge files on branch $branch (exit 3):"; printf '  %s\n' $touched; exit 3
fi
echo "No judge file touched on branch $branch. Claude exited $status (0 means it finished its turns cleanly)."
echo "Next: read docs/STATE.md in $wt, then"
echo "  git merge $branch && uv run python tools/check.py"
exit "$status"
