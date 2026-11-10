# Goals: one Claude Code session per mission

`/goal` keeps a session working until a condition holds. A small model reads the transcript after each turn and
decides. It needs Claude Code 2.1.139 or later and a trusted folder (FACTS K16). This workstation has 2.1.321.

**One goal covers one mission.** "Finish CVCOPs" cannot be a single goal, because the kit pauses for you by
design: the plan's OK, the licence, the lock, and your eyes in Missions 3 and 4.

## How a goal and the kit's pauses fit

The kit's Stop hook lets a turn end only when the checks pass or the first line of `docs/STATE.md` starts with
`WAITING:` or `BLOCKED:`. A goal adds a second check on top. So every goal line below ends with the same
clause: a pause line counts as met. The session then stops and waits for you. Answer, and paste the same goal
line again to carry on.

| Command | Does |
| --- | --- |
| `/goal <condition>` | Sets the goal and starts a turn |
| `/goal` | Shows the goal and the last verdict |
| `/goal clear` | Drops it |

A goal does not change the permission mode. The `ask` rules on judge files still prompt, and `git push` still
prompts. Never use `bypassPermissions`.

## Before each mission, your three steps

From Mission 1 on, in Git Bash, outside Claude:

1. Add the mission's name on its own line in `tests/thresholds/mission.txt`.
2. `uv run python tools/lock_judge.py`
3. `git add -A && git commit -m "Start M1"` (with the mission's own name)

In Windows PowerShell 5.1 the same three steps look like this. `&&` does not work there, so the commit is two
lines, and the commit line the lock tool prints must be split the same way.

```powershell
cd E:\Myth_and_Logic\Software\CVCOPS
Add-Content tests\thresholds\mission.txt "M1"
uv run python tools/lock_judge.py
git add -A
git commit -m "Start M1"
```

Run the lock in the working folder, not in another clone. A lock made elsewhere does not count here.

Mission 0 is closed (10 November 2026), so start at Session 2. Its lock comes at the end, when the session asks for it.

## Session 1: Mission 0

Open Git Bash or a terminal in this folder, run `claude`, trust the folder, then paste this as the first
message. It is the blueprint's kickoff prompt plus three facts about this folder.

```text
Read CLAUDE.md, GOALS.md, docs/BLUEPRINT.md, docs/FACTS.md and docs/STATE.md. We are at Mission 0.
This folder is not a git repository yet. After I OK the plan, run git init and make the first commit; the lock reads committed files. Leave the vendor/motion-cops submodule to me.
local.toml already points at hython for Houdini 22.0.492; confirm it in P1. On this machine bash on PATH is WSL, so check in P1 that hooks run in Git Bash.
Plan first: list the seven probes, what each records and where, and what you need from me.
Whenever you need me, put WAITING: and what you need on the first line of docs/STATE.md, then stop. Do that now, for the plan.
Then run Mission 0 only. Stop the same way when the probes are recorded and the self-test passes, for my lock. Finish when tools/check.py passes and docs/FACTS.md records all seven probe results.
Finish by updating docs/STATE.md: where we are, evidence, next action, blockers.
```

After you OK the plan, set the goal:

```text
/goal Mission 0 is done: the transcript shows uv run python tools/check.py exiting 0, docs/FACTS.md records the results of probes P1 to P7, and docs/STATE.md has a log entry with that command and the tail of its output. Constraints: Mission 0 only; no new dependency; nothing installed into Houdini's Python; never run tools/lock_judge.py. A pause is a stop: if the first line of docs/STATE.md starts with WAITING: or BLOCKED:, show that line and treat the goal as met. Otherwise stop after 60 turns and say what is left.
```

Expect two pauses after the plan: one for the licence and the public-or-private choice, one for your lock.

## Sessions 2 to 5

Do the three steps above first, `/clear` or start a new session, then paste one line.

**Mission 1, the flow operation**

```text
/goal Mission 1 is done: the transcript shows uv run python tools/check.py exiting 0 with the M1 rows listed and passing, and docs/STATE.md has a log entry with that command and the tail of its output. First confirm the committed tests/thresholds/mission.txt lists M1; if it does not, write WAITING: and stop. Constraints: Mission 1 only, as docs/BLUEPRINT.md defines it; no edits under tests/thresholds, tools/check.py, tools/lock_judge.py, docs/contracts or .claude; no new dependency. A pause is a stop: if the first line of docs/STATE.md starts with WAITING: or BLOCKED:, show that line and treat the goal as met. Otherwise stop after 40 turns and say what is left.
```

**Mission 2, the worker command**

```text
/goal Mission 2 is done: the transcript shows uv run python tools/check.py exiting 0 with the M2 rows listed and passing, uv run python -m cvcops capabilities shows flow and verify as available, and docs/STATE.md has a log entry with the check command and the tail of its output. First confirm the committed tests/thresholds/mission.txt lists M2; if it does not, write WAITING: and stop. Constraints: Mission 2 only; no edits under tests/thresholds, tools/check.py, tools/lock_judge.py, docs/contracts or .claude; no new dependency. A pause is a stop: if the first line of docs/STATE.md starts with WAITING: or BLOCKED:, show that line and treat the goal as met. Otherwise stop after 40 turns and say what is left.
```

**Mission 3, the bake asset.** Its parameters come from `houdini/build/controls.json`. Looks are your gate, so
this one pauses for you to open the example scene.

```text
/goal Mission 3 is done: the transcript shows uv run python tools/check.py --houdini exiting 0 with the M3 rows listed and passing, the asset was built by houdini/build/build_hdas.py from houdini/build/controls.json, Joe has confirmed the labels and defaults, and docs/STATE.md has a log entry with the check command and the tail of its output. First confirm the committed tests/thresholds/mission.txt lists M3; if it does not, write WAITING: and stop. Constraints: Mission 3 only; hython only, never the Houdini GUI; nothing installed into Houdini's Python; no edits under tests/thresholds, tools/check.py, tools/lock_judge.py, docs/contracts or .claude; no new dependency. A pause is a stop: if the first line of docs/STATE.md starts with WAITING: or BLOCKED:, show that line and treat the goal as met. Otherwise stop after 50 turns and say what is left.
```

**Mission 4, the warp**

```text
/goal Mission 4 is done: the transcript shows uv run python tools/check.py --houdini exiting 0 with the M4 rows listed and passing, the example scene carries a fix from a later frame onto earlier ones, Joe has looked at it, and docs/STATE.md has a log entry with the check command and the tail of its output. First confirm the committed tests/thresholds/mission.txt lists M4; if it does not, write WAITING: and stop. Constraints: Mission 4 only; hython only, never the Houdini GUI; no edits under tests/thresholds, tools/check.py, tools/lock_judge.py, docs/contracts or .claude; no new dependency. A pause is a stop: if the first line of docs/STATE.md starts with WAITING: or BLOCKED:, show that line and treat the goal as met. Otherwise stop after 50 turns and say what is left.
```

Then the release gate in `docs/BLUEPRINT.md`, which is yours.

## Unattended

Missions 1 and 2 can run without you through `bash tools/unattended.sh M1`, which the kit already ships and
tests. A goal also runs headless, as `claude -p` with the goal line as its prompt, but the launcher adds the
worktree branch and the judge report, so prefer it.

## After v0.1, outlines only

These get a goal line when their rows exist (decision 0003).

| Session | End state | Waits for |
| --- | --- | --- |
| Temporal check | `cvcops temporal` ranks frames; its rows pass | Rows drawn and locked (`docs/OPPORTUNITIES.md`) |
| ML probes PM1 to PM4 | Four results in `docs/FACTS.md`; no model code | v0.1 (`docs/ML_AND_AI.md`) |
| Mask input | `--mask` on the worker and the Mask input on the asset | The probe results and one new row |
