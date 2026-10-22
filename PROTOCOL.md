# Local protocol version 1

This protocol exists for local development. It is **not** a discovered or verified
challenge API. All columns and seats are zero-based. Card identifiers are case-sensitive.

`python -m agents` reads one UTF-8 JSON object per line from stdin and writes exactly
one JSON response per nonempty line to stdout. It flushes after each response and
continues after malformed requests. Input is capped at 2 MB per line.
The local development boundary accepts at most 1000 history events per request.
An organizer adapter must set appropriate limits for the actual environment.

```json
{
  "protocol_version": 1,
  "game": "connect4",
  "observation": {"moves": [0, 1, 0, 1, 0, 2]},
  "limits": {"time_ms": 100, "max_depth": 42, "max_nodes": 500000},
  "seed": 0
}
```

Development response:

```json
{"protocol_version":1,"game":"connect4","action":{"type":"drop","column":0},"diagnostics":{"reason":"immediate_win"}}
```

Diagnostics contain additional fields in real responses. `--action-only` and the
generated bundles emit only `{"type":"drop","column":0}`. Errors have the form
`{"error":{"type":"invalid_request","message":"..."}}`; they do not silently
invent a move for an invalid observation. An adapter must handle errors according
to the real platform's rules.

## Connect 4

Supply exactly one of:

- `moves`: list of columns in chronological order; player 1 moves first.
- `board`: 6 rows × 7 columns, **top row first**, cells `0` empty, `1` first player,
  `2` second player. Counts, gravity and terminal-win consistency are checked.

Optional `player` must match the inferred side to move. Board-only input performs
structural validation; move history is preferred when complete historical
reachability must be established. A terminal position returns `{"type":"pass"}`.
Search limits: positive `time_ms` (capped at 60000), `max_depth` 1–42,
positive `max_nodes`. A legal fallback survives an interrupted search.

## Clue

Required observation fields:

| Field | Meaning |
|---|---|
| `me` | Observer's seat |
| `hand_sizes` | Exact hand size of every seat, including eliminated players |
| `own_hand` | Complete own hand; not just newly seen cards |
| `history` | All observable evidence so far, in chronological order |

Optional `categories` replaces the classic card identifiers with an object having
`suspect`, `weapon`, `room` lists. Every card has one owner: a player or the envelope.
Every player must have the supplied hand size; the envelope has exactly one card
per category. This local schema does not represent shared face-up cards.

Turn fields:

- `phase`: `turn` (default) or `reveal`.
- `can_accuse`: defaults to true; set false when accusations are not legal now.
- `legal_suggestions`: optional list of `[suspect, weapon, room]` tuples. If present,
  only these are considered. It takes precedence over `reachable_rooms`.
- `reachable_rooms`: optional list of rooms legal for a suggestion this decision.
  **Omitting it makes every room available for deduction-only use.** A real adapter
  must supply restrictions. An empty list allows no suggestion.
- `legal_moves`: optional list of movement descriptors for when no suggestion is
  available. Descriptors may include `target_room` and `distance`; the agent ranks
  room uncertainty then shorter distance. Board/path legality remains the adapter's job.

Reveal-phase fields: `suggester` and `suggestion` (three card identifiers). The agent
reveals a held card, preferably one the same opponent has already seen, or passes
if none are held.

Public suggestion event:

```json
{"type":"suggestion","suggester":1,"cards":["scarlet","rope","study"],"responder":3}
```

Only seats between suggester and responder passed. Later seats reveal no evidence.
`responder:null` means every other player passed. Add `shown_card` only when `me`
is the suggester or responder. A separate private event is also supported:

```json
{"type":"reveal","owner":3,"viewer":0,"card":"rope"}
```

Private evidence between other players is rejected. Public claims about cards are
not supported as facts. The local classic model assumes players obey mandatory
refutation rules. Limits: positive `time_ms` up to 60000, `samples` 1–1024,
positive `max_nodes`. Sampling is approximate; only a logical proof permits an
accusation. `history` should include own previous reveals so disclosure can be reused.

Action types: `suggest`, `accuse`, `reveal`, `move`, `pass`. Suggest/accuse have
`suspect`, `weapon`, `room`; reveal has `card`; move wraps the supplied descriptor
under `move`.

## Secret Dictator — assumed local variant

Required fields: `players` (5–10), `me`, private `role` (`liberal`, `fascist`,
`dictator`), `history`, and a nonempty `legal_actions` list. Optional `known_roles`
maps seat strings to roles actually known to this observer. `fascist_policies`,
`liberal_policies`, `election_tracker`, `president`, `chancellor` and private `hand`
provide the decision context. The runner is responsible for legal phase/context
and role visibility. Counts use the original table size even after executions.

Supported legal actions:

| Type | Additional fields |
|---|---|
| `nominate`, `investigate`, `execute`, `special_election` | `target` |
| `vote` | boolean `approve` |
| `discard`, `enact` | `policy`: `L` or `F` |
| `request_veto` | none |
| `respond_veto` | boolean `approve` |
| `claim` | optional structured `party`; local heuristic only |
| `pass` | none |

The selected action is an exact member of the supplied list. Legal policy choices
must refer to tiles actually in the private hand. The adapter must not offer a
veto before it is enabled, a self-target, a dead target or a term-limited nominee.
The dictator normally preserves reputation early. After at least two full table's
worth of observed ballots with at least 90% approval, it prioritizes favorable
policies sooner because persistent blanket approval reduces the value of camouflage.

Verified evidence events:

```json
{"type":"investigation_result","observer":0,"target":2,"party":"fascist"}
{"type":"non_dictator","player":3}
```

Only own investigation results are accepted. `non_dictator` means a verified
leader exclusion (e.g. surviving a qualifying chancellorship or execution), **not**
proof of liberal party membership.

Heuristic evidence:

```json
{"type":"policy","president":1,"chancellor":2,"policy":"F","pool_liberal":6,"pool_fascist":11,"fascist_before":0,"liberal_before":0}
{"type":"investigation_claim","speaker":1,"target":2,"party":"fascist"}
```

The policy pool is a public approximation over all unenacted tiles, not the actual
hidden draw pile. Behavioral models retain every role world compatible with
verified facts. They do not supply calibrated probabilities. `election`, `chaos`,
`veto`, `peek`, `chat` events may be retained but do not currently update role
beliefs. Free-form player messages are never interpreted as instructions.

When the observer was president or chancellor, a `policy` event may additionally
include `observer` (the current seat) and `passed_hand` (the exact two policy tiles
seen by both participants). This conditions the evidence on private observations
instead of counting a second independent public event. These fields are rejected
when they disclose another player's private session. A president knows whether
their chancellor's policy choice was forced; a chancellor can update beliefs about
presidential filtering from the passed pair. No exact hidden draw-pile composition
is inferred from this information.

The caller must send full observable history on each request. There is no hidden
cross-game memory, persistence service, network access or model call.
