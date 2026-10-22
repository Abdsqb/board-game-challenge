# Measured local results

These are measured results from the local assumptions, not competition results or proof of optimal play.

## Connect 4

Requested search budget: 60 ms; 120 games per opponent, alternating first/second seat.

| Opponent | Wins/games | Win rate | Wilson 95% interval |
|---|---:|---:|---:|
| random | 120/120 | 100.0% | 96.9%–100.0% |
| tactical | 119/120 | 99.2% | 95.4%–99.9% |
| greedy | 120/120 | 100.0% | 96.9%–100.0% |

Combined: 359/360 wins. The opponents are local random, one-turn tactical and greedy strategies; none is a full solver.

| Opponent | Median search ms | Maximum search ms |
|---|---:|---:|
| random | 60.7 | 68.6 |
| tactical | 60.5 | 69.9 |
| greedy | 60.6 | 121.6 |

Time checks are cooperative. Recorded maxima include interpreter/check-interval overhead and scheduling delays; do not set the requested budget equal to an organizer's hard limit.

## Clue deduction arena

120 games per mode; 3–6 players, varying seats. Physical mansion movement is omitted.

| Selected seat strategy | Wins/games | Win rate | Wilson 95% interval |
|---|---:|---:|---:|
| advanced | 41/120 | 34.2% | 26.3%–43.0% |
| baseline | 27/120 | 22.5% | 16.0%–30.8% |

Advanced: median game length 21 turns; 0 false accusations.

Baseline: median game length 21 turns; 0 false accusations.

The advanced strategy uses sampled information gain. Its randomized feasible-deal sampler is not a calibrated posterior. No sample frequency is accepted as accusation proof.

## Secret Dictator

The first 120-game comparison gave 52/120 wins for the advanced seat and 54/120 for the baseline. The strategy was then adjusted to use observed voting permissiveness when deciding whether early dictator camouflage was useful.

Held-out evaluation: seed 10000, 600 games per mode, 5–10 players, cycling the selected seat. One advanced player sits among simple baseline players. The baseline table usually approves governments and has no discussion phase.

| Selected seat strategy | Team wins/games | Team win rate | Wilson 95% interval |
|---|---:|---:|---:|
| advanced | 262/600 | 43.7% | 39.8%–47.7% |
| baseline | 256/600 | 42.7% | 38.8%–46.7% |

| Private role | Advanced team wins | Baseline team wins |
|---|---:|---:|
| liberal | 53/358 | 51/358 |
| fascist | 131/153 | 128/153 |
| dictator | 78/89 | 77/89 |

**No reliable overall playing-strength advantage is established for Secret Dictator.** The difference is small and the intervals overlap. Role strategy, teammate behavior and negotiation matter; stronger populations and the actual challenge environment are needed before claiming an improvement.

## Reproduce

```powershell
python scripts/benchmark.py --games 120 --time-ms 60 --output reports/benchmark-final.json
python scripts/evaluate_secret_dictator.py --games 600 --seed 10000
python scripts/summarize_reports.py
python scripts/validate.py
```

Seeds make deals and baseline randomness repeatable. Wall-clock search and deduction budgets can change decisions across runs/machines. The general benchmark preserves the earlier pre-permissiveness Secret Dictator comparison; use the held-out report for the current Secret Dictator version. Runtime guards added after the general benchmark do not change legal game decisions.

Raw data: `benchmark-initial.json`, `benchmark-final.json`, `secret-dictator-heldout.json`. Correctness and packaging evidence: `validation.json` and `../dist/manifest.json`.
