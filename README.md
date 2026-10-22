# Board Game Challenge — local agent project

Three offline Python agents, local evaluation environments, automated checks, and
portable agent bundles. Python 3.11 or newer is the only runtime requirement;
there are no API keys, paid services, downloads, or third-party runtime dependencies.

**Status: implemented for local assumptions; not submitted and not verified against
the challenge.** The organizer's rules, agent interface, time limits, and submission
page were unavailable. The user authorized proceeding from known game rules.
See [PROJECT_STATUS.md](PROJECT_STATUS.md) for the remaining integration work.

The supplied deadline is **Sunday, November 1, 2026, 11:59 p.m. CST**. This project
does not schedule a background job or upload a submission.

Start with [the measured results](reports/RESULTS.md) or [the project status](PROJECT_STATUS.md).
Run `python scripts/validate.py` to recheck tests and rebuild all three portable agents
into `dist/` (generated locally; not committed).

## Quick start on Windows

Open a terminal in this folder, then run:

```powershell
python -m unittest discover -s tests -v
Get-Content examples/connect4.jsonl | python -m agents --action-only
Get-Content examples/clue.jsonl | python -m agents --action-only
Get-Content examples/secret-dictator.jsonl | python -m agents --action-only
python scripts/play.py connect4
```

On Linux/macOS, use `python3` when appropriate and replace `Get-Content` with `cat`.
Installation is optional. Running directly from this folder needs no package manager.

```powershell
python scripts/benchmark.py --games 36 --time-ms 50
python scripts/build_bundles.py
Get-Content examples/connect4.jsonl | python dist/connect4-agent.pyz
```

Bundles return **actions only**. The development runner includes private diagnostics
unless `--action-only` is set. Never forward diagnostics to other players.

## Agent designs

| Agent | Strategy | Practical limits |
|---|---|---|
| Connect 4 | Bitboards; immediate wins and forced blocks; non-losing move pruning; iterative-deepening alpha-beta; mirror-aware transposition table; central control and line evaluation | Standard 7 columns, 6 rows, four in a row. Depth/time/node bounded, so not a full perfect-play solver. |
| Clue | Exact ownership constraints, hand sizes, category restrictions, public passes, refutation disjunctions and private reveals; sampled information gain; reuse of already-revealed cards | Samples are feasible randomized deals, **not uniform posterior samples**. Accusations require a proof. Physical movement needs legal options from the platform. |
| Secret Dictator | Exact enumeration of role assignments consistent with verified facts; heuristic behavior likelihoods; role-aware nominations, votes, policy choices, investigations, special elections, executions and vetoes | Assumes a renamed Secret Hitler-style ruleset. No language-model negotiation, calibrated opponent model, or tournament-optimality claim. |

Default move budgets: Connect 4 250 ms; Clue 500 ms. These are cooperative wall-clock
budgets checked during work, not an operating-system-enforced deadline. Interpreter
startup, input parsing, output serialization and a small check interval add overhead.
Secret Dictator enumerates at most 840 initial role assignments; its heuristic does
not use a search-time setting. See [PROTOCOL.md](PROTOCOL.md).

## Local environments and evaluation

- Connect 4: standard alternating 7x6 games against random, tactical and greedy baselines.
- Clue: **deduction-only arena**, with classic cards/dealing/refutations, alternating
  rooms and all remaining rooms reachable. It omits the mansion grid, dice, secret
  passages and token relocation. Its win rates do not measure full classic Clue.
- Secret Dictator: 5–10 players, policy deck, role visibility, voting/term limits,
  chaos, presidential powers, special-election rotation and vetoes. It omits table
  discussion and public legislative claims. The baseline normally approves elections
  and uses simple role-aware policy selection. This is a weak opponent population.

Benchmarks record seeds, seat/role, outcomes and Wilson intervals. Limited samples,
weak opponents and local rule assumptions mean these results do not predict a
challenge leaderboard. Time-based search may choose differently on different
machines despite a fixed seed. For repeatable search effort, cap nodes/depth and
provide a sufficiently generous time budget.

## Tests

49 automated tests, standard library `unittest` only. Run them with:

```powershell
python -m unittest discover -s tests -v
```

### Connect 4 — [tests/test_connect4.py](tests/test_connect4.py) (9)

| Test | Checks |
|---|---|
| `test_immediate_win` | Takes a winning move when one is available |
| `test_must_block` | Blocks the opponent's immediate win |
| `test_window_count` | Line/window evaluation counts are correct |
| `test_terminal_and_invalid_moves` | Terminal positions and illegal moves are handled |
| `test_invalid_boards` | Malformed or impossible boards are rejected |
| `test_random_differential_move_logic` | Bitboard move logic matches an independent implementation on random positions |
| `test_endgames_against_independent_exhaustive_oracle` | Endgame choices agree with an exhaustive solver |
| `test_budget_always_returns_legal_fallback` | A tiny time budget still yields a legal move |
| `test_mirrored_tactics` | Tactics are found in mirrored positions |

### Clue — [tests/test_clue.py](tests/test_clue.py) (11)

