# HALYARD / target SABLE — Phase 6 regeneration pass

Full pipeline re-run with the move-alias fix. All 19 checkpoints rebuilt from a single post-fix candidate generation.

---

## 1. Consistency verified before anything downstream ran

The mixed-vintage failure from two sessions ago is the one I most wanted not to repeat, so the check runs first and blocks:

| check | result |
|---|---|
| matrix cells | **4,248,276** across 19 files |
| files stale or empty | **0** |
| every matrix postdates the candidate regeneration | **yes** (oldest matrix is 1.9 min after `04a_candidates.tsv`) |

## 2. What the alias fix actually recovered

`MOVE_BUBBLEBEAM` / `MOVE_THUNDERPUNCH` / `MOVE_VICE_GRIP` now resolve to their current spellings.

| | count |
|---|---|
| recovered moves appearing in candidate builds | 1,240 |
| **published ceilings using a recovered move** | **167 (0.87% of the ladder)** |
| — Thunder Punch / Vise Grip / Bubble Beam | 119 / 38 / 10 |

Tier spread of those 167 rows: F 113, D 23, C 8, NR 7, B 6, A 4, S 4, S+ 2.

**The impact is real but small, and smaller than I projected.** I predicted "194 species-checkpoint pairs" from a level-up-only comparison; the true figure at the published-ceiling level is 167 rows, over 80% of them in the bottom two tiers. The recovered moves were mostly not good enough to change a recommendation that mattered.

**A claim I made and have to withdraw.** I justified this re-run partly on Poliwrath's orientation verdict flipping from "no special track" to having one. That was wrong: I measured its movepool using level-up entries only, but the generator has always included teachable moves, under which Poliwrath's Attack already exceeded 1.15× its Sp. Atk. It generates physical-only now exactly as it did before. The silent-loss defect was genuine and worth fixing on principle — no information should vanish without being logged — but the specific evidence I used to argue urgency did not hold up.

## 3. Invariants after regeneration

| # | Metric | Value | Threshold | Result |
|---|---|---|---|---|
| I1 | max item share | 0.277 (Berry Juice) | ≤ 0.25 | FAIL |
| I2 | max nature share | 0.281 (Calm) | ≤ 0.20 | FAIL |
| I3 | mean \|r\| VORP vs BST within (checkpoint, role) | **0.502** | ≤ 0.60 | **PASS** |
| I4 | cells with <3 forms within 10% of leader | 117 | 0 | FAIL |
| I5 | top-6 teams needing more copies than exist | 1 | 0 | FAIL |
| I6 | stat-perturbation sensitivity | **0.856** | ≥ 0.20 | **PASS** |
| I7 | max move share | 0.129 (Focus Punch) | ≤ 0.30 | **PASS** |

Essentially unchanged from the pre-fix run, which is the expected and correct outcome for a 0.87% perturbation.

Tier distribution, thresholds numeric on VORP, curve not forced:
`S+ 3.4% · S 2.9% · A 6.0% · B 10.0% · C 16.0% · D 27.5% · F 34.1%`

1,078 rows are `NR` — replacement level undefined — and excluded from tiers and every invariant. 984 rows carry `cant_miss`.

## 4. Route view — scope settled

The route tab is read-only: which routes hold which encounters, no missable tracking, no completion state. Confirmed fully derivable from `01_species.tsv` alone — **691 species with wild encounter records across 127 maps**. The 100%-UNK `missable` and `prerequisites` columns in `02_world.tsv` therefore no longer block Phase 7.

## 5. Standing failures — none are regressions

- **I1 / I2** are single-item and single-nature concentration inside the wall-and-support population. Berry Juice is the only cheap reliable longevity item in the catalogue; Calm is the default defensive nature. Fixing means widening the reliable options or documenting that the hack offers none — `builds.md` forbids rotating choices to close the gap.
- **I4's 117 cells** are mostly genuine role scarcity: roles with 1–5 total occupants cannot have three within 10% of a leader. The invariant conflates a pool fact with a scoring fact and should be split.
- **I5's single failure** is Choice Specs at checkpoint 4 — top-6 team wants 3 copies, 1 exists.

## 6. Ready for Phase 7

Blocking defects are cleared. Remaining known gaps, all documented and none blocking the app:

- 647 in-pool forms carry `earliest_cp = UNK` (61.7% of ladder rows) — the largest ranking uncertainty, not recoverable from supplied files
- 9 Imperium-custom boss forms absent from Phase 1
- Gift Pokémon and in-game trades absent from `02_world.tsv`
