#!/usr/bin/env bash
# tools/unattended.sh with a stand-in for the claude CLI: does it refuse what it must, and report a judge file
# the run touched?
#   bash evidence/unattended_cases.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd); KIT="$HERE/.."
D=$(mktemp -d "${TMPDIR:-/tmp}/cvcops_unattended.XXXXXX"); cd "$D" || exit 1
git init -q . && git config user.email t@example.com && git config user.name t
mkdir -p tools docs tests/thresholds bin .claude
cp "$KIT/tools/unattended.sh" "$KIT/tools/lock_judge.py" tools/
echo '{"permissions": {"ask": []}}' > .claude/settings.json
echo "# State" > docs/STATE.md; echo "LIMIT = 0.12" > tests/thresholds/test_m1.py; echo "M1" > tests/thresholds/mission.txt
python3 tools/lock_judge.py --yes >/dev/null && git add . && git commit -qm "kit, judge locked for M1"
cat > bin/claude <<'EOS'
#!/usr/bin/env bash
# Makes the worktree as `-w <name>` does, commits some work, and misbehaves on request.
name="${@: -1}"; root="$(git rev-parse --show-toplevel)"; wt="$root/.claude/worktrees/$name"
git worktree add -q -b "worktree-$name" "$wt" >/dev/null 2>&1
cd "$wt" || exit 1
mkdir -p src && echo "x = 1" > src/flow.py && git add src && git commit -qm "work"
[ "${CHEAT:-}" = commit ] && { echo "LIMIT = 0.50" > tests/thresholds/test_m1.py; git commit -qam "loosen"; }
[ "${CHEAT:-}" = dirty ] && echo "LIMIT = 0.50" > tests/thresholds/test_m1.py
exit 0
EOS
chmod +x bin/claude
ok=1
case_() { want="$1"; phrase="$2"; desc="$3"; shift 3; out=$(env PATH="$D/bin:$PATH" "$@" 2>&1); got=$?
          if [ "$got" = "$want" ] && printf '%s' "$out" | grep -q "$phrase"; then echo "ok   $desc"; else ok=0; echo "BAD  $desc (exit $got, want $want)"; printf '%s\n' "$out" | sed 's/^/     /'; fi; }
case_ 2 "M1 and M2 only"        "a mission other than M1 or M2 is refused"               bash tools/unattended.sh MU
case_ 2 "does not list M2"      "a mission missing from the committed mission.txt is refused" bash tools/unattended.sh M2
echo "LIMIT = 0.50" > tests/thresholds/test_m1.py
case_ 2 "differs from its committed lock" "a judge edited before the run is refused"    bash tools/unattended.sh M1
git checkout -q -- tests/thresholds/test_m1.py
echo "M2" >> tests/thresholds/mission.txt
case_ 2 "does not list M2"      "an uncommitted mission.txt does not count"               bash tools/unattended.sh M2
python3 tools/lock_judge.py --yes >/dev/null && git add . && git commit -qm "M2 started, judge re-locked"
case_ 0 "No judge file touched" "an honest run may be merged"                             bash tools/unattended.sh M1
case_ 3 "DO NOT MERGE"          "a run that commits a loosened test is reported"          env CHEAT=commit bash tools/unattended.sh M2
git worktree remove --force .claude/worktrees/m2 && git branch -q -D worktree-m2
case_ 3 "DO NOT MERGE"          "a run that leaves a loosened test uncommitted is too"    env CHEAT=dirty bash tools/unattended.sh M2
[ "$ok" = 1 ] && echo "LAUNCHER: every case behaves" || { echo "LAUNCHER: a case misbehaves"; exit 1; }