| Test | Checks |
|---|---|
| `test_own_hand_and_one_card_per_category` | Own hand and one-solution-card-per-category constraints |
| `test_passes_are_public_evidence` | Players passing on a suggestion are recorded as not holding those cards |
| `test_only_passers_before_responder_are_excluded` | Only players before the refuter are treated as passers |
| `test_refutation_disjunction_and_hand_capacity` | "Holds at least one of" refutations combine with hand sizes |
| `test_contradiction_is_not_silently_ignored` | Inconsistent evidence raises an error |
| `test_other_players_private_reveals_are_rejected` | Private reveals to other players cannot leak in |
| `test_one_sample_does_not_authorize_accusation` | Sampling alone never triggers an accusation |
| `test_proven_accusation` | Accuses once the solution is logically proven |
| `test_legal_room_restriction_and_no_movement` | Suggestions respect legal rooms; no invented movement |
| `test_reuse_revealed_card` | Reuses already-revealed cards in suggestions |
| `test_feasible_samples_respect_constraints` | Sampled deals satisfy every known constraint |

### Secret Dictator — [tests/test_secret_dictator.py](tests/test_secret_dictator.py) (14)

| Test | Checks |
|---|---|
| `test_role_counts_and_worlds` | Role counts per table size and enumerated worlds |
| `test_prior_and_normalization` | Prior and belief normalization |
| `test_non_dictator_does_not_mean_liberal` | "Not the dictator" is not treated as "liberal" |
| `test_verified_investigation_and_claim_are_different` | Verified investigations vs. unverified claims |
| `test_other_players_private_information_rejected` | Other players' private info is rejected |
| `test_policy_outcome_never_proves_a_role` | Enacted policies alone never prove a role |
| `test_private_mixed_pair_is_stronger_evidence_than_public_outcome` | Privately seen policy pairs weigh more than public outcomes |
| `test_private_forced_pair_is_not_evidence_of_sabotage` | A forced pair is not counted as sabotage |
| `test_private_legislative_leak_is_rejected` | Legislative info the agent didn't see is rejected |
| `test_immediate_dictator_nomination` | Nominates the dictator when that wins immediately |
| `test_never_execute_known_dictator_on_own_team` | Never executes its own team's known dictator |
| `test_liberal_blocks_known_dictator_election` | Liberals vote down a known dictator's election |
| `test_policies_and_veto` | Policy selection and veto decisions |
| `test_dictator_adapts_policy_to_observed_voting_resistance` | Dictator adapts play to how permissive voting is |

### Simulation arenas — [tests/test_arenas.py](tests/test_arenas.py) (10)

| Test | Checks |
|---|---|
| `test_connect4_games_terminate_with_legal_actions` | Full Connect 4 games finish with only legal moves |
| `test_clue_hides_private_cards_and_finishes` | Clue games finish without exposing private cards |
| `test_secret_dictator_games_all_table_sizes` | Games run for every table size, 5–10 players |
| `test_chaos_resets_term_limits_and_grants_no_power` | Chaos clears term limits and grants no power |
| `test_five_alive_only_previous_chancellor_is_limited` | Term-limit rule with five players alive |
| `test_special_election_returns_to_original_rotation` | Presidency returns to normal order after a special election |
| `test_role_visibility_matches_assumed_rules` | Who sees whose role matches the assumed rules |
| `test_veto_chaos_with_empty_draw_pile` | Veto into chaos with an empty draw pile |
| `test_legislative_private_pair_only_reaches_participants` | Private policy cards only reach the president/chancellor |
| `test_all_advanced_tables_terminate` | Tables of advanced agents always finish |

### Protocol — [tests/test_protocol.py](tests/test_protocol.py) (5)

| Test | Checks |
|---|---|
| `test_all_examples_are_executable` | Every file in `examples/` produces a valid action |
| `test_action_only_has_no_diagnostics` | `--action-only` output contains no private diagnostics |
| `test_error_then_valid_message_in_same_process` | Recovers after a bad message in a long-running process |
| `test_invalid_interface_and_nonfinite_json` | Rejects unknown interfaces and NaN/Infinity JSON |
| `test_malformed_shapes_and_limits_return_errors_without_crashing` | Malformed or oversized input returns errors, not crashes |

## Layout

```text
agents/                 strategy cores, local protocol, simulation arenas
examples/               one executable JSON request for each game
prompts/                fallback instructions for prompt-based challenge platforms
scripts/play.py         interactive Connect 4 and simulation summaries
scripts/benchmark.py    seeded local comparisons
scripts/build_bundles.py portable .pyz agents plus source package and checksums
scripts/validate.py     correctness, Python 3.11 syntax and packaging checks
tests/                  differential, proof, privacy, protocol and full-game checks
reports/                measured local results
dist/                   generated bundles, manifest and source archive
```

## Rule references and attribution

The local assumptions were checked against [Hasbro's Connect 4 overview](https://instructions.hasbro.com/en-us/instruction/Connect-4-Game),
[Hasbro's classic Clue instructions](https://www.hasbro.com/common/instruct/clueins.pdf),
and the [Secret Hitler publisher's rules](https://www.secrethitler.com/assets/Secret_Hitler_Rules.pdf).
These are reference games, not verified challenge rules.

The Secret Dictator simulation adapts Secret Hitler gameplay by Mike Boxleiter,
Tommy Maranges and Mac Schubert, replacing the named leader with “dictator” and
omitting the theme, artwork and discussion phase. The publisher makes its game
available under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
The local Secret Dictator rules adaptation is shared under those same terms.
No publisher artwork or rulebook text is bundled. Game names belong to their
respective owners; this project has no publisher or challenge-organizer affiliation.
