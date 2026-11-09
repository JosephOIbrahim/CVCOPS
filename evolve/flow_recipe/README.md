# Flow recipe: an OpenEvolve seed

Evolve `estimate_flow(a, b)` for speed behind a hard accuracy gate. This is the pattern of OpenEvolve's
`background_blur` example, applied to optical flow with exact ground truth.

**Status.** Verified on 2026-11-08 in a 2-thread Linux sandbox, OpenEvolve 0.4.1, OpenCV 5.0.0: the config
loads, the cascade evaluator runs, six cheats and two known dead ends score zero, an honest speedup scores.
The sweep has run. No evolution has run yet: that needs a model.

## Order of work

1. `test_gaming.py`: the cheats and the dead ends must score 0. Run it before spending a token.
2. `sweep.py`: a plain sweep over DIS parameters. It writes `swept_program.py`, the seed and the bar.
3. `openevolve-run` from `swept_program.py`, up to three runs of 100 iterations, reading the trace after 20 to 50.
4. `promote.py <best_program.py>`: the verdict on the 25-pair holdout.

OpenEvolve 0.4.1 is pinned in the `evolve` group of `uv.lock`. A plain `uv sync` removes it again, so the run
names the group.

```
uv sync --group evolve
uv run python evolve/flow_recipe/test_gaming.py
uv run python evolve/flow_recipe/sweep.py
uv run --group evolve openevolve-run evolve/flow_recipe/swept_program.py evolve/flow_recipe/evaluator.py --config evolve/flow_recipe/config.yaml --iterations 100
uv run python evolve/flow_recipe/promote.py <path to best_program.py>
```

Set the model name in `config.yaml` first. Run on an idle machine: the score is a timing.

## Files

| File | Role |
| --- | --- |
| `initial_program.py` | Stock DIS MEDIUM inside `EVOLVE-BLOCK` markers: the reference recipe. |
| `swept_program.py` | Written by `sweep.py`: the sweep's winner, which seeds the search. |
| `evaluator.py` | Three-stage cascade: smoke, quality gate against ground truth, timing. Returns reasons as artifacts. |
| `fixtures.py` | Pairs with exact flow. Motions are drawn from ranges: 15 dev pairs, 25 holdout pairs, disjoint seeds. |
| `test_gaming.py` | Cheats and dead ends must score 0; an honest speedup must score. |
| `sweep.py` | 48 DIS configurations through the same gate and timing. |
| `promote.py` | Holdout verdict against the stock presets and the swept program. |
| `config.yaml` | Local model by default. Claude through the Claude Code CLI as a commented swap. |
| `check_under_openevolve.py` | Runs the evaluator through OpenEvolve's own classes. No model calls. |

## Rules

1. The search edits one block in one file. It never sees or changes the evaluator, fixtures, gaming tests or `promote.py`.
2. The gate is relative to the reference on each fixture. An absolute gate rejected the reference itself on unseen fixtures.
3. The dev-suite score is not evidence. Only `promote.py` decides.
4. A promoted recipe enters the package through a normal reviewed change, with the rung-1 tests green.
5. "No candidate beat the swept recipe" is a valid result. Stop after 300 iterations without a promotion.

## What the sandbox showed (960 by 540)

| Recipe | 15-pair dev suite | 25-pair holdout |
| --- | --- | --- |
| Stock MEDIUM (reference) | 1.0x, passes | passes |
| Stock FAST | scores 0 | fails |
| Half-resolution MEDIUM | scores 0 | fails |
| MEDIUM with 2 refinement iterations (swept) | 1.14 to 1.22x, passes | passes, 1.33 to 1.36x |

The first dev suite used five fixed motions and scored FAST at 4.4 to 4.7x. Drawing motions from ranges is what
made the dev suite reject the recipes the holdout rejects. The search must now beat about 1.53x MEDIUM.
