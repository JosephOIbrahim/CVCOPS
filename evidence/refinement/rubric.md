# CTO review rubric for an engineering blueprint

You are reviewing as a CTO who must approve this plan for a solo developer, and whose coding agent
(Claude Code) will execute it one mission per session. Score what is on the page, not what could be
inferred. Skip style, tone and formatting unless they cause a misreading.

Score each criterion from 0 to 5. Use whole numbers.
0 = absent. 1 = gestured at. 2 = present but an executor would have to guess. 3 = adequate.
4 = strong, at most one gap. 5 = nothing material to add.

| # | Criterion | What a 5 looks like |
| --- | --- | --- |
| 1 | Outcome and scope | One testable definition of the first release. Explicit non-goals. The reader can say what "done" is in a sentence. |
| 2 | Evidence | Every load-bearing claim is marked verified (with how) or assumed (with the probe that settles it). No number without a source. Unknowns are named, not papered over. |
| 3 | Decision quality | Hard-to-reverse decisions are identified and made deliberately, with the trade-off and what the choice turns on. Easy-to-reverse ones are kept cheap or deferred. |
| 4 | Sequencing | Work is ordered by dependency and by retiring the riskiest unknowns first. The smallest useful slice ships early. Optional work is clearly off the critical path. |
| 5 | Verifiability | Every mission ends in an executable check that passes or fails. Human gates are named with what the human must judge. Thresholds exist before the work. |
| 6 | Risk and kill criteria | Top risks have a signal, a pre-decided response and, where it applies, a stop rule. Build tax, vendor lock-in and licence risk are covered. |
| 7 | Cost discipline | Token, time and compute budgets are bounded. Optimisation is gated by measurement. The cheap option is tried first. |
| 8 | Operability for the executor | An agent can act on it without guessing: concrete commands, no contradictions, boundaries enforced by mechanism rather than prose, clear stop points. |
| 9 | Maintainability and ownership | Dependencies are pinned with an upgrade path. Upstream and licence posture are clear. It is clear who does what (agent or human). |
| 10 | Communication | The first screen gives the decision, the next action and what is needed from the owner. Numbers, names and counts agree across sections. |

## What to return

Return one JSON object and nothing else:

```json
{
  "scores": {"X": {"1": 0, "2": 0, "...": 0, "10": 0}, "Y": {"1": 0, "...": 0}},
  "totals": {"X": 0, "Y": 0},
  "weakest": {"X": "criterion number and one line why", "Y": "..."},
  "winner": "X or Y or tie",
  "why": "two sentences at most",
  "defects_in_winner": [
    {"severity": "high|medium|low", "where": "section and the exact words", "problem": "what an executor or owner would get wrong", "fix": "the smallest change that removes it"}
  ],
  "contradictions": ["any place where two parts of the same document disagree, quoted"],
  "unsupported": ["any factual claim or number in the winner that FACTS.md does not support, quoted"]
}
```

Rules for the defect list:
- At most five defects, most severe first. Fewer is fine. "None that matter" is a valid answer.
- A defect must change what someone would build, decide or verify. Wording preferences do not count.
- Do not ask for more content unless its absence blocks execution or hides a risk.
- If only one document is given, score it as X and leave Y out.
