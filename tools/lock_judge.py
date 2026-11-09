"""Lock the judge. Joe runs this, outside Claude. A deny rule keeps the agent from running it.

    python tools/lock_judge.py           show what changed since the last lock, ask, then lock
    python tools/lock_judge.py --yes     the same without the question
    python tools/lock_judge.py --check   exit 0 only if the judge matches judge.lock and the committed lock
    python tools/lock_judge.py --paths   print the judge's paths, one per line, for `git diff -- <paths>`

The judge is every file a mission is graded by: the threshold tests and their adapters, check.py, this script, the
reference the tests come from, the contracts, probe P1's record of Houdini's Python, the evolve lane's evaluator
files, and the Claude Code settings that hold the rules and the hook.
judge.lock records a hash of each. check.py calls verify() and fails on any difference, and fails while
judge.lock differs from the copy in the last commit, so a quiet edit to a test shows up at the next check.

The first lock also arms three permission rules. Until then the agent may write tests/thresholds/, tools/check.py
and docs/contracts/ freely, because Mission 0 records probe results there (houdini_units.json from P4) and fixes
anything the Windows self-test turns up. From the first lock on, an edit to any of them asks first.
"""
import argparse, fnmatch, hashlib, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK = "judge.lock"
SETTINGS = ".claude/settings.json"
JUDGE = [
    "tests/thresholds/**",
    "tools/check.py",
    "tools/lock_judge.py",
    "evidence/thresholds_reference.py",
    "docs/contracts/**",
    "docs/facts/p1_site_packages.json",
    "evolve/flow_recipe/evaluator.py",
    "evolve/flow_recipe/fixtures.py",
    "evolve/flow_recipe/promote.py",
    "evolve/flow_recipe/test_gaming.py",
    SETTINGS,
]
ARMED_AT_FIRST_LOCK = ["Edit(/tests/thresholds/**)", "Edit(/tools/check.py)", "Edit(/docs/contracts/**)"]
SKIP = ("__pycache__", ".pyc", ".pytest_cache")


def judge_files(root=ROOT):
    found = set()
    for pattern in JUDGE:
        if pattern.endswith("/**"):
            top = os.path.join(root, pattern[:-3])
            for folder, _, names in os.walk(top):
                for name in names:
                    rel = os.path.relpath(os.path.join(folder, name), root).replace(os.sep, "/")
                    if not any(s in rel for s in SKIP):
                        found.add(rel)
        elif os.path.isfile(os.path.join(root, pattern)):
            found.add(pattern)
    return sorted(found)


def digest(path):
    """Hash of the file with line endings normalised, so a Windows checkout and a Linux one agree."""
    with open(path, "rb") as f:
        data = f.read()
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def current(root=ROOT):
    return {rel: digest(os.path.join(root, rel)) for rel in judge_files(root)}


def read_lock(root=ROOT):
    path = os.path.join(root, LOCK)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)["files"]


def committed_lock(root=ROOT):
    """The files table of judge.lock in the last commit, or None if it is not committed or this is not a repo."""
    try:
        out = subprocess.run(["git", "show", "HEAD:" + LOCK], cwd=root, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout.decode("utf-8"))["files"]
    except (ValueError, KeyError):
        return None


def diff(old, new):
    old = old or {}
    added = sorted(set(new) - set(old)); removed = sorted(set(old) - set(new))
    changed = sorted(p for p in set(old) & set(new) if old[p] != new[p])
    return added, changed, removed


def verify(root=ROOT):
    """Problems as a list of sentences. An empty list means the judge is the locked one. check.py calls this."""
    locked = read_lock(root)
    if locked is None:
        return ["judge.lock does not exist yet: the judge has never been locked"]
    problems = []
    added, changed, removed = diff(locked, current(root))
    problems += [f"judge file changed since the lock: {p}" for p in changed]
    problems += [f"judge file added since the lock: {p}" for p in added]
    problems += [f"judge file removed since the lock: {p}" for p in removed]
    head = committed_lock(root)
    if head is None:
        problems.append("judge.lock is not in the last commit")
    elif head != locked:
        problems.append("judge.lock differs from the copy in the last commit")
    return problems


def arm(root=ROOT):
    """Add the rules that start at the first lock. Returns the rules it added."""
    path = os.path.join(root, SETTINGS)
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    ask = cfg.setdefault("permissions", {}).setdefault("ask", [])
    missing = [rule for rule in ARMED_AT_FIRST_LOCK if rule not in ask]
    if missing:
        ask.extend(missing)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cfg, f, indent=2); f.write("\n")
    return missing


def main():
    ap = argparse.ArgumentParser(description="Lock the judge, or check it against the lock.")
    ap.add_argument("--check", action="store_true"); ap.add_argument("--yes", action="store_true")
    ap.add_argument("--paths", action="store_true")
    a = ap.parse_args()
    if a.paths:
        print("\n".join([LOCK] + [p[:-3] if p.endswith("/**") else p for p in JUDGE]))
        return 0
    if a.check:
        problems = verify()
        for p in problems:
            print("JUDGE:", p)
        print("JUDGE: " + ("matches the lock" if not problems else f"{len(problems)} problem(s)"))
        return 1 if problems else 0

    if not os.path.isfile(os.path.join(ROOT, SETTINGS)):
        print(f"{SETTINGS} is missing. The kit ships it; restore it before locking."); return 1
    old = read_lock(); new = current()
    added, changed, removed = diff(old, new)
    print("First lock." if old is None else "Since the last lock:")
    if old is not None:
        try:
            last = subprocess.run(["git", "log", "-1", "--format=%h  %an  %ad  %s", "--date=short", "--", LOCK], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            last = ""
        print("  the lock in force was committed as: " + (last or "(never committed)"))
        print("  If that commit is not yours, stop and look at it before you lock again.")
    for label, paths in (("added", added), ("changed", changed), ("removed", removed)):
        for p in paths:
            print(f"  {label:<8} {p}")
    if old is not None and not (added or changed or removed):
        print("  nothing changed")
    with open(os.path.join(ROOT, SETTINGS), encoding="utf-8") as f:
        ask_now = json.load(f).get("permissions", {}).get("ask", [])
    to_arm = [r for r in ARMED_AT_FIRST_LOCK if r not in ask_now]
    if to_arm:
        print("This lock arms: " + ", ".join(to_arm))
    if changed or removed:
        print("Read each changed file before you agree: `git diff` shows what moved.")
    if not a.yes:
        if input("Lock this judge? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Not locked."); return 1
    arm()
    with open(os.path.join(ROOT, LOCK), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"files": current()}, f, indent=1, sort_keys=True); f.write("\n")
    print(f"Wrote {LOCK} for {len(current())} files. Now commit it with the judge:")
    print(f"  git add {LOCK} {SETTINGS} tests/thresholds tools/check.py docs/contracts && git commit -m \"Lock the judge\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
