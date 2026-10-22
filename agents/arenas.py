"""Seeded local evaluation environments, not challenge-platform emulators.

Connect Four is standard 7x6. Clue is a deduction-only arena: no mansion board,
dice or token relocation. Secret Dictator uses the documented assumed ruleset,
without a natural-language negotiation phase.
"""

from collections import Counter
from itertools import product
import random

from .clue import CATEGORIES, ClueAgent, Knowledge
from .connect4 import Position, Connect4Agent, COLUMNS, winning_cells, evaluate
from .secret_dictator import SecretDictatorAgent, role_counts, party


def connect4_baseline(position, rng, style="tactical"):
    legal = position.legal_moves()
    if style == "random":
        return rng.choice(legal)
    wins = winning_cells(position.current, position.occupied) & position.possible_mask()
    if wins:
        return next(c for c in legal if wins & COLUMNS[c])
    safe = position.safe_mask()
    candidates = [c for c in legal if safe & COLUMNS[c]] or legal
    if style == "greedy":
        return max(candidates, key=lambda c: -evaluate(position.play(c)))
    return rng.choice(candidates)


def play_connect4(seed=0, agent_seat=1, opponent="tactical", time_ms=25):
    rng = random.Random(seed)
    position, moves, timings, nodes = Position(), [], [], 0
    agent = Connect4Agent(time_limit_ms=time_ms)
    while position.legal_moves():
        if position.player == agent_seat:
            result = agent.choose(position)
            column = result.column
            timings.append(result.elapsed_ms)
            nodes += result.nodes
        else:
            column = connect4_baseline(position, rng, opponent)
        if column not in position.legal_moves():
            raise AssertionError("agent produced an illegal move")
        moves.append(column)
        position = position.play(column)
    return {"winner": position.winner(), "agent_seat": agent_seat, "moves": moves,
            "agent_move_ms": timings, "nodes": nodes}


def _clue_baseline(observation, rng):
    k = Knowledge(len(observation["hand_sizes"]), observation["me"], observation["hand_sizes"],
                  observation["own_hand"], observation.get("categories"))
    for event in observation["history"]:
        k.observe(event)
    domains = k.propagate()
    solution = k.forced_envelope(domains)
    if solution:
        return {"type": "accuse", **solution}
    chosen = []
    for name in k.category_names:
        eligible = observation["reachable_rooms"] if name == "room" else k.categories[name]
        candidates = [c for c in eligible if domains[k.index[c]] & (1 << k.envelope)] or eligible
        chosen.append(rng.choice(candidates))
    return {"type": "suggest", **dict(zip(k.category_names, chosen))}


def play_clue(seed=0, players=4, agent_seat=0, time_ms=60, samples=32, max_turns=250, advanced=True):
    if not 3 <= players <= 6 or not 0 <= agent_seat < players:
        raise ValueError("invalid local Clue table")
    rng = random.Random(seed)
    envelope = {name: rng.choice(cards) for name, cards in CATEGORIES.items()}
    deck = [card for cards in CATEGORIES.values() for card in cards if card not in envelope.values()]
    rng.shuffle(deck)
    hands = [deck[p::players] for p in range(players)]
    histories = [[] for _ in range(players)]
    last_room = [None] * players
    agent = ClueAgent(time_limit_ms=time_ms, samples=samples, seed=seed)
    false_accusations = 0
    out = set()
    for turn in range(max_turns):
        actor = turn % players
        if actor in out:
            continue
        ob = {"me": actor, "hand_sizes": [len(h) for h in hands], "own_hand": hands[actor],
              "history": histories[actor], "reachable_rooms": [r for r in CATEGORIES["room"] if r != last_room[actor]]}
        action = agent.choose(ob)["action"] if advanced and actor == agent_seat else _clue_baseline(ob, rng)
        if action["type"] == "accuse":
            guess = {name: action[name] for name in CATEGORIES}
            if guess == envelope:
                return {"winner": actor, "agent_seat": agent_seat, "turns": turn + 1,
                        "false_accusations": false_accusations, "finished": True}
            false_accusations += 1
            out.add(actor)
            continue
        if action["type"] != "suggest" or action["room"] not in ob["reachable_rooms"]:
            raise AssertionError("illegal local Clue action")
        last_room[actor] = action["room"]
        cards = [action[name] for name in ("suspect", "weapon", "room")]
        responder, shown = None, None
        for offset in range(1, players):
            seat = (actor + offset) % players
            held = [card for card in cards if card in hands[seat]]
            if held:
                responder = seat
                # All seats use the same minimal-disclosure refutation policy.
                reveal_ob = {"me": seat, "hand_sizes": [len(h) for h in hands], "own_hand": hands[seat],
                             "history": histories[seat], "phase": "reveal", "suggestion": cards, "suggester": actor}
                shown = agent.choose(reveal_ob)["action"]["card"]
                if shown not in held:
                    raise AssertionError("a revealed card was not held")
                break
        for viewer in range(players):
            event = {"type": "suggestion", "suggester": actor, "cards": cards.copy(), "responder": responder}
            if shown is not None and viewer in (actor, responder):
                event["shown_card"] = shown
            histories[viewer].append(event)
    return {"winner": None, "agent_seat": agent_seat, "turns": max_turns,
            "false_accusations": false_accusations, "finished": False}


