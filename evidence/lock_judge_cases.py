"""tools/lock_judge.py against the cases that matter. Standard library and git only.

    python evidence/lock_judge_cases.py

It copies the kit's judge files into a scratch repository and checks that the lock is refused or accepted
exactly when it should be: before a commit, after one, after a quiet edit, after a tampered lock, and in a worktree.
"""
import json, os, shutil, subprocess, sys, tempfile

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
work = tempfile.mkdtemp(prefix="cvcops_lock_")
repo = os.path.join(work, "repo")
for rel in ("tools/lock_judge.py", ".claude/settings.json", "evidence/thresholds_reference.py",
            "evolve/flow_recipe/evaluator.py", "evolve/flow_recipe/fixtures.py", "evolve/flow_recipe/promote.py", "evolve/flow_recipe/test_gaming.py"):
    os.makedirs(os.path.dirname(os.path.join(repo, rel)), exist_ok=True)
    shutil.copy(os.path.join(KIT, rel), os.path.join(repo, rel))
os.makedirs(os.path.join(repo, "tests", "thresholds"))
def write(rel, text, newline="\n"):
    with open(os.path.join(repo, rel), "w", newline=newline) as f: f.write(text)
write("tests/thresholds/mission.txt", "M0\n"); write("tests/thresholds/test_m1.py", "LIMIT = 0.12\n"); write("tools/check.py", "print('check')\n")

def sh(*cmd, cwd=repo):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
def lock(*args, cwd=repo):
    return sh(sys.executable, os.path.join(cwd, "tools", "lock_judge.py"), *args, cwd=cwd)
sh("git", "init", "-q", "."); sh("git", "config", "user.email", "t@example.com"); sh("git", "config", "user.name", "t"); sh("git", "config", "core.autocrlf", "false")
sh("git", "add", "."); sh("git", "commit", "-qm", "kit")

ok = True
def case(desc, got, want):
    global ok
    ok &= (got == want); print(f"{'ok ' if got == want else 'BAD'}  {desc}  (got {got}, want {want})")

r = lock("--check"); case("before any lock, the check fails", r.returncode, 1)
ask0 = json.load(open(os.path.join(repo, ".claude/settings.json")))["permissions"]["ask"]
case("the shipped settings do not yet ask before an edit to the tests", "Edit(/tests/thresholds/**)" in ask0, False)
r = lock("--yes"); case("the first lock succeeds", r.returncode, 0)
case("the first lock says what it arms", "This lock arms: Edit(/tests/thresholds/**), Edit(/tools/check.py)" in r.stdout, True)
ask1 = json.load(open(os.path.join(repo, ".claude/settings.json")))["permissions"]["ask"]
case("after it, the settings ask before an edit to the tests and to check.py", all(x in ask1 for x in ("Edit(/tests/thresholds/**)", "Edit(/tools/check.py)")), True)
r = lock("--check"); case("a lock that is not committed fails the check", r.returncode, 1)
sh("git", "add", "."); sh("git", "commit", "-qm", "lock")
r = lock("--check"); case("once committed, the check passes", r.returncode, 0)
write("tests/thresholds/test_m1.py", "LIMIT = 0.50\n")
r = lock("--check"); case("a loosened threshold fails the check", r.returncode, 1)
case("and the check names the file", "tests/thresholds/test_m1.py" in r.stdout, True)
write("tests/thresholds/test_m1.py", "LIMIT = 0.12\n")
r = lock("--check"); case("restoring the file passes again", r.returncode, 0)
write("tests/thresholds/test_m1.py", "LIMIT = 0.12\r\n", newline="")
r = lock("--check"); case("Windows line endings alone do not fail the check", r.returncode, 0)
write("tests/thresholds/test_m1.py", "LIMIT = 0.12\n")
write("tests/thresholds/test_extra.py", "pass\n")
r = lock("--check"); case("a new file among the tests fails the check", r.returncode, 1)
os.remove(os.path.join(repo, "tests/thresholds/test_extra.py"))
# the agent edits a test AND rewrites judge.lock to match, without a commit
write("tests/thresholds/test_m1.py", "LIMIT = 0.50\n")
import importlib.util
spec = importlib.util.spec_from_file_location("lj", os.path.join(repo, "tools", "lock_judge.py")); lj = importlib.util.module_from_spec(spec); spec.loader.exec_module(lj)
with open(os.path.join(repo, "judge.lock"), "w") as f: json.dump({"files": lj.current(repo)}, f, indent=1, sort_keys=True)
r = lock("--check"); case("a lock rewritten to match a loosened test still fails: it differs from the commit", r.returncode, 1)
sh("git", "checkout", "--", "judge.lock", "tests/thresholds/test_m1.py")
r = lock("--check"); case("back to the committed state, the check passes", r.returncode, 0)
# a mission start: Joe adds a mission and re-locks
write("tests/thresholds/mission.txt", "M0\nM1\n")
r = lock("--yes"); case("re-lock at a mission start lists the change", "changed  tests/thresholds/mission.txt" in r.stdout, True)
sh("git", "add", "."); sh("git", "commit", "-qm", "M1 starts")
r = lock("--check"); case("and passes once committed", r.returncode, 0)
wt = os.path.join(work, "wt"); sh("git", "worktree", "add", "-q", wt)
r = lock("--check", cwd=wt); case("a worktree of the same commit passes the check", r.returncode, 0)
r = subprocess.run([sys.executable, os.path.join(repo, "tools", "lock_judge.py")], cwd=repo, input="n\n", capture_output=True, text=True)
case("answering no leaves the judge unlocked and exits 1", r.returncode, 1)
print("LOCK: every case behaves" if ok else "LOCK: a case misbehaves"); sys.exit(0 if ok else 1)
