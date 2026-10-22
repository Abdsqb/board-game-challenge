"""Versioned local protocol. This is NOT the organizer's submission interface."""

from dataclasses import asdict
import json
from .clue import ClueAgent
from .connect4 import Connect4Agent, Position
from .secret_dictator import SecretDictatorAgent

PROTOCOL_VERSION = 1
MAX_LINE_BYTES = 2_000_000


def decide(request, game=None):
    if not isinstance(request, dict):
        raise ValueError("request must be a JSON object")
    if request.get("protocol_version", PROTOCOL_VERSION) != PROTOCOL_VERSION:
        raise ValueError("unsupported protocol version")
    requested_game = request.get("game", game)
    if game is not None and requested_game != game:
        raise ValueError("request game conflicts with the selected agent")
    observation = request.get("observation")
    if not isinstance(observation, dict):
        raise ValueError("observation must be a JSON object")
    for field in ("history", "legal_actions"):
        if field in observation and (not isinstance(observation[field], list)
                                    or any(not isinstance(item, dict) for item in observation[field])):
            raise ValueError(f"{field} must be a list of objects")
    if "history" in observation and len(observation["history"]) > 1000:
        raise ValueError("local protocol supports at most 1000 history events")
    for field in ("known_roles", "categories"):
        if field in observation and not isinstance(observation[field], dict):
            raise ValueError(f"{field} must be an object")
    limits = request.get("limits", {})
    if not isinstance(limits, dict):
        raise ValueError("limits must be an object")
    if requested_game == "connect4":
        if "moves" in observation and "board" in observation:
            raise ValueError("provide moves or board, not both")
        if "moves" not in observation and "board" not in observation:
            raise ValueError("provide a move history or board")
        position = (Position.from_moves(observation["moves"]) if "moves" in observation
                    else Position.from_rows(observation["board"]))
        if "player" in observation and observation["player"] != position.player:
            raise ValueError("player disagrees with the board's move counts")
        result = Connect4Agent(time_limit_ms=limits.get("time_ms", 250),
                               max_depth=limits.get("max_depth", 42),
                               max_nodes=limits.get("max_nodes", 500_000)).choose(position)
        action = {"type": "drop", "column": result.column} if result.column is not None else {"type": "pass"}
        response = {"action": action, "diagnostics": asdict(result)}
    elif requested_game == "clue":
        response = ClueAgent(time_limit_ms=limits.get("time_ms", 500),
                             samples=limits.get("samples", 96),
                             seed=request.get("seed", 0),
                             max_nodes=limits.get("max_nodes", 80_000)).choose(observation)
    elif requested_game == "secret-dictator":
        response = SecretDictatorAgent().choose(observation)
    else:
        raise ValueError("game must be connect4, clue or secret-dictator")
    return {"protocol_version": PROTOCOL_VERSION, "game": requested_game, **response}


def parse_line(line):
    if len(line.encode("utf-8")) > MAX_LINE_BYTES:
        raise ValueError("request exceeds the local 2 MB size limit")
    def reject_constant(value):
        raise ValueError(f"non-finite JSON value is not allowed: {value}")
    return json.loads(line, parse_constant=reject_constant)