POWER_TRACKS = {
    5: {3: "peek", 4: "execute", 5: "execute"},
    6: {3: "peek", 4: "execute", 5: "execute"},
    7: {2: "investigate", 3: "special_election", 4: "execute", 5: "execute"},
    8: {2: "investigate", 3: "special_election", 4: "execute", 5: "execute"},
    9: {1: "investigate", 2: "investigate", 3: "special_election", 4: "execute", 5: "execute"},
    10: {1: "investigate", 2: "investigate", 3: "special_election", 4: "execute", 5: "execute"},
}


class SecretDictatorArena:
    def __init__(self, seed=0, players=7, advanced_seats=(), max_rounds=200):
        self.rng = random.Random(seed)
        self.players, self.advanced_seats, self.max_rounds = players, set(advanced_seats), max_rounds
        counts = role_counts(players)
        self.roles = [role for role, count in counts.items() for _ in range(count)]
        self.rng.shuffle(self.roles)
        self.alive = list(range(players))
        self.deck = ["L"] * 6 + ["F"] * 11
        self.rng.shuffle(self.deck)
        self.discard = []
        self.history = [[] for _ in range(players)]
        self.lp = self.fp = self.tracker = 0
        self.president = self.rng.randrange(players)
        self.last_president = self.last_chancellor = None
        self.resume_after = None
        self.investigated = set()
        self.winner = self.win_reason = None
        self.rounds, self.action_count = 0, 0
        self.agent = SecretDictatorAgent()

    def _public(self, event):
        for history in self.history:
            history.append(dict(event))

    def _next_alive(self, seat):
        return next((seat + i) % self.players for i in range(1, self.players + 1)
                    if (seat + i) % self.players in self.alive)

    def eligible_chancellors(self):
        blocked = {self.president, self.last_chancellor}
        if len(self.alive) > 5:
            blocked.add(self.last_president)
        return [p for p in self.alive if p not in blocked]

    def observe(self, me, actions, **extra):
        role = self.roles[me]
        known = {str(me): role}
        if role == "fascist" or role == "dictator" and self.players <= 6:
            known.update({str(p): r for p, r in enumerate(self.roles) if r != "liberal"})
        return {"players": self.players, "me": me, "role": role, "known_roles": known,
                "alive": self.alive.copy(), "fascist_policies": self.fp, "liberal_policies": self.lp,
                "election_tracker": self.tracker, "president": self.president,
                "history": self.history[me], "legal_actions": actions, **extra}

    def _baseline(self, ob):
        actions, role = ob["legal_actions"], ob["role"]
        kind = actions[0]["type"]
        if kind == "vote":
            return next(a for a in actions if a["approve"])
        if kind in ("discard", "enact"):
            wanted = "L" if role != "liberal" else "F"
            if kind == "enact":
                wanted = "F" if role != "liberal" else "L"
            return next((a for a in actions if a.get("policy") == wanted), actions[0])
        if kind == "respond_veto":
            want = ("F" if role != "liberal" else "L") not in ob.get("hand", [])
            return next(a for a in actions if a["approve"] == want)
        # Do not make the baseline omniscient: only use its own permitted role knowledge.
        if kind == "nominate" and role != "liberal" and self.fp >= 3:
            leader = next((int(p) for p, r in ob["known_roles"].items() if r == "dictator"), None)
            if leader is not None:
                win = next((a for a in actions if a.get("target") == leader), None)
                if win:
                    return win
        if kind == "execute" and role != "liberal":
            safe = [a for a in actions if ob["known_roles"].get(str(a["target"])) != "dictator"]
            if safe:
                return self.rng.choice(safe)
        return self.rng.choice(actions)

    def choose(self, me, actions, **extra):
        observation = self.observe(me, actions, **extra)
        action = self.agent.choose(observation)["action"] if me in self.advanced_seats else self._baseline(observation)
        if action not in actions:
            raise AssertionError("Secret Dictator agent returned an illegal action")
        self.action_count += 1
        return action

    def _reshuffle_if_needed(self):
        if len(self.deck) < 3:
            self.deck += self.discard
            self.discard = []
            self.rng.shuffle(self.deck)

    def _check_cards(self):
        if len(self.deck) + len(self.discard) + self.lp + self.fp != 17:
            raise AssertionError("policy tiles were lost or duplicated")
        if self.deck.count("L") + self.discard.count("L") + self.lp != 6:
            raise AssertionError("liberal policy conservation failed")
        if self.deck.count("F") + self.discard.count("F") + self.fp != 11:
            raise AssertionError("fascist policy conservation failed")

    def _enact(self, policy, chaos=False):
        self.lp += policy == "L"
        self.fp += policy == "F"
        self.tracker = 0
        if chaos:
            self.last_president = self.last_chancellor = None
            self._public({"type": "chaos", "policy": policy})
        if self.lp >= 5:
            self.winner, self.win_reason = "liberal", "five_liberal_policies"
        if self.fp >= 6:
            self.winner, self.win_reason = "fascist", "six_fascist_policies"

    def _failed_government(self):
        self.tracker += 1
        if self.tracker == 3:
            self._enact(self.deck.pop(0), chaos=True)
            self._reshuffle_if_needed()

    def _advance(self, special_target=None):
        if special_target is not None:
            self.resume_after, self.president = self.president, special_target
        elif self.resume_after is not None:
            self.president = self._next_alive(self.resume_after)
            self.resume_after = None
        else:
            self.president = self._next_alive(self.president)

    def step(self):
        if self.winner:
            raise ValueError("game is already over")
        self.rounds += 1
        eligible = self.eligible_chancellors()
        if not eligible:
            raise AssertionError("no eligible chancellor")
        chancellor = self.choose(self.president, [{"type": "nominate", "target": p} for p in eligible])["target"]
        ballots = {p: self.choose(p, [{"type": "vote", "approve": True}, {"type": "vote", "approve": False}],
                                 chancellor=chancellor)["approve"] for p in self.alive}
        self._public({"type": "election", "president": self.president, "chancellor": chancellor,
                      "votes": ballots})
        if sum(ballots.values()) <= len(self.alive) / 2:
            self._failed_government()
            self._advance()
            self._check_cards()
            return
        self.last_president, self.last_chancellor = self.president, chancellor
        if self.fp >= 3:
            if self.roles[chancellor] == "dictator":
                self.winner, self.win_reason = "fascist", "dictator_elected"
                return
            self._public({"type": "non_dictator", "player": chancellor})
        hand = self.deck[:3]
        self.deck = self.deck[3:]
        choices = [{"type": "discard", "policy": p} for p in sorted(set(hand))]
        discarded = self.choose(self.president, choices, hand=hand.copy(), chancellor=chancellor)["policy"]
        hand.remove(discarded)
        self.discard.append(discarded)
        passed_hand = hand.copy()
        choices = [{"type": "enact", "policy": p} for p in sorted(set(hand))]
        if self.fp >= 5:
            choices.append({"type": "request_veto"})
        decision = self.choose(chancellor, choices, hand=hand.copy(), chancellor=chancellor)
        if decision["type"] == "request_veto":
            accepted = self.choose(self.president, [{"type": "respond_veto", "approve": True},
                                                  {"type": "respond_veto", "approve": False}],
                                   hand=hand.copy(), chancellor=chancellor)["approve"]
            if accepted:
                self.discard += hand
                self._public({"type": "veto", "president": self.president, "chancellor": chancellor})
                self._reshuffle_if_needed()
                self._failed_government()
                self._reshuffle_if_needed()
                self._advance()
                self._check_cards()
                return
            decision = self.choose(chancellor, [a for a in choices if a["type"] == "enact"],
                                   hand=hand.copy(), chancellor=chancellor)
        policy = decision["policy"]
        hand.remove(policy)
        self.discard += hand
        # Remaining public pool is known; actual hidden draw/discard counts are not.
        self._public({"type": "policy", "president": self.president, "chancellor": chancellor,
                      "policy": policy, "pool_liberal": 6 - self.lp, "pool_fascist": 11 - self.fp,
                      "fascist_before": self.fp, "liberal_before": self.lp})
        for observer in (self.president, chancellor):
            self.history[observer][-1].update({"observer": observer, "passed_hand": passed_hand.copy()})
        self._enact(policy)
        self._reshuffle_if_needed()
        special_target = None
        if not self.winner and policy == "F":
            power = POWER_TRACKS[self.players].get(self.fp)
            if power == "peek":
                self.history[self.president].append({"type": "peek", "policies": self.deck[:3]})
            elif power == "investigate":
                candidates = [p for p in self.alive if p != self.president and p not in self.investigated]
                target = self.choose(self.president, [{"type": "investigate", "target": p} for p in candidates])["target"]
                self.investigated.add(target)
                self.history[self.president].append({"type": "investigation_result", "observer": self.president,
                                                     "target": target, "party": party(self.roles[target])})
            elif power == "special_election":
                special_target = self.choose(self.president, [{"type": "special_election", "target": p}
                                                             for p in self.alive if p != self.president])["target"]
            elif power == "execute":
                target = self.choose(self.president, [{"type": "execute", "target": p}
                                                     for p in self.alive if p != self.president])["target"]
                self.alive.remove(target)
                if self.roles[target] == "dictator":
                    self.winner, self.win_reason = "liberal", "dictator_executed"
                else:
                    self._public({"type": "non_dictator", "player": target})
        self._advance(special_target)
        self._check_cards()

    def run(self):
        while not self.winner and self.rounds < self.max_rounds:
            self.step()
        return {"winner": self.winner, "reason": self.win_reason, "rounds": self.rounds,
                "roles": self.roles.copy(), "liberal_policies": self.lp, "fascist_policies": self.fp,
                "action_count": self.action_count, "finished": self.winner is not None}
