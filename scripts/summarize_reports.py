"""Generate an honest short summary from measured JSON reports."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pct(value):
    return f"{100 * value:.1f}%"


def row(label, summary):
    lo, hi = summary["win_rate_wilson_95"]
    return f"| {label} | {summary.get('win', 0)}/{summary['games']} | {pct(summary['win_rate'])} | {pct(lo)}–{pct(hi)} |"


def main():
    report = json.loads((ROOT / "reports" / "benchmark-final.json").read_text(encoding="utf-8"))
    heldout = json.loads((ROOT / "reports" / "secret-dictator-heldout.json").read_text(encoding="utf-8"))
    lines = ["# Measured local results", "",
             "These are measured results from the local assumptions, not competition results or proof of optimal play.", "",
             "## Connect 4", "", f"Requested search budget: {report['requested_move_budget_ms']:g} ms; 120 games per opponent, alternating first/second seat.", "",
             "| Opponent | Wins/games | Win rate | Wilson 95% interval |", "|---|---:|---:|---:|"]
    lines += [row(name, value["summary"]) for name, value in report["connect4"].items()]
    total_games = sum(v["summary"]["games"] for v in report["connect4"].values())
    total_wins = sum(v["summary"].get("win", 0) for v in report["connect4"].values())
    lines += ["", f"Combined: {total_wins}/{total_games} wins. The opponents are local random, one-turn tactical and greedy strategies; none is a full solver.", "",
              "| Opponent | Median search ms | Maximum search ms |", "|---|---:|---:|"]
    lines += [f"| {name} | {value['median_move_ms']:.1f} | {value['max_move_ms']:.1f} |" for name, value in report["connect4"].items()]
    lines += ["", "Time checks are cooperative. Recorded maxima include interpreter/check-interval overhead and scheduling delays; do not set the requested budget equal to an organizer's hard limit.", "",
              "## Clue deduction arena", "", "120 games per mode; 3–6 players, varying seats. Physical mansion movement is omitted.", "",
              "| Selected seat strategy | Wins/games | Win rate | Wilson 95% interval |", "|---|---:|---:|---:|"]
    lines += [row(name, report["clue"][name]["summary"]) for name in ("advanced", "baseline")]
    for mode in ("advanced", "baseline"):
        value = report["clue"][mode]
        lines += ["", f"{mode.capitalize()}: median game length {value['median_turns']:g} turns; {value['false_accusations']} false accusations."]
    lines += ["", "The advanced strategy uses sampled information gain. Its randomized feasible-deal sampler is not a calibrated posterior. No sample frequency is accepted as accusation proof.", "",
              "## Secret Dictator", "", "The first 120-game comparison gave 52/120 wins for the advanced seat and 54/120 for the baseline. The strategy was then adjusted to use observed voting permissiveness when deciding whether early dictator camouflage was useful.", "",
              f"Held-out evaluation: seed {heldout['seed']}, 600 games per mode, 5–10 players, cycling the selected seat. One advanced player sits among simple baseline players. The baseline table usually approves governments and has no discussion phase.", "",
              "| Selected seat strategy | Team wins/games | Team win rate | Wilson 95% interval |", "|---|---:|---:|---:|"]
    lines += [row(name, heldout["modes"][name]["summary"]) for name in ("advanced", "baseline")]
    lines += ["", "| Private role | Advanced team wins | Baseline team wins |", "|---|---:|---:|"]
    for role in ("liberal", "fascist", "dictator"):
        a = heldout["modes"]["advanced"]["by_role"].get(role, {})
        b = heldout["modes"]["baseline"]["by_role"].get(role, {})
        lines += [f"| {role} | {a.get('win', 0)}/{a.get('games', 0)} | {b.get('win', 0)}/{b.get('games', 0)} |"]
    lines += ["", "**No reliable overall playing-strength advantage is established for Secret Dictator.** The difference is small and the intervals overlap. Role strategy, teammate behavior and negotiation matter; stronger populations and the actual challenge environment are needed before claiming an improvement.", "",
              "## Reproduce", "", "```powershell", "python scripts/benchmark.py --games 120 --time-ms 60 --output reports/benchmark-final.json", "python scripts/evaluate_secret_dictator.py --games 600 --seed 10000", "python scripts/summarize_reports.py", "python scripts/validate.py", "```", "",
              "Seeds make deals and baseline randomness repeatable. Wall-clock search and deduction budgets can change decisions across runs/machines. The general benchmark preserves the earlier pre-permissiveness Secret Dictator comparison; use the held-out report for the current Secret Dictator version. Runtime guards added after the general benchmark do not change legal game decisions.", "",
              "Raw data: `benchmark-initial.json`, `benchmark-final.json`, `secret-dictator-heldout.json`. Correctness and packaging evidence: `validation.json` and `../dist/manifest.json`.", ""]
    (ROOT / "reports" / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print("Updated reports/RESULTS.md")


if __name__ == "__main__":
    main()
