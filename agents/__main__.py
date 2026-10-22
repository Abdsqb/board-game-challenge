"""One JSON request per input line, one JSON response per output line."""

import argparse
import json
import sys
from .protocol import decide, parse_line, MAX_LINE_BYTES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", choices=("connect4", "clue", "secret-dictator"))
    parser.add_argument("--action-only", action="store_true", help="return only the action object")
    args = parser.parse_args()
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    while True:
        line = sys.stdin.readline(MAX_LINE_BYTES + 2)
        if not line:
            break
        if not line.strip():
            continue
        oversized = len(line.encode("utf-8")) > MAX_LINE_BYTES
        if oversized and not line.endswith("\n"):
            # Drain the rejected message so its tail cannot become a new request.
            while True:
                tail = sys.stdin.readline(MAX_LINE_BYTES + 2)
                if not tail or tail.endswith("\n"):
                    break
        try:
            if oversized:
                raise ValueError("request exceeds the local 2 MB size limit")
            result = decide(parse_line(line), args.game)
            if args.action_only:
                result = result["action"]
        except (ValueError, TypeError, KeyError, IndexError, OverflowError, RecursionError) as error:
            result = {"error": {"type": "invalid_request", "message": str(error)}}
        print(json.dumps(result, separators=(",", ":"), allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
