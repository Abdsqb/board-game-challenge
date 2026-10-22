"""Role-aware agent for an explicitly assumed Secret Hitler-style local ruleset.

Exact enumeration handles role counts and verified facts. Behavioral likelihoods
are heuristic opponent models, not calibrated probabilities or logical proofs.
Only structured observations are interpreted; player chat is untrusted data.
"""

from dataclasses import dataclass
from itertools import combinations
from math import comb, exp, log, log2

ROLES = ("liberal", "fascist", "dictator")


def role_counts(players):
    if type(players) is not int or not 5 <= players <= 10:
        raise ValueError("local rules support 5 through 10 players")
    fascists = (players - 3) // 2
    return {"liberal": players - fascists - 1, "fascist": fascists, "dictator": 1}


def role_worlds(players):
    counts = role_counts(players)
    for dictator in range(players):
        others = [p for p in range(players) if p != dictator]
        for fascists in combinations(others, counts["fascist"]):
            world = ["liberal"] * players
            world[dictator] = "dictator"
            for p in fascists:
                world[p] = "fascist"
            yield tuple(world)


def party(role):
    return "liberal" if role == "liberal" else "fascist"


def sabotage_rate(role, fascist_policies=0, liberal_policies=0):
    if role == "liberal":
        return .02  # Small noise keeps behavioral evidence from becoming certainty.
    if liberal_policies >= 4 or fascist_policies >= 4:
        return .98
    if role == "dictator":
        return .3 if fascist_policies < 3 else .7
    return .85


def fascist_policy_likelihood(president_role, chancellor_role, event):
    liberal = int(event.get("pool_liberal", 6))
    fascist = int(event.get("pool_fascist", 11))
    if liberal < 0 or fascist < 0 or liberal + fascist < 3:
        raise ValueError("invalid public policy pool")
    fp, lp = event.get("fascist_before", 0), event.get("liberal_before", 0)
    qp, qc = sabotage_rate(president_role, fp, lp), sabotage_rate(chancellor_role, fp, lp)
    denominator = comb(liberal + fascist, 3)
    result = 0.0
    for count_l in range(4):
        count_f = 3 - count_l
        if count_l > liberal or count_f > fascist:
            continue
        chance = comb(liberal, count_l) * comb(fascist, count_f) / denominator
        enact_f = 1 if count_l == 0 else 0 if count_l == 3 else qp + (1 - qp) * qc if count_l == 1 else qp * qc
        result += chance * enact_f
    return result


def private_policy_likelihood(world, me, event):
    """Condition on policy cards genuinely observed in a legislative session.

    A president knows the passed pair. A chancellor knows that pair but not the
    original draw; observing it changes the likelihood of presidential filtering.
    """
    hand = event["passed_hand"]
    if len(hand) != 2 or any(p not in ("L", "F") for p in hand):
        raise ValueError("private passed_hand must contain exactly two policies")
    president, chancellor = event["president"], event["chancellor"]
    if event.get("observer") != me or me not in (president, chancellor):
        raise ValueError("another player's private legislative cards are not observable")
    if event["policy"] not in hand:
        raise ValueError("enacted policy cannot come from the recorded passed hand")
    fp, lp = event.get("fascist_before", 0), event.get("liberal_before", 0)
    count_passed_l = hand.count("L")
    chance_f = (1 if count_passed_l == 0 else 0 if count_passed_l == 2
                else sabotage_rate(world[chancellor], fp, lp))
    enact = chance_f if event["policy"] == "F" else 1 - chance_f
    if me == president:
        return enact
    liberal, fascist = int(event.get("pool_liberal", 6)), int(event.get("pool_fascist", 11))
    if liberal < 0 or fascist < 0 or liberal + fascist < 3:
        raise ValueError("invalid public policy pool")
    qp = sabotage_rate(world[president], fp, lp)
    observed_pair = 0.0
    for count_l in range(4):
        if count_l > liberal or 3 - count_l > fascist:
            continue
        chance = comb(liberal, count_l) * comb(fascist, 3 - count_l) / comb(liberal + fascist, 3)
        if count_l == 0:
            observed_pair += chance * (count_passed_l == 0)
        elif count_l == 3:
            observed_pair += chance * (count_passed_l == 2)
        else:
            observed_pair += chance * (qp * (count_passed_l == count_l - 1)
                                      + (1 - qp) * (count_passed_l == count_l))
    return observed_pair * enact


