"""Held-out seeded role-by-role evaluation for the Secret Dictator heuristic."""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents.arenas import SecretDictatorArena
from benchmark import summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=600)
    parser.add_argument("--seed", type=int, default=10000)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "secret-dictator-heldout.json")
    args = parser.parse_args()
    if args.games < 1:
        parser.error("games must be positive")
    started = perf_counter()
    source_digest = hashlib.sha256()
    for path in sorted((ROOT / "agents").glob("*.py")):
        source_digest.update(path.name.encode())
        source_digest.update(path.read_bytes())
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "seed": args.seed,
              "source_sha256": source_digest.hexdigest(),
              "scope": "one advanced seat among simple always-approve baselines; assumed local rules; no discussion",
              "modes": {}}
    for mode in ("advanced", "baseline"):
        records, by_role, by_players = [], defaultdict(list), defaultdict(list)
        for i in range(args.games):
            players = 5 + i % 6
            seat = (i // 6) % players
            arena = SecretDictatorArena(args.seed + i, players, [seat] if mode == "advanced" else [])
            result = arena.run()
            role = result["roles"][seat]
            team = "liberal" if role == "liberal" else "fascist"
            result.update({"seed": args.seed + i, "agent_seat": seat, "agent_role": role, "players": players,
                           "outcome": "unfinished" if not result["finished"] else "win" if result["winner"] == team else "loss"})
            records.append(result)
            by_role[role].append(result)
            by_players[str(players)].append(result)
        report["modes"][mode] = {"summary": summarize(records), "by_role": {k: summarize(v) for k, v in by_role.items()},
                                    "by_players": {k: summarize(v) for k, v in by_players.items()}, "records": records}
        print(mode, json.dumps(report["modes"][mode]["summary"]), flush=True)
    report["elapsed_seconds"] = perf_counter() - started
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
