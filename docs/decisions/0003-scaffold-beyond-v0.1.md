# 0003. Scaffold the controls, the motion opportunities and the ML and AI lanes now; build them after v0.1

Status: accepted, 9 November 2026. Joe asked for the scaffold when the work moved to Claude Code on the
workstation.

## Decision

**The scaffold is specs, registers, stubs and references. None of it enters the v0.1 judge, and the release
gate's order stands.**

| Scaffold | Files | Live when |
| --- | --- | --- |
| Controls | `houdini/build/controls.json`, `docs/CONTROLS.md`, `tests/unit/test_controls.py` | Mission 3, which builds the asset from it |
| Motion opportunities | `docs/opportunities.json`, `docs/OPPORTUNITIES.md`, `src/cvcops/ops/temporal.py`, `evidence/opportunities_reference.py`, `tests/unit/test_opportunities.py` | After v0.1, one at a time, each with locked rows first |
| ML and AI | `docs/ML_AND_AI.md`, probes PM1 to PM4 in `docs/FACTS.md` | After v0.1, each lane behind its entry gate |
| Goals | `GOALS.md` | Now: one goal line per Claude Code session |

## Why

The blueprint's risk table names scope creep: a node beyond flow before v0.1 gets parked. A scaffold keeps that
rule and still records the thinking while it is fresh. The controls are the one part v0.1 needs, because
Mission 3 cannot build an asset without its interface.

## What each side may do

- A session may read the scaffold at any time and may extend a doc or a register when it learns something.
- A session may not write the body of a parked stub, add an operation, or add a dependency before v0.1 ships.
- An opportunity or an ML lane becomes a mission by the five steps at the end of `docs/OPPORTUNITIES.md`.
- The temporal check is the one opportunity marked `next`. Changing the pick is Joe's call and a line in
  `docs/STATE.md`.

## Consequences

The repository now says what could come after v0.1 without promising it. Two new unit tests run at rung 1 and
keep the scaffold honest: the controls cannot drift from the worker, and the register cannot name an operation
the manifest lacks. `docs/BLUEPRINT.md` is unchanged.