@dataclass
class Beliefs:
    worlds: list[tuple[str, ...]]
    weights: list[float]
    marginals: list[dict[str, float]]

    def joint_fascist(self, a, b):
        return sum(w for world, w in zip(self.worlds, self.weights)
                   if world[a] != "liberal" and world[b] != "liberal")


def infer(observation):
    players, me, role = observation["players"], observation["me"], observation["role"]
    role_counts(players)
    if type(me) is not int or not 0 <= me < players or role not in ROLES:
        raise ValueError("invalid seat or private role")

    def seat(value):
        if type(value) is not int or not 0 <= value < players:
            raise ValueError("unknown player seat")
        return value

    known = {me: role}
    for key, value in observation.get("known_roles", {}).items():
        p = seat(int(key))
        if value not in ROLES or p in known and known[p] != value:
            raise ValueError("contradictory known role")
        known[p] = value
    facts, soft = [], []
    for event in observation.get("history", []):
        kind = event.get("type")
        if kind == "investigation_result":
            if event["observer"] != me:
                raise ValueError("another player's private investigation is not observable")
            p, result = seat(event["target"]), event["party"]
            if result not in ("liberal", "fascist"):
                raise ValueError("invalid party")
            facts.append(("party", p, result))
        elif kind == "non_dictator":
            facts.append(("non_dictator", seat(event["player"]), None))
        elif kind == "policy":
            seat(event["president"])
            seat(event["chancellor"])
            if event["policy"] not in ("L", "F"):
                raise ValueError("invalid policy")
            soft.append(event)
        elif kind == "investigation_claim":
            seat(event["speaker"])
            seat(event["target"])
            if event["party"] not in ("liberal", "fascist"):
                raise ValueError("invalid party claim")
            soft.append(event)
        elif kind == "election":
            votes = event.get("votes", {})
            if not isinstance(votes, dict) or any(type(value) is not bool for value in votes.values()):
                raise ValueError("election votes must map seats to booleans")
            for key in votes:
                seat(int(key))
        elif kind in ("chaos", "veto", "peek", "chat"):
            # Public votes/chat are retained by the runner but are not hard facts.
            continue
        else:
            raise ValueError(f"unsupported Secret Dictator event: {kind}")
    worlds, logs = [], []
    for world in role_worlds(players):
        if any(world[p] != value for p, value in known.items()):
            continue
        if any((party(world[p]) != value if kind == "party" else world[p] == "dictator")
               for kind, p, value in facts):
            continue
        score = 0.0
        for event in soft:
            if event["type"] == "policy":
                if "passed_hand" in event:
                    likelihood = private_policy_likelihood(world, me, event)
                else:
                    chance = fascist_policy_likelihood(world[event["president"]], world[event["chancellor"]], event)
                    likelihood = chance if event["policy"] == "F" else 1 - chance
                # A misspecified behavior/deck model must never rule out a role world.
                score += log(max(.02, min(.98, likelihood)))
            else:
                truthful = party(world[event["target"]]) == event["party"]
                reliability = .92 if world[event["speaker"]] == "liberal" else .5
                score += .6 * log(reliability if truthful else 1 - reliability)
        worlds.append(world)
        logs.append(score)
    if not worlds:
        raise ValueError("private knowledge and verified facts admit no role assignment")
    peak = max(logs)
    weights = [exp(value - peak) for value in logs]
    total = sum(weights)
    weights = [value / total for value in weights]
    marginals = [{role_name: sum(w for world, w in zip(worlds, weights) if world[p] == role_name)
                  for role_name in ROLES} for p in range(players)]
    return Beliefs(worlds, weights, marginals)


