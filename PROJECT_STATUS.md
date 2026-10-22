# Project plan and handoff

## Objective

Build the strongest practical, tested agents we can from the available information
for Connect 4, Clue and Secret Dictator. Make all rule assumptions visible and leave
a small, well-defined adapter boundary for the actual competition.

## Known requirements

- Submit one agent for each of the three games.
- AI assistance is expected and encouraged.
- User-supplied deadline: Sunday, November 1, 2026, 11:59 p.m. CST.
- The challenge itself contains additional rules that are currently unavailable.
- The user explicitly authorized proceeding without access to those materials.
- Keep the existing case-tracker app and its unfinished edits intact.

## Delivery plan

| Phase | Acceptance criterion | Status |
|---|---|---|
| Project isolation | All new work is under `board-game-challenge/` | Complete |
| Rule assumptions | Explicit reference rules and unsupported variants documented | Complete |
| Strategy cores | All three agents run offline and use only supplied observations | Complete |
| Correctness | Independent move checks, deduction proof checks, privacy and protocol checks pass | Complete; see validation report |
| Local play | Full Connect 4, deduction-only Clue, assumed Secret Dictator simulators | Complete |
| Playing-strength evaluation | Compare seeds/seats/roles against named baselines and retain actual outcomes | Complete; limitations in results report |
| Portable packaging | Three action-only agent bundles, source archive, checksums, isolated smoke tests | Complete; package manifest records checks |
| Challenge integration | Implement actual observation/action format, allowed dependencies and resource limits | Awaiting organizer materials |
| Submission | Upload and obtain organizer receipt/acceptance | Not attempted; access unavailable |

## Organizer information needed later

1. Actual rule variants, including Clue board/movement and Secret Dictator phases.
2. Whether an agent is source code, an executable, a container, an endpoint, or a prompt.
3. Observation fields, legal-action representation, action schema and indexing.
4. Per-move and per-game CPU/time/memory limits, Python version, and persistence model.
5. Whether network calls, external models, additional packages or precomputed data are allowed.
6. Scoring, tie-breaks, illegal-action handling, seat rotation, team composition and test access.
7. Submission mechanism, revision policy, receipt, and exact deadline timezone.

Do not infer compatibility from the local JSON interface or from passing local tests.
Do not report this project as submitted without an actual organizer receipt.

## Local acceptance evidence

- 49 automated tests pass, including independent Connect 4 differential/endgame
  checks, Clue proof/privacy checks, protocol recovery and simulated games.
- Each portable bundle passes a smoke test with isolated Python imports from a
  directory outside the source package, returning actions only.
- Connect 4: 359/360 wins against the three named local baselines at a requested
  60 ms search budget. This does not establish perfect play.
- Clue: 41/120 wins versus 27/120 for its baseline in the deduction-only arena;
  no false accusations occurred in that benchmark.
- Secret Dictator: 262/600 team wins versus 256/600 for baseline in held-out local
  games. This does not establish a reliable overall advantage.
- See `reports/RESULTS.md`, `reports/validation.json` and `dist/manifest.json` for
  measured details, timing limits and artifact checksums.

## Integration procedure

1. Save the original rules/starter SDK as reference material.
2. Map observable fields to the local core without including opponents' private data.
3. Map legal actions back to the platform's exact accepted format; forward actions only.
4. For Clue, provide legal suggestions/reachable rooms and legal movement options from
   the real board, including secret passages, blocked squares and room-entry restrictions.
5. Update the Secret Dictator model if its roles, powers, policy counts or victory
   conditions differ from the assumed reference game.
6. Set budgets below platform limits, allowing for process startup and communication.
7. Run organizer examples and seeded matches, then validate the actual packaged artifact.
8. Upload before lock, save the receipt, and rerun the submission once if the platform
   supports a smoke test. No unattended background submission is configured here.

## Further strength work with a real test environment

- Connect 4: compare with a stronger external solver/opponent, expand tactical puzzles,
  consider a compiled search backend or opening book if rules and limits permit.
- Clue: replace approximate deal sampling with calibrated posterior sampling if it
  improves measured decisions; add board-aware planning against the organizer's map.
- Secret Dictator: estimate opponent behavior from actual matches, model policy claims,
  make use of private policy peeks, and measure strategy across stronger populations.

These are bounded next steps, not a claim that more computation can guarantee
“perfect” tournament play in hidden-information games.
