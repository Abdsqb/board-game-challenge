import unittest
from agents.arenas import SecretDictatorArena, play_clue, play_connect4


class ArenaTests(unittest.TestCase):
    def test_connect4_games_terminate_with_legal_actions(self):
        for seed in range(6):
            result = play_connect4(seed=seed, agent_seat=1 + seed % 2, time_ms=3)
            self.assertLessEqual(len(result["moves"]), 42)

    def test_clue_hides_private_cards_and_finishes(self):
        for seed in range(5):
            result = play_clue(seed=seed, players=3 + seed % 4, time_ms=15, samples=8)
            self.assertTrue(result["finished"], result)
            self.assertEqual(result["false_accusations"], 0)

    def test_secret_dictator_games_all_table_sizes(self):
        for players in range(5, 11):
            for seed in range(5):
                arena = SecretDictatorArena(seed=seed, players=players, advanced_seats=[seed % players])
                result = arena.run()
                self.assertTrue(result["finished"], result)
                arena._check_cards()

    def test_chaos_resets_term_limits_and_grants_no_power(self):
        arena = SecretDictatorArena(seed=0)
        arena.last_president, arena.last_chancellor = 0, 1
        arena.deck = ["F"] + ["L"] * 6 + ["F"] * 10
        arena.tracker = 2
        arena._failed_government()
        self.assertEqual(arena.fp, 1)
        self.assertEqual(arena.tracker, 0)
        self.assertIsNone(arena.last_president)
        self.assertIsNone(arena.last_chancellor)
        self.assertEqual(arena.investigated, set())
        arena._check_cards()

    def test_five_alive_only_previous_chancellor_is_limited(self):
        arena = SecretDictatorArena(players=7)
        arena.alive = [0, 1, 2, 3, 4]
        arena.president, arena.last_president, arena.last_chancellor = 0, 1, 2
        self.assertEqual(arena.eligible_chancellors(), [1, 3, 4])
        arena.alive.append(5)
        self.assertEqual(arena.eligible_chancellors(), [3, 4, 5])

    def test_special_election_returns_to_original_rotation(self):
        arena = SecretDictatorArena(players=7)
        arena.president = 2
        arena._advance(special_target=5)
        self.assertEqual(arena.president, 5)
        arena._advance()
        self.assertEqual(arena.president, 3)
        arena.president = 2
        arena._advance(special_target=3)
        arena._advance()
        self.assertEqual(arena.president, 3)

    def test_role_visibility_matches_assumed_rules(self):
        for players in (5, 7):
            arena = SecretDictatorArena(players=players)
            dictator = arena.roles.index("dictator")
            fascist = arena.roles.index("fascist")
            liberal = arena.roles.index("liberal")
            self.assertEqual(len(arena.observe(liberal, [])["known_roles"]), 1)
            self.assertEqual(len(arena.observe(dictator, [])["known_roles"]), 2 if players == 5 else 1)
            self.assertGreater(len(arena.observe(fascist, [])["known_roles"]), 1)

    def test_veto_chaos_with_empty_draw_pile(self):
        arena = SecretDictatorArena(seed=9, players=5)
        arena.roles = ["liberal", "liberal", "liberal", "fascist", "dictator"]
        arena.president = 0
        arena.fp, arena.tracker = 5, 2
        arena.deck = ["F", "F", "F"]
        arena.discard = ["L"] * 6 + ["F"] * 3

        def choose(me, actions, **context):
            kind = actions[0]["type"]
            if kind == "nominate":
                return next(a for a in actions if a["target"] == 1)
            if kind in ("vote", "respond_veto"):
                return next(a for a in actions if a["approve"])
            if any(a["type"] == "request_veto" for a in actions):
                return {"type": "request_veto"}
            return actions[0]

        arena.choose = choose
        arena._check_cards()
        arena.step()
        self.assertEqual(arena.tracker, 0)
        self.assertIsNone(arena.last_president)
        self.assertIsNone(arena.last_chancellor)
        self.assertEqual(len(arena.alive), 5)
        arena._check_cards()

    def test_legislative_private_pair_only_reaches_participants(self):
        arena = SecretDictatorArena(seed=10, players=5)
        arena.roles = ["liberal", "liberal", "liberal", "fascist", "dictator"]
        arena.president = 0

        def choose(me, actions, **context):
            if actions[0]["type"] == "nominate":
                return next(a for a in actions if a["target"] == 1)
            if actions[0]["type"] == "vote":
                return next(a for a in actions if a["approve"])
            return actions[0]

        arena.choose = choose
        arena.step()
        for p in range(5):
            policies = [e for e in arena.history[p] if e["type"] == "policy"]
            self.assertEqual(len(policies), 1)
            self.assertEqual("passed_hand" in policies[0], p in (0, 1))

    def test_all_advanced_tables_terminate(self):
        for players in (5, 7, 10):
            arena = SecretDictatorArena(seed=23, players=players, advanced_seats=range(players))
            self.assertTrue(arena.run()["finished"])


if __name__ == "__main__":
    unittest.main()