class SecretDictatorAgent:
    def choose(self, observation):
        beliefs = infer(observation)
        actions = observation.get("legal_actions")
        if not isinstance(actions, list) or not actions:
            raise ValueError("the runner must supply a nonempty legal_actions list")
        role, me = observation["role"], observation["me"]
        evil = role != "liberal"
        fp, lp = observation.get("fascist_policies", 0), observation.get("liberal_policies", 0)
        tracker = observation.get("election_tracker", 0)
        votes = [approve for event in observation.get("history", []) if event.get("type") == "election"
                 for approve in event.get("votes", {}).values() if type(approve) is bool]
        # Reputation has less value at a table that repeatedly approves everyone.
        # Keep the cautious dictator default until there is actual voting evidence.
        permissive_table = len(votes) >= 2 * observation["players"] and sum(votes) / len(votes) >= .9

        def p_f(p):
            return 1 - beliefs.marginals[p]["liberal"]

        def p_d(p):
            return beliefs.marginals[p]["dictator"]

        def score(action):
            kind = action["type"]
            if kind in ("nominate", "special_election", "execute", "investigate"):
                p = action["target"]
                if type(p) is not int or not 0 <= p < observation["players"] or p == me:
                    raise ValueError("invalid target in supplied legal action")
            if kind == "nominate":
                if evil:
                    if fp >= 3:
                        return 20 * p_d(p) + 1.5 * p_f(p)
                    # Build a plausible candidate's reputation before the win gate.
                    return .55 * p_d(p) + .3 * p_f(p)
                return 1 - p_f(p) - (5 * p_d(p) if fp >= 3 else .1 * p_d(p))
            if kind == "vote":
                president, chancellor = observation["president"], observation["chancellor"]
                if type(action.get("approve")) is not bool:
                    raise ValueError("vote approve must be a boolean")
                risk = p_d(chancellor) if fp >= 3 else 0
                both_good = 1 - p_f(president) - p_f(chancellor) + beliefs.joint_fascist(president, chancellor)
                if evil:
                    advantage = (5 * risk + .65 * (p_f(president) + p_f(chancellor)) - .55)
                    if role == "dictator" and fp < 3:
                        advantage = .35 + .2 * p_f(chancellor)
                else:
                    advantage = both_good - .32 - 3.5 * risk
                    if tracker == 2:
                        # Chaos advances a random policy; don't reject harmless governments forever.
                        advantage += .35 if fp < 5 else .12
                    if fp >= 5:
                        advantage -= .22 * (1 - both_good)
                return advantage if action["approve"] else -advantage
            if kind in ("discard", "enact"):
                policy = action["policy"]
                if policy not in ("L", "F"):
                    raise ValueError("policy must be L or F")
                prefer_f = evil and (role != "dictator" or fp >= 3 or lp >= 4 or permissive_table)
                preferred = "F" if prefer_f else "L"
                # Discard the opposite of the policy we want the government to enact.
                if kind == "discard":
                    preferred = "L" if prefer_f else "F"
                urgency = 10 if (fp >= 5 or lp >= 4) else 2
                return urgency if policy == preferred else -urgency
            if kind == "execute":
                if evil:
                    return 2 * (1 - p_f(p)) - 100 * p_d(p)
                return 8 * p_d(p) + p_f(p)
            if kind == "investigate":
                probability = p_f(p)
                entropy = -sum(x * log2(x) for x in (probability, 1 - probability) if x > 0)
                return entropy + .25 * p_d(p) if not evil else 1 - p_f(p)
            if kind == "special_election":
                return (p_f(p) - .5 * p_d(p)) if evil else 1 - p_f(p)
            if kind in ("request_veto", "respond_veto"):
                hand = observation.get("hand", [])
                if evil:
                    want_veto = bool(hand) and "F" not in hand
                else:
                    want_veto = bool(hand) and "L" not in hand
                if tracker == 2 and lp >= 4 and evil:
                    want_veto = False
                accept = action.get("approve", True)
                return 4 if accept == want_veto else -4
            if kind == "claim":
                # Structured optional public report; no private role is disclosed.
                return 1 if action.get("party", "liberal") == "liberal" else 0
            if kind == "pass":
                return -100
            raise ValueError(f"unsupported legal action: {kind}")

        ranked = [(score(action), i, action) for i, action in enumerate(actions)]
        value, _, action = max(ranked, key=lambda item: (item[0], -item[1]))
        return {"action": dict(action), "diagnostics": {
            "reason": "role_aware_heuristic", "score": round(value, 6),
            "feasible_role_worlds": len(beliefs.worlds),
            "marginals": beliefs.marginals,
            "probabilities": "exact_role_constraints_with_uncalibrated_behavior_likelihoods",
        }}
