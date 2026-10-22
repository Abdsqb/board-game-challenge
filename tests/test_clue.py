import random
import unittest
from time import perf_counter

from agents.clue import (Knowledge, ClueAgent, InconsistentEvidence, _Budget,
                         information_gain)

TOY = {"suspect": ["s1", "s2"], "weapon": ["w1", "w2"], "room": ["r1", "r2"]}


def toy_observation(**extra):
    return {"categories": TOY, "me": 0, "hand_sizes": [1, 1, 1],
            "own_hand": ["s1"], "history": [], **extra}


class ClueTests(unittest.TestCase):
    def test_own_hand_and_one_card_per_category(self):
        k = Knowledge(3, 0, [1, 1, 1], ["s1"], TOY)
        d = k.propagate()
        self.assertEqual(d[k.index["s1"]], 1)
        self.assertEqual(d[k.index["s2"]], 1 << k.envelope)
        self.assertTrue(all(not d[k.index[c]] & 1 for c in ("s2", "w1", "w2", "r1", "r2")))

    def test_passes_are_public_evidence(self):
        k = Knowledge(3, 0, [1, 1, 1], ["s1"], TOY)
        k.observe({"type": "suggestion", "suggester": 0, "cards": ["s2", "w2", "r2"], "responder": None})
        self.assertEqual(k.forced_envelope(k.propagate()), {"suspect": "s2", "weapon": "w2", "room": "r2"})

    def test_only_passers_before_responder_are_excluded(self):
        k = Knowledge(3, 0, [1, 1, 1], ["s1"], TOY)
        k.observe({"type": "suggestion", "suggester": 0, "cards": ["s2", "w1", "r1"], "responder": 1})
        self.assertTrue(k.domains[k.index["w1"]] & (1 << 2))

    def test_refutation_disjunction_and_hand_capacity(self):
        k = Knowledge(3, 0, [1, 1, 1], ["s1"], TOY)
        k.observe({"type": "suggestion", "suggester": 0, "cards": ["s2", "w1", "r1"], "responder": 1})
        k.observe({"type": "reveal", "owner": 2, "viewer": 0, "card": "r1"})
        d = k.propagate()
        self.assertEqual(d[k.index["w1"]], 1 << 1)
        self.assertEqual(k.forced_envelope(d), {"suspect": "s2", "weapon": "w2", "room": "r2"})

    def test_contradiction_is_not_silently_ignored(self):
        k = Knowledge(3, 0, [1, 1, 1], ["s1"], TOY)
        k.observe({"type": "reveal", "owner": 1, "viewer": 0, "card": "s1"})
        with self.assertRaises(InconsistentEvidence):
            k.propagate()

    def test_other_players_private_reveals_are_rejected(self):
        k = Knowledge(3, 0, [1, 1, 1], ["s1"], TOY)
        with self.assertRaises(ValueError):
            k.observe({"type": "reveal", "owner": 1, "viewer": 2, "card": "w1"})
        with self.assertRaises(ValueError):
            k.observe({"type": "suggestion", "suggester": 1, "cards": ["s2", "w1", "r1"],
                       "responder": 2, "shown_card": "w1"})

    def test_one_sample_does_not_authorize_accusation(self):
        result = ClueAgent(samples=1, time_limit_ms=100).choose(toy_observation())
        self.assertEqual(result["action"]["type"], "suggest")

    def test_proven_accusation(self):
        ob = toy_observation(history=[{"type": "suggestion", "suggester": 0,
                                       "cards": ["s2", "w2", "r2"], "responder": None}])
        result = ClueAgent().choose(ob)
        self.assertEqual(result["action"], {"type": "accuse", "suspect": "s2", "weapon": "w2", "room": "r2"})

    def test_legal_room_restriction_and_no_movement(self):
        agent = ClueAgent(samples=8, time_limit_ms=50)
        self.assertEqual(agent.choose(toy_observation(reachable_rooms=["r1"]))["action"]["room"], "r1")
        self.assertEqual(agent.choose(toy_observation(reachable_rooms=[]))["action"]["type"], "pass")
        action = agent.choose(toy_observation(reachable_rooms=[], legal_moves=[{"target_room": "r2", "distance": 1}]))["action"]
        self.assertEqual(action["type"], "move")

    def test_reuse_revealed_card(self):
        ob = {"me": 0, "hand_sizes": [6, 6, 6],
              "own_hand": ["scarlet", "mustard", "candlestick", "knife", "kitchen", "study"],
              "phase": "reveal", "suggester": 1, "suggestion": ["scarlet", "knife", "study"],
              "history": [{"type": "reveal", "owner": 0, "viewer": 1, "card": "knife"}]}
        self.assertEqual(ClueAgent().choose(ob)["action"]["card"], "knife")

    def test_feasible_samples_respect_constraints(self):
        k = Knowledge(3, 0, [1, 1, 1], ["s1"], TOY)
        budget = _Budget(perf_counter() + 1, 10000)
        rng = random.Random(5)
        worlds = [k.solve_one(k.propagate(), rng, budget) for _ in range(50)]
        for world in worlds:
            self.assertEqual([world.count(i) for i in range(4)], [1, 1, 1, 3])
            self.assertEqual(world[k.index["s1"]], 0)
            self.assertTrue(all(sum(world[i] == 3 for i in group) == 1 for group in k.groups))
        gain = information_gain(k, worlds, ("s1", "w1", "r1"))
        self.assertGreaterEqual(gain, 0)
        self.assertLessEqual(gain, 2.01)


if __name__ == "__main__":
    unittest.main()
