"""Clue ownership constraints and information-gathering decisions.

Logical conclusions and approximate samples are deliberately separate. Samples
rank suggestions; an accusation requires a proof, never just high sample frequency.
Movement is supplied by the caller as reachable rooms/legal actions.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import product
from math import isfinite, log2
import random
from time import perf_counter

CATEGORIES = {
    "suspect": ["scarlet", "mustard", "white", "green", "peacock", "plum"],
    "weapon": ["candlestick", "knife", "lead_pipe", "revolver", "rope", "wrench"],
    "room": ["kitchen", "ballroom", "conservatory", "dining_room", "billiard_room",
             "library", "lounge", "hall", "study"],
}


class InconsistentEvidence(ValueError):
    pass


class _Limit(Exception):
    pass


@dataclass
class _Budget:
    deadline: float
    max_nodes: int
    nodes: int = 0

    def check(self):
        self.nodes += 1
        if self.nodes > self.max_nodes or perf_counter() >= self.deadline:
            raise _Limit


class Knowledge:
    def __init__(self, players, me, hand_sizes, own_hand, categories=None):
        self.categories = categories or CATEGORIES
        if set(self.categories) != {"suspect", "weapon", "room"}:
            raise ValueError("categories must be suspect, weapon and room")
        if any(not values for values in self.categories.values()):
            raise ValueError("categories cannot be empty")
        self.category_names = ("suspect", "weapon", "room")
        self.cards = tuple(c for name in self.category_names for c in self.categories[name])
        if len(set(self.cards)) != len(self.cards):
            raise ValueError("card identifiers must be unique")
        if not 2 <= players <= 6 or type(me) is not int or not 0 <= me < players:
            raise ValueError("invalid player count or seat")
        if len(hand_sizes) != players or any(type(n) is not int or n < 0 for n in hand_sizes):
            raise ValueError("one nonnegative hand size is required for each player")
        if sum(hand_sizes) != len(self.cards) - 3:
            raise ValueError("hand sizes must account for every non-envelope card")
        if len(set(own_hand)) != len(own_hand) or len(own_hand) != hand_sizes[me]:
            raise ValueError("own_hand must be complete and match the hand size")
        self.players, self.me, self.envelope = players, me, players
        self.capacities = tuple(hand_sizes) + (3,)
        self.index = {card: i for i, card in enumerate(self.cards)}
        self.groups = tuple(tuple(self.index[c] for c in self.categories[name]) for name in self.category_names)
        self.domains = [(1 << (players + 1)) - 1 for _ in self.cards]
        self.clauses = []
        self.shown = defaultdict(set)
        own = set(own_hand)
        for card in own:
            self._assign(card, me)
        for card in self.cards:
            if card not in own:
                self._exclude(card, me)

    def _seat(self, owner):
        if type(owner) is not int or not 0 <= owner < self.players:
            raise ValueError("unknown player seat")

    def _assign(self, card, owner):
        if card not in self.index:
            raise ValueError(f"unknown card: {card}")
        self.domains[self.index[card]] &= 1 << owner

    def _exclude(self, card, owner):
        if card not in self.index:
            raise ValueError(f"unknown card: {card}")
        self.domains[self.index[card]] &= ~(1 << owner)

    def observe(self, event):
        kind = event.get("type")
        if kind == "reveal":
            owner, viewer, card = event["owner"], event["viewer"], event["card"]
            self._seat(owner)
            self._seat(viewer)
            if viewer != self.me and owner != self.me:
                raise ValueError("a private reveal between other players is not observable")
            self._assign(card, owner)
            if owner == self.me:
                self.shown[viewer].add(card)
        elif kind == "suggestion":
            suggester, cards = event["suggester"], event["cards"]
            self._seat(suggester)
            if len(cards) != 3 or any(cards[i] not in self.categories[name]
                                      for i, name in enumerate(self.category_names)):
                raise ValueError("a suggestion must contain suspect, weapon, room in that order")
            responder = event.get("responder")
            if responder is not None:
                self._seat(responder)
                if responder == suggester:
                    raise ValueError("a player cannot disprove their own suggestion")
            seat = (suggester + 1) % self.players
            while seat != suggester and seat != responder:
                for card in cards:
                    self._exclude(card, seat)
                seat = (seat + 1) % self.players
            if responder is not None:
                self.clauses.append((responder, tuple(self.index[c] for c in cards)))
            if "shown_card" in event:
                if responder is None or event["shown_card"] not in cards:
                    raise ValueError("invalid shown card")
                if suggester != self.me and responder != self.me:
                    raise ValueError("shown_card would leak another player's private evidence")
                self._assign(event["shown_card"], responder)
                if responder == self.me:
                    self.shown[suggester].add(event["shown_card"])
        else:
            raise ValueError("unsupported evidence event")

    def propagate(self, domains=None):
        d = list(self.domains if domains is None else domains)
        env = 1 << self.envelope
        changed = True
        while changed:
            before = tuple(d)
            if any(mask == 0 for mask in d):
                raise InconsistentEvidence("a card has no possible owner")
            for owner, capacity in enumerate(self.capacities):
                bit = 1 << owner
                fixed = [i for i, mask in enumerate(d) if mask == bit]
                possible = [i for i, mask in enumerate(d) if mask & bit]
                if len(fixed) > capacity or len(possible) < capacity:
                    raise InconsistentEvidence("evidence conflicts with a hand size")
                if len(fixed) == capacity:
                    for i in possible:
                        if d[i] != bit:
                            d[i] &= ~bit
                elif len(possible) == capacity:
                    for i in possible:
                        d[i] = bit
            for group in self.groups:
                fixed = [i for i in group if d[i] == env]
                possible = [i for i in group if d[i] & env]
                if len(fixed) > 1 or not possible:
                    raise InconsistentEvidence("envelope must contain one card of each category")
                if fixed:
                    for i in possible:
                        if i != fixed[0]:
                            d[i] &= ~env
                elif len(possible) == 1:
                    d[possible[0]] = env
            for owner, indices in self.clauses:
                bit = 1 << owner
                if any(d[i] == bit for i in indices):
                    continue
                possible = [i for i in indices if d[i] & bit]
                if not possible:
                    raise InconsistentEvidence("a recorded responder cannot hold any suggested card")
                if len(possible) == 1:
                    d[possible[0]] = bit
            changed = tuple(d) != before
        return d

    def solve_one(self, domains, rng, budget):
        budget.check()
        try:
            d = self.propagate(domains)
        except InconsistentEvidence:
            return None
        unresolved = [i for i, mask in enumerate(d) if mask.bit_count() > 1]
        if not unresolved:
            return tuple(mask.bit_length() - 1 for mask in d)
        # Randomized minimum-remaining-values search gives diverse feasible deals.
        # It is NOT a uniform posterior sampler; never use it to prove an accusation.
        smallest = min(d[i].bit_count() for i in unresolved)
        choices = [i for i in unresolved if d[i].bit_count() == smallest]
        i = rng.choice(choices)
        owners = [owner for owner in range(self.players + 1) if d[i] & (1 << owner)]
        rng.shuffle(owners)
        for owner in owners:
            child = d.copy()
            child[i] = 1 << owner
            result = self.solve_one(child, rng, budget)
            if result is not None:
                return result
        return None

    def forced_envelope(self, domains):
        env = 1 << self.envelope
        result = {}
        for name, group in zip(self.category_names, self.groups):
            fixed = [self.cards[i] for i in group if domains[i] == env]
            if len(fixed) != 1:
                return None
            result[name] = fixed[0]
        return result

    def envelope_of(self, world):
        return tuple(self.cards[next(i for i in group if world[i] == self.envelope)] for group in self.groups)


def _entropy(counts):
    total = sum(counts)
    return -sum((n / total) * log2(n / total) for n in counts if n) if total else 0.0


def information_gain(knowledge, worlds, cards, prepared=None):
    """Approximate envelope information, accounting for responder order and choice.

    Within each feasible deal, assume a responder selects each matching card with
    equal probability. Actual opponents may intentionally disclose less information.
    """
    by_outcome = defaultdict(Counter)
    envelopes = Counter()
    indices = [knowledge.index[c] for c in cards]
    prepared = prepared if prepared is not None else [(w, knowledge.envelope_of(w)) for w in worlds]
    for world, envelope in prepared:
        envelopes[envelope] += 1
        responder = (knowledge.me + 1) % knowledge.players
        while responder != knowledge.me:
            held = [i for i in indices if world[i] == responder]
            if held:
                for i in held:
                    by_outcome[(responder, i)][envelope] += 1 / len(held)
                break
            responder = (responder + 1) % knowledge.players
        else:
            by_outcome[(None, None)][envelope] += 1
    total = len(worlds)
    conditional = sum(sum(counter.values()) / total * _entropy(counter.values())
                      for counter in by_outcome.values()) if total else 0
    return max(0.0, _entropy(envelopes.values()) - conditional)


class ClueAgent:
    def __init__(self, time_limit_ms=500, samples=96, seed=0, max_nodes=80_000):
        if (type(time_limit_ms) not in (int, float) or not isfinite(time_limit_ms) or not 0 < time_limit_ms <= 60_000
                or type(samples) is not int or not 1 <= samples <= 1024
                or type(max_nodes) is not int or max_nodes < 1):
            raise ValueError("invalid deduction budget")
        self.time_limit_ms, self.samples, self.seed, self.max_nodes = time_limit_ms, samples, seed, max_nodes

    def choose(self, observation):
        started = perf_counter()
        categories = observation.get("categories")
        sizes = observation["hand_sizes"]
        k = Knowledge(len(sizes), observation["me"], sizes, observation["own_hand"], categories)
        for event in observation.get("history", []):
            k.observe(event)
        domains = k.propagate()
        phase = observation.get("phase", "turn")
        if phase == "reveal":
            cards = observation["suggestion"]
            viewer = observation["suggester"]
            k._seat(viewer)
            held = [c for c in cards if c in observation["own_hand"]]
            if not held:
                return {"action": {"type": "pass"}, "diagnostics": {"reason": "cannot_disprove"}}
            # Reuse a card this opponent has already seen, then one most widely seen.
            card = max(held, key=lambda c: (c in k.shown[viewer], sum(c in s for s in k.shown.values()), c))
            return {"action": {"type": "reveal", "card": card}, "diagnostics": {"reason": "minimize_new_disclosure"}}
        if phase != "turn":
            raise ValueError("Clue phase must be turn or reveal")
        solution = k.forced_envelope(domains)
        if solution and observation.get("can_accuse", True):
            return {"action": {"type": "accuse", **solution}, "diagnostics": {"proof": "constraint_propagation"}}
        rng = random.Random(self.seed)
        deadline = started + self.time_limit_ms / 1000
        budget = _Budget(min(deadline, started + self.time_limit_ms / 1000 * .65), self.max_nodes)
        worlds = []
        for _ in range(self.samples):
            try:
                world = k.solve_one(domains, rng, budget)
            except _Limit:
                break
            if world is None:
                raise InconsistentEvidence("no complete deal satisfies the evidence")
            worlds.append(world)
        proof = "unresolved"
        if worlds and len({k.envelope_of(w) for w in worlds}) == 1:
            candidate = k.envelope_of(worlds[0])
            proof_budget = _Budget(deadline, self.max_nodes - min(budget.nodes, self.max_nodes))
            try:
                proven = True
                for card in candidate:
                    alternative = domains.copy()
                    alternative[k.index[card]] &= ~(1 << k.envelope)
                    if k.solve_one(alternative, rng, proof_budget) is not None:
                        proven = False
                        break
                if proven:
                    solution = dict(zip(k.category_names, candidate))
                    proof = "exhaustive_counterexample_search"
            except _Limit:
                pass
            budget.nodes += proof_budget.nodes
        if solution and observation.get("can_accuse", True):
            action = {"type": "accuse", **solution}
        else:
            supplied = observation.get("legal_suggestions")
            reachable = observation.get("reachable_rooms")
            if supplied is not None:
                candidates = [tuple(c) for c in supplied]
            else:
                rooms = list(k.categories["room"]) if reachable is None else list(reachable)
                candidates = list(product(k.categories["suspect"], k.categories["weapon"], rooms))
            for cards in candidates:
                if len(cards) != 3 or any(cards[i] not in k.categories[name] for i, name in enumerate(k.category_names)):
                    raise ValueError("invalid legal suggestion")
            if not candidates:
                moves = observation.get("legal_moves", [])
                if moves:
                    # An adapter may attach target-room/distance estimates to legal moves.
                    def movement_value(move):
                        room = move.get("target_room")
                        uncertainty = bool(room in k.index and domains[k.index[room]] & (1 << k.envelope))
                        return uncertainty, -float(move.get("distance", 0))
                    action = {"type": "move", "move": max(moves, key=movement_value)}
                else:
                    action = {"type": "pass"}
            else:
                best, best_value = candidates[0], -1.0
                scored = 0
                prepared = [(w, k.envelope_of(w)) for w in worlds]
                if worlds:
                    # Rank the full candidate set cheaply before exact sampled
                    # scoring so tight budgets don't bias us to the first suspect.
                    card_entropy = {}
                    for card, i in k.index.items():
                        n = sum(w[i] == k.envelope for w in worlds)
                        card_entropy[card] = _entropy((n, len(worlds) - n))
                    rng.shuffle(candidates)
                    candidates.sort(key=lambda cards: sum(card_entropy[c] for c in cards), reverse=True)
                for cards in candidates:
                    if perf_counter() >= deadline:
                        break
                    if worlds:
                        value = information_gain(k, worlds, cards, prepared)
                    else:
                        value = sum(bool(domains[k.index[c]] & (1 << k.envelope)) for c in cards)
                    if value > best_value:
                        best, best_value = cards, value
                    scored += 1
                action = {"type": "suggest", **dict(zip(k.category_names, best))}
                proof = "approximate_information_gain" if worlds and scored else "legal_fallback"
        return {"action": action, "diagnostics": {"reason": proof, "feasible_samples": len(worlds),
                "sampling": "randomized_feasible_deals_not_uniform", "nodes": budget.nodes,
                "elapsed_ms": round((perf_counter() - started) * 1000, 3)}}
