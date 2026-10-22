import unittest
from agents.secret_dictator import infer, role_counts, role_worlds, SecretDictatorAgent


def observation(**extra):
    return {"players": 5, "me": 0, "role": "liberal", "history": [],
            "fascist_policies": 0, "liberal_policies": 0, **extra}


class SecretDictatorTests(unittest.TestCase):
    def test_role_counts_and_worlds(self):
        expected = {5: (3, 1), 6: (4, 1), 7: (4, 2), 8: (5, 2), 9: (5, 3), 10: (6, 3)}
        for n, (liberals, fascists) in expected.items():
            counts = role_counts(n)
            self.assertEqual(counts, {"liberal": liberals, "fascist": fascists, "dictator": 1})
            for world in role_worlds(n):
                self.assertEqual({r: world.count(r) for r in counts}, counts)

    def test_prior_and_normalization(self):
        beliefs = infer(observation())
        self.assertAlmostEqual(sum(beliefs.weights), 1)
        self.assertAlmostEqual(beliefs.marginals[0]["liberal"], 1)
        self.assertAlmostEqual(beliefs.marginals[1]["dictator"], .25)
        self.assertAlmostEqual(beliefs.marginals[1]["fascist"], .25)
        for marginal in beliefs.marginals:
            self.assertAlmostEqual(sum(marginal.values()), 1)

    def test_non_dictator_does_not_mean_liberal(self):
        beliefs = infer(observation(history=[{"type": "non_dictator", "player": 1}]))
        self.assertEqual(beliefs.marginals[1]["dictator"], 0)
        self.assertGreater(beliefs.marginals[1]["fascist"], 0)

    def test_verified_investigation_and_claim_are_different(self):
        fact = {"type": "investigation_result", "observer": 0, "target": 1, "party": "fascist"}
        self.assertEqual(infer(observation(history=[fact])).marginals[1]["liberal"], 0)
        claim = {"type": "investigation_claim", "speaker": 2, "target": 1, "party": "fascist"}
        self.assertGreater(infer(observation(history=[claim])).marginals[1]["liberal"], 0)

    def test_other_players_private_information_rejected(self):
        with self.assertRaises(ValueError):
            infer(observation(history=[{"type": "investigation_result", "observer": 2, "target": 1, "party": "fascist"}]))

    def test_policy_outcome_never_proves_a_role(self):
        beliefs = infer(observation(history=[{"type": "policy", "president": 1, "chancellor": 2, "policy": "F"}]))
        self.assertGreater(beliefs.marginals[1]["liberal"], 0)
        self.assertGreater(beliefs.marginals[1]["fascist"], 0)

    def test_private_mixed_pair_is_stronger_evidence_than_public_outcome(self):
        event = {"type": "policy", "president": 0, "chancellor": 1, "policy": "F"}
        public = infer(observation(history=[event])).marginals[1]["liberal"]
        private = infer(observation(history=[{**event, "observer": 0, "passed_hand": ["L", "F"]}])).marginals[1]["liberal"]
        self.assertLess(private, public)

    def test_private_forced_pair_is_not_evidence_of_sabotage(self):
        event = {"type": "policy", "president": 0, "chancellor": 1, "policy": "F",
                 "observer": 0, "passed_hand": ["F", "F"]}
        self.assertAlmostEqual(infer(observation(history=[event])).marginals[1]["liberal"], .5)

    def test_private_legislative_leak_is_rejected(self):
        event = {"type": "policy", "president": 1, "chancellor": 2, "policy": "F",
                 "observer": 1, "passed_hand": ["F", "F"]}
        with self.assertRaises(ValueError):
            infer(observation(history=[event]))

    def test_immediate_dictator_nomination(self):
        ob = observation(role="fascist", known_roles={"3": "dictator"}, fascist_policies=3,
                         legal_actions=[{"type": "nominate", "target": 1}, {"type": "nominate", "target": 3}])
        self.assertEqual(SecretDictatorAgent().choose(ob)["action"]["target"], 3)

    def test_never_execute_known_dictator_on_own_team(self):
        ob = observation(role="fascist", known_roles={"3": "dictator"},
                         legal_actions=[{"type": "execute", "target": 3}, {"type": "execute", "target": 1}])
        self.assertEqual(SecretDictatorAgent().choose(ob)["action"]["target"], 1)

    def test_liberal_blocks_known_dictator_election(self):
        ob = observation(fascist_policies=3, president=1, chancellor=2, known_roles={"2": "dictator"},
                         legal_actions=[{"type": "vote", "approve": True}, {"type": "vote", "approve": False}])
        self.assertFalse(SecretDictatorAgent().choose(ob)["action"]["approve"])

    def test_policies_and_veto(self):
        agent = SecretDictatorAgent()
        actions = [{"type": "enact", "policy": "F"}, {"type": "enact", "policy": "L"}]
        self.assertEqual(agent.choose(observation(legal_actions=actions))["action"]["policy"], "L")
        self.assertEqual(agent.choose(observation(role="fascist", liberal_policies=4, legal_actions=actions))["action"]["policy"], "F")
        veto = [{"type": "request_veto"}, {"type": "enact", "policy": "F"}]
        self.assertEqual(agent.choose(observation(fascist_policies=5, hand=["F", "F"], legal_actions=veto))["action"]["type"], "request_veto")

    def test_dictator_adapts_policy_to_observed_voting_resistance(self):
        actions = [{"type": "enact", "policy": "F"}, {"type": "enact", "policy": "L"}]
        cautious = observation(role="dictator", legal_actions=actions)
        self.assertEqual(SecretDictatorAgent().choose(cautious)["action"]["policy"], "L")
        approving = [{"type": "election", "votes": {str(p): True for p in range(5)}} for _ in range(2)]
        self.assertEqual(SecretDictatorAgent().choose({**cautious, "history": approving})["action"]["policy"], "F")
        resistant = [{"type": "election", "votes": {"0": True, "1": True, "2": False, "3": False, "4": False}} for _ in range(2)]
        self.assertEqual(SecretDictatorAgent().choose({**cautious, "history": resistant})["action"]["policy"], "L")


if __name__ == "__main__":
    unittest.main()
