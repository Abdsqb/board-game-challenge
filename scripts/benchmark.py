"""Reproducible local evaluation. Does not predict a challenge leaderboard."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from math import sqrt
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents.arenas import play_connect4, play_clue, SecretDictatorArena


def interval(wins, games):
    if not games:
        return None
    z = 1.96
    p = wins / games
    denominator = 1 + z * z / games
    center = (p + z * z / (2 * games)) / denominator
    half = z * sqrt((p * (1 - p) + z * z / (4 * games)) / games) / denominator
    return [round(center - half, 4), round(center + half, 4)]


def summarize(records):
    counts = Counter(r["outcome"] for r in records)
    return {"games": len(records), **dict(counts), "win_rate": counts["win"] / len(records) if records else None,
            "win_rate_wilson_95": interval(counts["win"], len(records))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=30, help="games per C4 opponent and per other game")
    parser.add_argument("--time-ms", type=float, default=40)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "benchmark.json")
    args = parser.parse_args()
    if args.games < 1 or args.time_ms <= 0:
        parser.error("games and time-ms must be positive")
    started = perf_counter()
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "seed": args.seed, "requested_move_budget_ms": args.time_ms,
              "scope": "local assumptions only; Clue has no mansion movement; Secret Dictator has no discussion",
              "connect4": {}, "clue": {}, "secret_dictator": {}}
    for opponent in ("random", "tactical", "greedy"):
        records, timings = [], []
        for i in range(args.games):
            result = play_connect4(args.seed + i, 1 + i % 2, opponent, args.time_ms)
            result["outcome"] = "draw" if result["winner"] is None else "win" if result["winner"] == result["agent_seat"] else "loss"
            timings += result.pop("agent_move_ms")
            records.append(result)
        report["connect4"][opponent] = {"summary": summarize(records), "records": records,
                                           "median_move_ms": statistics.median(timings), "max_move_ms": max(timings)}
        print(f"Connect4 / {opponent}: {report['connect4'][opponent]['summary']}", flush=True)
    for mode in ("advanced", "baseline"):
        records = []
        for i in range(args.games):
            players = 3 + i % 4
            result = play_clue(args.seed + i, players, i % players, args.time_ms, samples=48, advanced=mode == "advanced")
            result["outcome"] = "unfinished" if not result["finished"] else "win" if result["winner"] == result["agent_seat"] else "loss"
            result["players"] = players
            records.append(result)
        report["clue"][mode] = {"summary": summarize(records), "records": records,
                                   "median_turns": statistics.median(r["turns"] for r in records),
                                   "false_accusations": sum(r["false_accusations"] for r in records)}
        print(f"Clue / {mode}: {report['clue'][mode]['summary']}", flush=True)
    for mode in ("advanced", "baseline"):
        records, by_role = [], defaultdict(list)
        for i in range(args.games):
            players = 5 + i % 6
            seat = i % players
            arena = SecretDictatorArena(args.seed + i, players, [seat] if mode == "advanced" else [])
            result = arena.run()
            role = result["roles"][seat]
            team = "liberal" if role == "liberal" else "fascist"
            result.update({"agent_seat": seat, "agent_role": role, "players": players,
                           "outcome": "unfinished" if not result["finished"] else "win" if result["winner"] == team else "loss"})
            records.append(result)
            by_role[role].append(result)
        report["secret_dictator"][mode] = {"summary": summarize(records), "by_role": {k: summarize(v) for k, v in by_role.items()},
                                              "records": records}
        print(f"Secret Dictator / {mode}: {report['secret_dictator'][mode]['summary']}", flush=True)
    report["elapsed_seconds"] = perf_counter() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {args.output}", flush=True)


if __name__ == "__main__":
    main()
