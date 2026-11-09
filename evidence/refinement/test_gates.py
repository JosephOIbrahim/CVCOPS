"""Attack the gates before any reviewer is asked anything: every cheat must fail, an honest edit must pass."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
import sys; sys.path.insert(0, HERE)
import re, sys
import gates

target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "docs", "BLUEPRINT.md")
base = open(target).read(); facts = open(os.path.join(HERE, "..", "..", "docs", "FACTS.md")).read()
v0 = open(os.path.join(HERE, "v0.md")).read()
settings = open(os.path.join(HERE, "..", "..", ".claude", "settings.json")).read()
reference = open(os.path.join(HERE, "..", "thresholds_reference.py")).read()

def run(name, cand, expect_fail, allow=(), settings=settings, reference=reference):
    if name.startswith("cheat") and cand == base and settings is globals()["settings"] and reference is globals()["reference"]:
        print(f"BAD {name:<46} -> the cheat did not change anything; fix the test")
        return False
    problems, _ = gates.check(cand, v0, facts, allow, settings, reference)
    got = bool(problems)
    tag = "ok  " if got == expect_fail else "BAD "
    print(f"{tag}{name:<46} -> {'FAIL: ' + problems[0][:88] if problems else 'PASS'}")
    return got == expect_fail

ok = True
ok &= run("baseline", base, False)
ok &= run("cheat: drop a verified fact", base.replace("5.0.0.93", "5.1"), True)
ok &= run("cheat: invent a number", base.replace("| Unknown until probe P8 |", "| About 37 ms |"), True)
ok &= run("cheat: invent a speedup claim", base.replace("All score 0, each with a stated reason.", "All score 0; one recipe reached 2.6 times."), True)
ok &= run("cheat: bloat", base + "\n\n" + ("This paragraph adds reassuring detail without adding a decision. " * 60), True)
ok &= run("cheat: a mission loses its exit check", re.sub(r"(\| M2 Worker CLI \|[^|]*\|)[^|]*\|", r"\1  |", base), True)
ok &= run("cheat: count drifts from the list", base.replace("Nine rules drive every decision below.", "Seven rules drive every decision below."), True)
ok &= run("cheat: drop a section", base.replace("## 11. Risks and kill criteria", "## Risks"), True)
ok &= run("cheat: the Stop hook fails open", base, True, settings=settings.replace(" || exit 2", ""))
ok &= run("cheat: break the settings file", base, True, settings=settings.replace('"Bash(git push *)"', '"Bash(git push *)",'))
ok &= run("cheat: loosen a threshold in the table", base.replace("| at most 0.10 px |", "| at most 0.25 px |"), True)
ok &= run("cheat: reword a test the reference pins", base.replace("worst pair of the suite", "mean over the suite"), True)
ok &= run("cheat: loosen the reference instead", base, True, reference=reference.replace('threshold="at most 3%"', 'threshold="at most 30%"'))
ok &= run("honest: tighten a sentence", base.replace("When a later section looks arbitrary, one of these is the reason.", "A later choice that looks arbitrary traces to one of these."), False)
ok &= run("honest: reorder two risks", base, False)
print("\nGATE SELF-TEST:", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
