"""Hard gates for blueprint refinement. A candidate that fails any gate scores zero, whatever a reviewer thinks.

    python gates.py <candidate.md> [--baseline v0.md] [--facts FACTS.md] [--allow "10" "12 px" ...]

G1 facts      every load-bearing fact (pattern list below) is still present
G2 numbers    no numeric token that is absent from the baseline and from FACTS.md (stops invented figures)
G3 structure  all sections in order; every mission row has a "Done when"; kickoff block present;
              the kit's .claude/settings.json parses and its Stop hook fails closed
G4 size       at most CAP x the baseline word count (refine by sharpening, not by adding)
G5 counts     stated counts match what they count (premises, rules, probes, missions, fixes)
G6 exam       every row of evidence/thresholds_reference.py appears in the threshold table with the same
              wording and the same threshold, so the document and the reference cannot drift apart
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
import json, re, sys, argparse

FACTS = [
    r"d2a22ad", r"26 Oct 2026", r"255\.0", r"\(1, 2, 0\.3\)", r"next_pos", r"no HDK support for Copernicus",
    r"no licen[cs]e file", r"\.hdalc", r"5 Nov 2026", r"5\.0\.0\.93", r"about 0\.02 px", r"0\.79 s \(MEDIUM\)", r"1\.3 s",
    r"Feb 2023", r"RTX 50", r"Time Shift", r"Ripple solver", r"OpenEXR: NO", r"bit-exact", r"useOpenCL\(\)",
    r"patch size 8", r"at or below 16", r"opencv_px", r"float32 RGB", r"0\.4\.1", r"Six deliberate cheats",
    r"3\.6 to 3\.9", r"4\.4 to 4\.7", r"1\.53", r"1\.33 to 1\.36", r"25-pair holdout", r"15-pair", r"15%", r"300 iterations", r"100 iterations",
    r"0\.018 to 0\.023", r"0\.058 to 0\.102", r"0\.083 px", r"at most 0\.05 px", r"at most 0\.15 px", r"at most 0\.12 px",
    r"lines 161 to 195", r"lines 283 to 292", r"lines 584 to 621", r"Lines 10 and 11", r"20%", r"a quarter of the time", r"bake receipt",
    r"CPython 3\.13", r"judge\.lock", r"BLOCKED:", r"tools/check\.py --hook", r"No evolution run", r"MoGe-2", r"SAM2",
    r"3e72b5b", r"unverified",
    # added by the first-principles review of 2026-11-09 (see gate_changes.log)
    r"WAITING:", r"thresholds_reference\.py", r"--selftest", r"at most 3%", r"two regions 16 px apart", r"32-bit float",
    r"1 to 48 threads", r"Git Bash", r"claude doctor", r"\.claude/settings\.json", r"tools/unattended\.sh", r"0\.869",
    # added by the workstation cross-reference of 2026-11-09
    r"OpenFX", r"Precision 32-bit", r"Maintain State", r"ROP Image", r"write_exr", r"mission\.txt", r"preferences folder",
    # added by the plugin scaffold of 2026-11-09
    r"impls\.py", r"capabilities\.json", r"0001-synapse-umbrella", r"nine planted faults", r"ARCHITECTURE\.md",
]
CAP = 1.25
SECTIONS = ["## Capsule", "## 1. Thesis", "## 2. What v1 assumed", "## 3. The one judgment call", "## 4. First principles",
            "## 5. Architecture", "## 6. Flow contract v1", "## 7. Evolve lane", "## 8. Missions",
            "## 9. Operating rules for Claude Code", "## 10. Upstream track", "## 11. Risks and kill criteria",
            "## 12. Parked until v0.1 ships", "## 13. Kickoff prompt", "## 14. Sources"]
MISSIONS = ["M0", "M1", "M2", "M3", "M4", "ME", "M5", "M6", "MN", "MU"]
NUM = re.compile(r"(?<![\w.#/-])\d+(?:[.,]\d+)*%?(?![\w/-])")
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "thirteen": 13}


def strip_links(t):
    return re.sub(r"\]\([^)]*\)", "]", t)


def numbers(t):
    return set(NUM.findall(strip_links(t)))


def section(t, head):
    i = t.index(head); j = t.find("\n## ", i + 1)
    return t[i:(j if j != -1 else len(t))]


def table_rows(sec):
    rows = [l for l in sec.splitlines() if l.startswith("|")]
    return [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]


def numbered_items(sec):
    return len(re.findall(r"^\d+\. ", sec, flags=re.M))


def check(cand, base, facts, allow=(), settings=None, reference=None):
    problems = []
    # G1
    for pat in FACTS:
        if not re.search(pat, cand):
            problems.append(f"G1 facts: missing /{pat}/")
    # G2
    new = numbers(cand) - numbers(base) - numbers(facts) - set(allow)
    if new:
        problems.append("G2 numbers: not in baseline or FACTS.md: " + ", ".join(sorted(new)))
    # G3
    pos = -1
    for h in SECTIONS:
        p = cand.find("\n" + h)
        if p == -1:
            problems.append(f"G3 structure: missing section {h!r}")
        elif p < pos:
            problems.append(f"G3 structure: section out of order {h!r}")
        pos = max(pos, p)
    if not any(p.startswith("G3") for p in problems):
        ms = section(cand, "## 8. Missions"); rows = table_rows(ms)
        head = next((r for r in rows if "Mission" in r[0] and "Done when" in r), None)
        if head is None:
            problems.append("G3 structure: mission table header with 'Done when' not found")
        else:
            di = head.index("Done when")
            for m in MISSIONS:
                row = next((r for r in rows if r[0].startswith(m + " ")), None)
                if row is None:
                    problems.append(f"G3 structure: mission {m} has no row")
                elif len(row) <= di or len(row[di]) < 12:
                    problems.append(f"G3 structure: mission {m} has no 'Done when'")
        if settings is not None:
            try:
                cfg = json.loads(settings); cmd = cfg["hooks"]["Stop"][0]["hooks"][0]["command"]
                assert "tools/check.py --hook" in cmd, "the Stop hook does not run check.py"
                assert cmd.rstrip().endswith("|| exit 2"), "the Stop hook does not fail closed"
                assert "WAITING|BLOCKED" in cmd, "the Stop hook has no pause line"
                assert "Edit(/vendor/**)" in cfg["permissions"]["deny"], "vendor/ is not denied"
                assert cfg["env"]["CLAUDE_CODE_USE_POWERSHELL_TOOL"] == "0", "the PowerShell tool is not switched off"
            except Exception as e:
                problems.append(f"G3 structure: .claude/settings.json: {type(e).__name__}: {e}")
        if "```text" not in section(cand, "## 13. Kickoff prompt"):
            problems.append("G3 structure: kickoff prompt block missing")
    # G4
    wc, wb = len(strip_links(cand).split()), len(strip_links(base).split())
    if wc > CAP * wb:
        problems.append(f"G4 size: {wc} words > {CAP} x baseline {wb}")
    # G5
    if not any(p.startswith("G3") for p in problems):
        def said(pattern, text):
            m = re.search(pattern, text, flags=re.I)
            return WORDS.get(m.group(1).lower()) if m else None
        s2 = section(cand, "## 2. What v1 assumed"); rows = table_rows(s2)[2:]
        holds = sum(r[1] in ("Holds", "Hold") for r in rows); new_ = sum(r[0].startswith("New:") for r in rows)
        change = len(rows) - holds - new_
        want = (said(r"(\w+) of v1's premises hold", s2), said(r"hold, (\w+) change", s2), said(r"and (\w+) findings? (?:are|is) new", s2))
        if want != (holds, change, new_):
            problems.append(f"G5 counts: section 2 says {want}, table has hold/change/new = {(holds, change, new_)}")
        s4 = section(cand, "## 4. First principles")
        if said(r"(\w+) rules drive", s4) != numbered_items(s4):
            problems.append(f"G5 counts: section 4 rule count {said(r'(\w+) rules drive', s4)} != {numbered_items(s4)} items")
        s7 = section(cand, "## 7. Evolve lane")
        if said(r"(\w+) rules govern", s7) != numbered_items(s7):
            problems.append(f"G5 counts: section 7 rule count {said(r'(\w+) rules govern', s7)} != {numbered_items(s7)} items")
        s8 = section(cand, "## 8. Missions")
        probes = len(re.findall(r"^\| P\d+ ", s8, flags=re.M))
        if said(r"answers (\w+) questions", s8) != probes:
            problems.append(f"G5 counts: probes said {said(r'answers (\w+) questions', s8)} != {probes} rows")
        core = len(re.findall(r"^\| M[0-4] [A-Z]", s8, flags=re.M))      # mission rows, not the "M3 known motion" threshold row
        if said(r"(\w+) missions reach v0\.1", s8) != core or f"Mile 0 of {core}" not in cand:
            problems.append(f"G5 counts: core missions {core} disagree with the text or the capsule")
        s10 = section(cand, "## 10. Upstream track"); fixes = len(table_rows(s10)[2:]) - 1
        if said(r"(\w+) fixes and one request", s10) != fixes:
            problems.append(f"G5 counts: upstream fixes said {said(r'(\w+) fixes and one request', s10)} != {fixes}")
    # G6
    if reference is not None and not any(p.startswith("G3") for p in problems):
        rows = re.findall(r'dict\(key="(\w+)", mission="(M\d)", label="([^"]*)", threshold="([^"]*)"', reference)
        if len(rows) < 8:
            problems.append(f"G6 exam: only {len(rows)} rows found in the reference; the parser or the file is wrong")
        lines = [l for l in section(cand, "## 8. Missions").splitlines() if l.startswith("| M")]
        for key, mission, label, threshold in rows:
            if not any(l.startswith(f"| {mission} |") and label in l and f"| {threshold} |" in l for l in lines):
                problems.append(f"G6 exam: no {mission} row with the reference's wording and threshold for {key!r}")
    return problems, {"words": wc, "baseline_words": wb}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("candidate"); ap.add_argument("--baseline", default=os.path.join(HERE, "v0.md"))
    ap.add_argument("--facts", default=os.path.join(HERE, "..", "..", "docs", "FACTS.md")); ap.add_argument("--allow", nargs="*", default=[])
    ap.add_argument("--settings", default=os.path.join(HERE, "..", "..", ".claude", "settings.json"))
    ap.add_argument("--reference", default=os.path.join(HERE, "..", "thresholds_reference.py"))
    a = ap.parse_args()
    problems, info = check(open(a.candidate).read(), open(a.baseline).read(), open(a.facts).read(), a.allow,
                           open(a.settings).read(), open(a.reference).read())
    print(f"words {info['words']} (baseline {info['baseline_words']}, cap {int(CAP * info['baseline_words'])})")
    for p in problems:
        print("FAIL", p)
    print("GATES:", "PASS" if not problems else f"FAIL ({len(problems)})")
    sys.exit(0 if not problems else 1)
