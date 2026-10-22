"""Human-playable Connect Four or a narrated local deduction-game simulation."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents.connect4 import Connect4Agent, Position
from agents.arenas import play_clue, SecretDictatorArena


def display(position):
    symbols = (".", "X", "O")
    print("\n  " + " ".join(str(c + 1) for c in range(7)))
    for row in position.rows():
        print("  " + " ".join(symbols[value] for value in row))
    print()


def play_connect4(human_first=True, time_ms=500):
    human = 1 if human_first else 2
    agent, position = Connect4Agent(time_limit_ms=time_ms), Position()
    print("Connect 4: you are " + ("X" if human == 1 else "O") + ". Enter a column 1-7, or q to quit.")
    while position.legal_moves():
        display(position)
        if position.player == human:
            try:
                answer = input("Your column: ").strip()
            except EOFError:
                return
            if answer.lower() in ("q", "quit", "exit"):
                return
            try:
                column = int(answer) - 1
                position = position.play(column)
            except ValueError as error:
                print(f"Choose a legal column. {error}")
        else:
            result = agent.choose(position)
            print(f"Agent plays {result.column + 1} (completed depth {result.depth}).")
            position = position.play(result.column)
    display(position)
    winner = position.winner()
    print("Draw." if winner is None else "You win." if winner == human else "Agent wins.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", choices=("connect4", "clue", "secret-dictator"))
    parser.add_argument("--second", action="store_true", help="human plays second in Connect 4")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--players", type=int)
    parser.add_argument("--time-ms", type=float, default=500)
    args = parser.parse_args()
    if args.game == "connect4":
        play_connect4(not args.second, args.time_ms)
    elif args.game == "clue":
        print("Clue deduction-only simulation; omits the mansion board and dice. The advanced agent is seat 0.")
        print(json.dumps(play_clue(seed=args.seed, players=args.players or 4, time_ms=args.time_ms), indent=2))
    else:
        print("Secret Dictator simulation using the assumed Secret Hitler-style rules. No discussion phase.")
        arena = SecretDictatorArena(seed=args.seed, players=args.players or 7, advanced_seats=[0])
        print(json.dumps(arena.run(), indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExited.")
