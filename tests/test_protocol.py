import json
from pathlib import Path
import subprocess
import sys
import unittest

from agents.protocol import decide, parse_line

ROOT = Path(__file__).resolve().parents[1]


class ProtocolTests(unittest.TestCase):
    def test_all_examples_are_executable(self):
        for path in (ROOT / "examples").glob("*.jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                response = decide(parse_line(line))
                self.assertIn("action", response)
                self.assertEqual(response["protocol_version"], 1)

    def test_action_only_has_no_diagnostics(self):
        request = {"game": "connect4", "observation": {"moves": [0, 1, 0, 1, 0, 2]}}
        result = subprocess.run([sys.executable, "-m", "agents", "--game", "connect4", "--action-only"],
                                cwd=ROOT, input=json.dumps(request) + "\n", capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"type": "drop", "column": 0})

    def test_error_then_valid_message_in_same_process(self):
        valid = json.dumps({"game": "connect4", "observation": {"moves": [0, 1, 0, 1, 0, 2]}})
        result = subprocess.run([sys.executable, "-m", "agents"], cwd=ROOT,
                                input="not-json\n{}\n" + valid + "\n", capture_output=True, text=True, timeout=10)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(responses), 3)
        self.assertIn("error", responses[0])
        self.assertIn("error", responses[1])
        self.assertEqual(responses[2]["action"]["column"], 0)

    def test_invalid_interface_and_nonfinite_json(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(ValueError):
                parse_line('{"x":' + value + '}')
        with self.assertRaises(ValueError):
            decide({"game": "clue", "observation": {}}, "connect4")
        with self.assertRaises(ValueError):
            decide({"protocol_version": 2, "game": "connect4", "observation": {"moves": []}})
        with self.assertRaises(ValueError):
            decide({"game": "connect4", "observation": {"moves": [], "board": []}})

    def test_malformed_shapes_and_limits_return_errors_without_crashing(self):
        requests = [
            {"game": "clue", "observation": {"history": ["bad"]}},
            {"game": "clue", "observation": {"categories": ["suspect", "weapon", "room"]}},
            {"game": "secret-dictator", "observation": {"known_roles": []}},
            {"game": "secret-dictator", "observation": {"legal_actions": "vote"}},
            {"game": "secret-dictator", "observation": {"players": 5, "me": 0, "role": "liberal",
               "history": [{"type": "election", "votes": [True]}], "legal_actions": [{"type": "pass"}]}},
            {"game": "connect4", "observation": {"moves": []}, "limits": {"time_ms": 0}},
            {"game": "connect4", "observation": {"moves": []}, "limits": {"max_depth": 1.5}},
        ]
        result = subprocess.run([sys.executable, "-m", "agents"], cwd=ROOT,
                                input="".join(json.dumps(r) + "\n" for r in requests),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(responses), len(requests))
        self.assertTrue(all("error" in r for r in responses))


if __name__ == "__main__":
    unittest.main()
